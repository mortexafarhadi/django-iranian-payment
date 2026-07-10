"""
درگاه پرداخت الکترونیک سامان (SEP) — REST/JSON. پیاده‌سازی بر اساس مستند فنی
رسمی نگارش ۳.۶ (دی ۱۴۰۴).

⚠️ تجربی: کد کامل از مستند است و منطق با InMemoryTransport تست شده، ولی با
ترمینال واقعی تست نشده. تا تست واقعی در registry عمومی قرار نمی‌گیرد. فقط با
import صریح:
    from django_iranian_payment.core.experimental.saman import SamanGateway

پیش‌نیاز تست واقعی: ثبت IP سرور پذیرنده نزد سامان (وگرنه کد 8
MerchantIpAddressIsInvalid در زمان دریافت توکن).

روند کامل (طبق مستند):
1. initiate → action=token: یک توکن می‌گیریم. خروجی موفق {"status":1,"token":...}.
   هدایت به صفحه‌ی پرداخت طبق روش ۲٫۱ مستند: یک فرم auto-submit با متد POST و
   فیلد مخفی `Token` به آدرس درگاه کلاسیک `OnlinePG/OnlinePG` ارسال می‌شود
   (لایه‌ی Django این فرم را می‌سازد؛ redirect_method="POST" و
   redirect_fields={"Token": token}). چرا فرم POST نه redirect GET؟ مستند
   (صفحه ۱۰) صریح است: هدایت حتماً باید از طریق فرم/لینکِ سایت پذیرنده باشد تا
   مرورگر هدر Referrer را بفرستد، وگرنه «امکان ورود به درگاه پرداخت وجود نخواهد
   داشت». یک redirect 302 سمت‌سرور این Referrer را مطمئن نمی‌فرستد.
2. بازگشت از بانک (callback POST): سامان State/Status/RefNum/ResNum/RRN/... را
   POST می‌کند. RefNum و State برای verify لازم‌اند (در extra پاس داده می‌شوند).
3. verify → VerifyTransaction با RefNum و TerminalNumber.
   ⚠️ سامان در برابر double-spending مسئولیتی نمی‌پذیرد: یک RefNum را بارها
   verify می‌کند. یکتایی RefNum مسئولیت ماست (لایه‌ی Django با state machine).
   کد ResultCode=2 یعنی «درخواست تکراری» (verify دوم) → DUPLICATE نگاشت می‌شود.
4. reverse → ReverseTransaction: تا ۵۰ دقیقه پس از تراکنش، برگشت وجه.

نکات مستند که رعایت شده:
- مبلغ ریال است، عدد صحیح بدون اعشار.
- نام پارامترها case-sensitive است (نکته ۴ مستند).
- بازگشت موفق verify: Success=true و ResultCode=0 و OrginalAmount باید با
  مبلغ ارسالی اولیه تطبیق داشته باشد (نکته ۲ مستند). تطبیق مبلغ اینجا انجام
  می‌شود؛ عدم تطبیق → FAILED با کد amount_mismatch.

⚠️ neo-pg / بلوپی (BluPay): اگر ترمینالِ پذیرنده neo-pg فعال داشته باشد، سامان
هدر X-IPG-Url (مثل https://neo-pg.sep.ir/transaction/init) را در پاسخ توکن
می‌فرستد و انتظار دارد توکن به همان آدرس POST شود — که آن‌جا یک مودال انتخاب
«درگاه اینترنتی / بلوپی» نمایش می‌دهد. این پیاده‌سازی **عمداً X-IPG-Url را
نادیده می‌گیرد** و همیشه به درگاه کلاسیک (`OnlinePG/OnlinePG`، ورود مستقیم کارت،
بدون مودال) POST می‌کند — رفتاری که کاربر خواسته و اکثر سایت‌ها دارند. اگر
ترمینالی اجباراً به neo-pg مسیردهی شده باشد و درگاه کلاسیک توکن را نپذیرد
(TokenNotFound)، باید از واحد کسب‌وکار نوین سامان خواست بلوپی را روی ترمینال
غیرفعال کنند.
"""

