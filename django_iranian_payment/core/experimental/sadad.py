"""
درگاه پرداخت الکترونیک سداد (sadad) — REST/JSON (WebApi) با امضای 3DES.
پیاده‌سازی بر اساس مستند رسمی «راهنمای پیاده‌سازی فرآیند خرید» ویرایش ۱.۱۰/۱.۱۱.

درگاه ملی به سداد منتقل شده؛ این همان درگاهی است که از سایت بانک ملی به آن
هدایت می‌شوید. (اسکلت melli.py باید به همین SadadGateway اشاره دهد.)

⚠️ تجربی: منطق با InMemoryTransport تست شده، ولی با ترمینال واقعی تست نشده.
تا تست واقعی در registry عمومی قرار نمی‌گیرد. فقط با import صریح:
    from django_iranian_payment.core.experimental.sadad import SadadGateway

رمزنگاری: برخلاف ایران‌کیش (AES+RSA)، سداد از 3DES استفاده می‌کند:
TripleDES(ECB, PKCS7) روی داده، خروجی Base64. کلید پذیرنده خودش Base64 است
(پس از دیکد باید ۱۶ یا ۲۴ بایت باشد).
    - در PaymentRequest: SignData = enc("TerminalId;OrderId;Amount")
    - در Verify: SignData = enc(Token)

روند کامل (طبق مستند):
1. initiate → api/v0/Request/PaymentRequest: توکن می‌گیریم. ResCode == 0 موفق.
2. هدایت: کاربر را به Purchase?Token=<token> ریدایرکت می‌کنیم (GET ساده).
3. بازگشت (callback POST): سداد OrderId, Token, ResCode, و... را POST می‌کند.
4. verify → api/v0/Advice/Verify: با Token و SignData=enc(Token).
   ResCode == 0 موفق؛ ResCode == 100 یعنی «تکراری/قبلاً موفق» → DUPLICATE.
   ⚠️ اگر verify در ۱۵ دقیقه فراخوانی نشود، مبلغ خودکار به مشتری برمی‌گردد.

وابستگی اختیاری:
    uv add pycryptodome
"""

from ..base import BaseGateway
from ..exceptions import (
    GatewayConfigurationError,
    GatewayPaymentError,
)
from ..models import (
    InitiateResult,
    PaymentRequest,
    PaymentResult,
    PaymentStatus,
)

_REQUEST_URL = "https://sadad.shaparak.ir/api/v0/Request/PaymentRequest"
_VERIFY_URL = "https://sadad.shaparak.ir/api/v0/Advice/Verify"
_PURCHASE_URL = "https://sadad.shaparak.ir/Purchase"  # ?Token=<token>

# کدهای ResCode (پیوست مستند)
_RC_OK = 0  # موفق (در هر سه جدول)
_RC_VERIFY_DUPLICATE = 100  # verify: درخواست تکراری، قبلا موفق ثبت شده


