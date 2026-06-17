"""
درگاه به‌پرداخت ملت — SOAP. پیاده‌سازی بر اساس مستند رسمی نگارش ۱.۳۸.

روند کامل (طبق مستند):
1. initiate → bpPayRequest: خروجی "ResCode,RefId" است. اگر ResCode == "0"،
   RefId را با POST فرم به startpay می‌فرستیم (نه redirect ساده). این درگاه
   redirect_url را به startpay می‌دهد ولی هدایت واقعی نیاز به فرم POST دارد
   (لایه‌ی Django این را در view مدیریت می‌کند).
2. بازگشت از بانک (callback POST): بانک ResCode, SaleOrderId, SaleReferenceId,
   RefId و ... را POST می‌کند. saleReferenceId و saleOrderId برای verify لازم‌اند.
3. verify → بسته به settle_mode:
   - "verify_settle" (پیش‌فرض، توصیه‌شده): bpVerifySettleRequest — تأیید و واریز
     اتمیک در یک فراخوانی. پنجره‌ی شکست بین verify و settle را می‌بندد.
   - "verify_only": فقط bpVerifyRequest. ⚠️ پول واریز نمی‌شود تا settle() صدا
     زده شود. اگر در ۲۰ دقیقه verify و در ۳ ساعت settle نشود، بانک Autoreversal
     می‌زند و وجه به مشتری برمی‌گردد.
4. settle() (فقط برای verify_only): bpSettleRequest — واریز نهایی.
5. reverse(): bpReversalRequest — برگشت وجه وقتی وضعیت پرداخت روشن نیست
   (timeout در verify). باید پس از verify و حداکثر ۳ ساعت پس از آن.
6. inquiry(): bpInquiryRequest — استعلام وضعیت وقتی verify پاسخ نداد.

نکات مستند که رعایت شده:
- مبلغ ریال است. orderId باید عددی (long) باشد.
- ResCode == "0" یعنی موفق در همه‌ی متدها.
- در verify: کدهای "43" (قبلاً verify شده) و "45" (settle شده) را موفق در نظر
  می‌گیریم (idempotent از سمت بانک).

برای SOAP به zeep نیاز است:
    uv add zeep   # یا: pip install "django-iranian-payment[soap]"
"""

from datetime import datetime

from django_iranian_payment.core.base import BaseGateway
from django_iranian_payment.core.exceptions import (
    GatewayConfigurationError,
    GatewayConnectionError,
    GatewayPaymentError,
)
from django_iranian_payment.core.models import (
    InitiateResult,
    PaymentRequest,
    PaymentResult,
    PaymentStatus,
)

_WSDL_LIVE = "https://bpm.shaparak.ir/pgwchannel/services/pgw?wsdl"
_WSDL_SANDBOX = "https://pgw.dev.bpmellat.ir/pgwchannel/services/pgw?wsdl"
_STARTPAY_LIVE = "https://bpm.shaparak.ir/pgwchannel/startpay.mellat"
_STARTPAY_SANDBOX = "https://pgw.dev.bpmellat.ir/pgwchannel/startpay.mellat"

# کدهای موفقیت در توابع مختلف (طبق جدول ۱۱)
_RES_OK = "0"
_RES_ALREADY_VERIFIED = "43"  # قبلاً Verify شده
_RES_ALREADY_SETTLED = "45"  # تراکنش Settle شده است
_RES_ALREADY_REVERSED = "48"  # تراکنش Reverse شده است