from ..base import BaseGateway
from ..exceptions import GatewayPaymentError
from ..models import (
    InitiateResult,
    PaymentRequest,
    PaymentResult,
    PaymentStatus,
)

# آدرس درگاه کلاسیک: هم endpointِ درخواست توکن است، هم action فرمِ هدایت (POST).
_TOKEN_URL = "https://sep.shaparak.ir/OnlinePG/OnlinePG"
_VERIFY_URL = "https://sep.shaparak.ir/verifyTxnRandomSessionkey/ipg/VerifyTransaction"
_REVERSE_URL = (
    "https://sep.shaparak.ir/verifyTxnRandomSessionkey/ipg/ReverseTransaction"
)

# کدهای State در callback (جدول وضعیت تراکنش، صفحه ۱۴)
_STATE_OK = "OK"

# کدهای ResultCode سرویس verify/reverse (صفحه ۱۹)
_RC_SUCCESS = 0
_RC_DUPLICATE = 2  # درخواست تکراری (verify دوم روی همان RefNum)


class SamanGateway(BaseGateway):
    slug = "saman"
    requires = ("terminal_id",)

    @property
    def _token_url(self):
        # هم endpointِ درخواست توکن است، هم action فرمِ هدایت POST (درگاه کلاسیک).
        return self.config.get("token_url", _TOKEN_URL)

    @property
    def _verify_url(self):
        return self.config.get("verify_url", _VERIFY_URL)

    @property
    def _reverse_url(self):
        return self.config.get("reverse_url", _REVERSE_URL)

    # ---------- initiate ----------

    def initiate(self, request: PaymentRequest) -> InitiateResult:
        fee_result = request.resolve_amount()
        amount_to_send = fee_result.amount_to_send

        payload = {
            "action": "token",
            "TerminalId": str(self.config["terminal_id"]),
            "Amount": amount_to_send,  # ریال، با کارمزد در صورت وجود
            "ResNum": str(request.order_id),  # شماره‌ی خرید یکتای سمت ما
            "RedirectUrl": request.callback_url,
        }
        if request.mobile:
            payload["CellNumber"] = request.mobile
        token_expiry = self.config.get("token_expiry_min")
        if token_expiry:
            payload["TokenExpiryInMin"] = int(token_expiry)

        headers = {"Content-Type": "application/json"}
        result = self._post(self._token_url, json=payload, headers=headers)

        status = result.get("status")
        if status != 1:
            raise GatewayPaymentError(
                f"سامان توکن نداد. کد: {result.get('errorCode')} — "
                f"{result.get('errorDesc')}",
                gateway=self.slug,
                code=str(result.get("errorCode")),
                raw=result,
            )

        token = result.get("token")
        # هدایت طبق روش ۲٫۱ مستند: فرم auto-submit با متد POST و فیلد `Token` به
        # آدرس درگاه کلاسیک. این تنها روشی است که Referrer را می‌فرستد (الزام
        # مستند) و مودال neo-pg/بلوپی را دور می‌زند. X-IPG-Url عمداً خوانده نمی‌شود.
        return InitiateResult(
            redirect_url=self._token_url,
            redirect_method="POST",
            redirect_fields={"Token": token},
            authority=token,
            amount_to_send=amount_to_send,
            fee=fee_result.fee,
            raw={
                "result": result,
                "token": token,
                "post_to": self._token_url,
            },
        )

    # ---------- verify ----------

    def _resolve_ref_num(self, authority, extra):
        """
        RefNum (رسید دیجیتالی) را از extra یا authority می‌گیرد.
        سامان در callbackِ POST مقدار RefNum را برمی‌گرداند؛ verify با آن انجام
        می‌شود نه با توکن. اگر در extra نبود، authority استفاده می‌شود (سازگاری).
        """
        extra = extra or {}
        ref_num = extra.get("ref_num") or extra.get("RefNum") or extra.get("refnum")
        if not ref_num:
            raise GatewayPaymentError(
                "درگاه سامان برای verify به RefNum (رسید دیجیتالی) نیاز دارد "
                "(از callbackِ POST بانک می‌آید). آن را در extra بده: "
                "verify(..., extra={'ref_num': ...}).",
                gateway=self.slug,
                code="missing_ref_num",
            )
        return str(ref_num)

    def verify(
        self, *, authority: str, amount: int, order_id: str, extra: dict = None
    ) -> PaymentResult:
        extra = extra or {}

        # اگر State در callback آمد و OK نبود، حتی verify نزن — تراکنش ناموفق.
        state = extra.get("state") or extra.get("State")
        if state is not None and str(state).upper() != _STATE_OK:
            return PaymentResult(
                status=PaymentStatus.FAILED,
                gateway_slug=self.slug,
                order_id=order_id,
                error_code=str(state),
                error_message=f"وضعیت تراکنش سامان OK نبود: {state}",
                raw={"state": state},
            )

        ref_num = self._resolve_ref_num(authority, extra)

        payload = {
            "RefNum": ref_num,
            "TerminalNumber": int(self.config["terminal_id"]),
        }
        headers = {"Content-Type": "application/json"}
        result = self._post(self._verify_url, json=payload, headers=headers)

        result_code = result.get("ResultCode")
        success = result.get("Success")
        detail = result.get("TransactionDetail") or {}

        is_ok = success is True and result_code in (_RC_SUCCESS, _RC_DUPLICATE)
        if not is_ok:
            return PaymentResult(
                status=PaymentStatus.FAILED,
                gateway_slug=self.slug,
                order_id=order_id,
                error_code=str(result_code),
                error_message=str(result.get("ResultDescription") or "verify ناموفق"),
                raw=result,
            )

        # تطبیق مبلغ (نکته ۲ مستند): OrginalAmount باید با مبلغ ارسالی برابر باشد.
        original_amount = detail.get("OrginalAmount")
        if original_amount is not None and int(original_amount) != int(amount):
            return PaymentResult(
                status=PaymentStatus.FAILED,
                gateway_slug=self.slug,
                order_id=order_id,
                reference_id=str(detail.get("RRN")),
                amount=int(original_amount),
                error_code="amount_mismatch",
                error_message=(
                    f"مبلغ تأییدشده ({original_amount}) با مبلغ ارسالی ({amount}) "
                    "یکی نیست — تراکنش نباید پذیرفته شود."
                ),
                raw=result,
            )

        status = (
            PaymentStatus.DUPLICATE
            if result_code == _RC_DUPLICATE
            else PaymentStatus.SUCCESS
        )
        return PaymentResult(
            status=status,
            gateway_slug=self.slug,
            order_id=order_id,
            reference_id=str(detail.get("RRN") or ref_num),
            amount=amount,
            card_number=detail.get("MaskedPan"),
            raw=result,
        )

    # ---------- reverse (برگشت وجه) ----------

    def reverse(self, *, ref_num: str) -> PaymentResult:
        """
        برگشت وجه. تا ۵۰ دقیقه پس از تراکنش، فقط در صورتی که قبلاً verify شده باشد.
        """
        payload = {
            "RefNum": str(ref_num),
            "TerminalNumber": int(self.config["terminal_id"]),
        }
        headers = {"Content-Type": "application/json"}
        result = self._post(self._reverse_url, json=payload, headers=headers)

        result_code = result.get("ResultCode")
        success = result.get("Success")
        detail = result.get("TransactionDetail") or {}

        if success is True and result_code in (_RC_SUCCESS, _RC_DUPLICATE):
            return PaymentResult(
                status=PaymentStatus.CANCELLED,
                gateway_slug=self.slug,
                order_id=str(detail.get("RefNum") or ref_num),
                reference_id=str(detail.get("RRN") or ref_num),
                raw=result,
            )
        return PaymentResult(
            status=PaymentStatus.FAILED,
            gateway_slug=self.slug,
            order_id=str(ref_num),
            error_code=str(result_code),
            error_message=str(result.get("ResultDescription") or "reverse ناموفق"),
            raw=result,
        )