class SadadGateway(BaseGateway):
    slug = "sadad"
    requires = ("merchant_id", "terminal_id", "terminal_key")

    @property
    def _request_url(self):
        return self.config.get("request_url", _REQUEST_URL)

    @property
    def _verify_url(self):
        return self.config.get("verify_url", _VERIFY_URL)

    @property
    def _purchase_url(self):
        return self.config.get("purchase_url", _PURCHASE_URL)

    # ---------- رمزنگاری 3DES ----------

    def _sign(self, data: str) -> str:
        """
        داده را با TripleDES(ECB, PKCS7) و کلید پذیرنده (Base64) رمز و Base64 می‌کند.
        کلید terminal_key خودش Base64 است؛ پس از دیکد باید ۱۶ یا ۲۴ بایت باشد.
        """
        import base64

        try:
            from Crypto.Cipher import DES3
            from Crypto.Util.Padding import pad
        except ImportError as e:
            raise GatewayConfigurationError(
                "درگاه سداد به pycryptodome نیاز دارد: uv add pycryptodome",
                gateway=self.slug,
            ) from e

        try:
            key = base64.b64decode(self.config["terminal_key"])
        except Exception as e:
            raise GatewayConfigurationError(
                "terminal_key سداد باید Base64 معتبر باشد.",
                gateway=self.slug,
            ) from e

        if len(key) not in (16, 24):
            raise GatewayConfigurationError(
                f"کلید سداد پس از دیکد Base64 باید ۱۶ یا ۲۴ بایت باشد "
                f"(الان {len(key)} بایت).",
                gateway=self.slug,
            )

        cipher = DES3.new(key, DES3.MODE_ECB)
        encrypted = cipher.encrypt(pad(data.encode(), 8))  # بلاک 3DES = ۸ بایت
        return base64.b64encode(encrypted).decode()

    # ---------- initiate ----------

    def initiate(self, request: PaymentRequest) -> InitiateResult:
        from datetime import datetime

        fee_result = request.resolve_amount()
        amount_to_send = fee_result.amount_to_send

        terminal_id = str(self.config["terminal_id"])
        order_id = str(request.order_id)
        # SignData = enc("TerminalId;OrderId;Amount")
        sign_data = self._sign(f"{terminal_id};{order_id};{amount_to_send}")

        payload = {
            "MerchantId": str(self.config["merchant_id"]),
            "TerminalId": terminal_id,
            "Amount": amount_to_send,  # ریال
            "OrderId": int(order_id),
            "LocalDateTime": datetime.now().strftime("%m/%d/%Y %H:%M:%S"),
            "ReturnUrl": request.callback_url,
            "SignData": sign_data,
        }
        if request.description:
            payload["AdditionalData"] = request.description
        if request.mobile:
            payload["UserId"] = request.mobile

        headers = {"Content-Type": "application/json"}
        result = self._post(self._request_url, json=payload, headers=headers)

        res_code = result.get("ResCode")
        if res_code != _RC_OK:
            raise GatewayPaymentError(
                f"سداد درخواست را رد کرد. کد: {res_code} — "
                f"{result.get('Description')}",
                gateway=self.slug,
                code=str(res_code),
                raw=result,
            )

        token = result.get("Token")
        if not token:
            raise GatewayPaymentError(
                "سداد با کد موفق ولی بدون Token پاسخ داد.",
                gateway=self.slug,
                code=str(res_code),
                raw=result,
            )

        return InitiateResult(
            redirect_url=f"{self._purchase_url}?Token={token}",
            authority=token,
            amount_to_send=amount_to_send,
            fee=fee_result.fee,
            raw=result,
        )

    # ---------- verify ----------

    def verify(
        self, *, authority: str, amount: int, order_id: str, extra: dict = None
    ) -> PaymentResult:
        extra = extra or {}

        # اگر ResCode در callback آمد و موفق نبود، verify نزن.
        cb_code = extra.get("res_code") or extra.get("ResCode")
        if cb_code is not None and str(cb_code) != str(_RC_OK):
            return PaymentResult(
                status=PaymentStatus.FAILED,
                gateway_slug=self.slug,
                order_id=order_id,
                error_code=str(cb_code),
                error_message=f"تراکنش سداد در callback ناموفق بود (ResCode={cb_code})",
                raw={"res_code": cb_code},
            )

        # SignData = enc(Token)
        sign_data = self._sign(authority)
        payload = {"Token": authority, "SignData": sign_data}
        headers = {"Content-Type": "application/json"}
        result = self._post(self._verify_url, json=payload, headers=headers)

        res_code = result.get("ResCode")

        if res_code == _RC_OK or res_code == _RC_VERIFY_DUPLICATE:
            status = (
                PaymentStatus.DUPLICATE
                if res_code == _RC_VERIFY_DUPLICATE
                else PaymentStatus.SUCCESS
            )
            return PaymentResult(
                status=status,
                gateway_slug=self.slug,
                order_id=str(result.get("OrderId") or order_id),
                reference_id=str(result.get("RetrivalRefNo")),
                amount=result.get("Amount") or amount,
                raw=result,  # CardHolderFullName و SystemTraceNo اینجا در raw هستند
            )

        return PaymentResult(
            status=PaymentStatus.FAILED,
            gateway_slug=self.slug,
            order_id=order_id,
            error_code=str(res_code),
            error_message=str(result.get("Description") or "verify ناموفق"),
            raw=result,
        )