class MellatGateway(BaseGateway):
    slug = "mellat"
    requires = ("terminal_id", "username", "password")

    @property
    def _wsdl(self):
        return _WSDL_SANDBOX if self.sandbox else _WSDL_LIVE

    @property
    def startpay_url(self):
        return _STARTPAY_SANDBOX if self.sandbox else _STARTPAY_LIVE

    @property
    def _settle_mode(self):
        # پیش‌فرض: verify_settle (تک‌مرحله‌ای، توصیه‌شده)
        mode = self.config.get("settle_mode", "verify_settle")
        if mode not in ("verify_settle", "verify_only"):
            raise GatewayConfigurationError(
                f"درگاه ملت: settle_mode نامعتبر «{mode}». مقادیر مجاز: "
                "verify_settle یا verify_only",
                gateway=self.slug,
            )
        return mode

    def _client(self):
        """کلاینت SOAP. transport قابل تزریق برای تست از طریق self.transport."""
        # اگر transport تزریق‌شده متد soap_call داشته باشد (InMemoryTransport تست)،
        # از همان استفاده می‌کنیم؛ وگرنه zeep واقعی.
        if hasattr(self.transport, "soap_call"):
            return None  # مسیر تست؛ _call مستقیم از transport استفاده می‌کند
        try:
            from zeep import Client
            from zeep.transports import Transport
        except ImportError as e:
            raise GatewayConfigurationError(
                'درگاه ملت به zeep نیاز دارد: pip install "django-iranian-payment[soap]"',
                gateway=self.slug,
            ) from e
        try:
            # timeout روی هم دانلود WSDL و هم فراخوانی متدها اعمال می‌شود تا
            # در نبود دسترسی به سرور، به‌جای ۵ دقیقه انتظار، سریع شکست بخورد.
            transport = Transport(timeout=self.timeout, operation_timeout=self.timeout)
            return Client(self._wsdl, transport=transport)
        except Exception as e:
            raise GatewayConnectionError(
                f"خطای اتصال به WSDL ملت: {e}", gateway=self.slug
            ) from e

    def _call(self, method, **params):
        """
        یک متد SOAP را صدا می‌زند و خروجي رشته‌ای آن را برمی‌گرداند.
        در تست: transport.soap_call(method, params) فراخوانی می‌شود.
        در تولید: zeep client.service.<method>(**params).
        """
        if hasattr(self.transport, "soap_call"):
            return self.transport.soap_call(method, params)
        client = self._client()
        try:
            func = getattr(client.service, method)
            return str(func(**params))
        except Exception as e:
            raise GatewayConnectionError(
                f"خطای فراخوانی {method} ملت: {e}", gateway=self.slug
            ) from e

    def _creds(self):
        return {
            "terminalId": int(self.config["terminal_id"]),
            "userName": self.config["username"],
            "userPassword": self.config["password"],
        }

    # ---------- initiate ----------

    def initiate(self, request: PaymentRequest) -> InitiateResult:
        fee_result = request.resolve_amount()
        amount_to_send = fee_result.amount_to_send

        now = datetime.now()
        params = {
            **self._creds(),
            "orderId": int(request.order_id),
            "amount": amount_to_send,  # ریال، با کارمزد در صورت وجود
            "localDate": now.strftime("%Y%m%d"),
            "localTime": now.strftime("%H%M%S"),
            "additionalData": request.description or "",
            "callBackUrl": request.callback_url,
            "payerId": 0,
        }

        result = self._call("bpPayRequest", **params)
        # خروجی: "ResCode,RefId" — مثلا "0,AF82041a2Bf6989c7fF9"
        parts = str(result).split(",")
        res_code = parts[0].strip()

        if res_code != _RES_OK:
            raise GatewayPaymentError(
                f"ملت درخواست را رد کرد. کد: {res_code}",
                gateway=self.slug,
                code=res_code,
                raw={"raw": result},
            )

        if len(parts) < 2:
            raise GatewayPaymentError(
                "ملت RefId برنگرداند با وجود کد موفق.",
                gateway=self.slug,
                code=res_code,
                raw={"raw": result},
            )

        ref_id = parts[1].strip()
        return InitiateResult(
            # ملت با POST فرم به startpay می‌رود؛ redirect_url صرفاً مقصد فرم است.
            # لایه‌ی Django باید فرم auto-submit با فیلد RefId بسازد.
            redirect_url=f"{self.startpay_url}?RefId={ref_id}",
            authority=ref_id,
            amount_to_send=amount_to_send,
            fee=fee_result.fee,
            raw={"raw": result, "startpay_url": self.startpay_url, "ref_id": ref_id},
        )

    # ---------- verify (دومرحله‌ای یا تک‌مرحله‌ای) ----------

    def _resolve_sale_ids(self, authority, order_id, extra):
        """
        saleReferenceId و saleOrderId را از extra استخراج می‌کند.
        ملت در callbackِ POST این‌ها را برمی‌گرداند؛ کاربر باید در extra بدهد.
        """
        extra = extra or {}
        sale_reference_id = extra.get("sale_reference_id") or extra.get(
            "SaleReferenceId"
        )
        # saleOrderId اگر داده نشود، طبق مستند می‌توان با orderId یکسان گرفت
        sale_order_id = (
            extra.get("sale_order_id") or extra.get("SaleOrderId") or order_id
        )
        if not sale_reference_id:
            raise GatewayPaymentError(
                "درگاه ملت برای verify به sale_reference_id نیاز دارد "
                "(از callbackِ POST بانک می‌آید). آن را در extra بده: "
                "verify(..., extra={'sale_reference_id': ...}).",
                gateway=self.slug,
                code="missing_sale_reference_id",
            )
        return int(sale_reference_id), int(sale_order_id)

    def verify(
        self, *, authority: str, amount: int, order_id: str, extra: dict = None
    ) -> PaymentResult:
        sale_reference_id, sale_order_id = self._resolve_sale_ids(
            authority, order_id, extra
        )
        method = (
            "bpVerifySettleRequest"
            if self._settle_mode == "verify_settle"
            else "bpVerifyRequest"
        )
        res_code = self._call(
            method,
            **self._creds(),
            orderId=int(order_id),
            saleOrderId=sale_order_id,
            saleReferenceId=sale_reference_id,
        ).strip()

        # موفق: 0 (تازه)، 43 (قبلاً verify)، 45 (قبلاً settle)
        success_codes = (_RES_OK, _RES_ALREADY_VERIFIED, _RES_ALREADY_SETTLED)
        if res_code in success_codes:
            status = (
                PaymentStatus.DUPLICATE
                if res_code in (_RES_ALREADY_VERIFIED, _RES_ALREADY_SETTLED)
                else PaymentStatus.SUCCESS
            )
            return PaymentResult(
                status=status,
                gateway_slug=self.slug,
                order_id=order_id,
                reference_id=str(sale_reference_id),
                amount=amount,
                raw={"res_code": res_code, "settle_mode": self._settle_mode},
            )

        return PaymentResult(
            status=PaymentStatus.FAILED,
            gateway_slug=self.slug,
            order_id=order_id,
            error_code=res_code,
            error_message=f"verify ملت ناموفق (کد {res_code})",
            raw={"res_code": res_code},
        )

    # ---------- settle (فقط برای verify_only) ----------

    def settle(self, *, order_id, sale_order_id, sale_reference_id) -> PaymentResult:
        """
        واریز نهایی برای حالت verify_only. در حالت verify_settle لازم نیست.
        ⚠️ اگر verify_only را انتخاب کردی و این را صدا نزنی، پول واریز نمی‌شود
        و در ۳ ساعت بانک Autoreversal می‌زند.
        """
        res_code = self._call(
            "bpSettleRequest",
            **self._creds(),
            orderId=int(order_id),
            saleOrderId=int(sale_order_id),
            saleReferenceId=int(sale_reference_id),
        ).strip()

        if res_code in (_RES_OK, _RES_ALREADY_SETTLED):
            return PaymentResult(
                status=(
                    PaymentStatus.DUPLICATE
                    if res_code == _RES_ALREADY_SETTLED
                    else PaymentStatus.SUCCESS
                ),
                gateway_slug=self.slug,
                order_id=order_id,
                reference_id=str(sale_reference_id),
                raw={"res_code": res_code},
            )
        return PaymentResult(
            status=PaymentStatus.FAILED,
            gateway_slug=self.slug,
            order_id=order_id,
            error_code=res_code,
            error_message=f"settle ملت ناموفق (کد {res_code})",
            raw={"res_code": res_code},
        )

    # ---------- reverse (برگشت وجه در شکست/ابهام) ----------

    def reverse(self, *, order_id, sale_order_id, sale_reference_id) -> PaymentResult:
        """
        برگشت وجه. وقتی وضعیت پرداخت روشن نیست (timeout در verify) یا پذیرنده
        نمی‌خواهد کالا بدهد. طبق مستند: پس از bpVerifyRequest و حداکثر ۳ ساعت
        پس از Verify. کد 48 یعنی قبلاً reverse شده (idempotent).
        """
        res_code = self._call(
            "bpReversalRequest",
            **self._creds(),
            orderId=int(order_id),
            saleOrderId=int(sale_order_id),
            saleReferenceId=int(sale_reference_id),
        ).strip()

        if res_code in (_RES_OK, _RES_ALREADY_REVERSED):
            return PaymentResult(
                status=(
                    PaymentStatus.DUPLICATE
                    if res_code == _RES_ALREADY_REVERSED
                    else PaymentStatus.CANCELLED
                ),
                gateway_slug=self.slug,
                order_id=order_id,
                reference_id=str(sale_reference_id),
                raw={"res_code": res_code},
            )
        return PaymentResult(
            status=PaymentStatus.FAILED,
            gateway_slug=self.slug,
            order_id=order_id,
            error_code=res_code,
            error_message=f"reverse ملت ناموفق (کد {res_code})",
            raw={"res_code": res_code},
        )

    # ---------- inquiry (استعلام وضعیت) ----------

    def inquiry(self, *, order_id, sale_order_id, sale_reference_id) -> str:
        """
        استعلام وضعیت تراکنش وقتی verify پاسخ نداد. خروجی: کد پاسخ (رشته).
        کاربر بر اساس این کد تصمیم می‌گیرد reverse بزند یا تراکنش را موفق بداند.
        """
        return self._call(
            "bpInquiryRequest",
            **self._creds(),
            orderId=int(order_id),
            saleOrderId=int(sale_order_id),
            saleReferenceId=int(sale_reference_id),
        ).strip()
