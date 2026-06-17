"""
درگاه نکست‌پی (nextpay) — REST/JSON. پیاده‌سازی بر اساس مستندات رسمی
nextpay.org/nx/docs.

⚠️ تجربی: منطق با InMemoryTransport تست شده، ولی با کلید/ترمینال واقعی تست نشده.
تا تست واقعی در registry عمومی قرار نمی‌گیرد. فقط با import صریح:
    from django_iranian_payment.core.experimental.nextpay import NextPayGateway

نکته‌ی حیاتی واحد پول: مبلغ نکست‌پی به‌صورت پیش‌فرض «تومان» است. ولی این پکیج
طبق قرارداد همیشه ریال می‌گیرد (بند ۱). برای جلوگیری از تله‌ی ۱۰برابری، همیشه
currency="IRR" به نکست‌پی می‌فرستیم و amount ریالی را بدون تبدیل پاس می‌دهیم.

روند کامل (طبق مستند):
1. initiate → gateway/token: توکن می‌گیریم. ⚠️ کد موفقیت ساخت توکن code == -1
   است (نه 0 و نه مثبت). trans_id همان توکن است.
2. هدایت: کاربر را به gateway/payment/<trans_id> ریدایرکت می‌کنیم (GET ساده،
   برخلاف ملت/سامان نیازی به فرم POST نیست).
3. بازگشت (callback GET): نکست‌پی trans_id, order_id, amount را با GET برمی‌گرداند.
4. verify → gateway/verify: با api_key, trans_id, amount, currency=IRR.
   code == 0 یعنی موفق. code == -25 یا -49 یعنی تراکنش تکراری → DUPLICATE.
5. refund(): همان endpoint verify با refund_request="yes_money_back" تا ۲۰ دقیقه
   پس از تأیید. code == -90 یعنی عودت موفق.
"""

from ..base import BaseGateway
from ..exceptions import GatewayPaymentError
from ..models import (
    InitiateResult,
    PaymentRequest,
    PaymentResult,
    PaymentStatus,
)

_TOKEN_URL = "https://nextpay.org/nx/gateway/token"
_VERIFY_URL = "https://nextpay.org/nx/gateway/verify"
_PAYMENT_URL = "https://nextpay.org/nx/gateway/payment"  # /<trans_id> اضافه می‌شود

# کدهای پاسخ (پیوست ۱ مستند)
_CODE_VERIFY_OK = 0  # پرداخت تکمیل و موفق
_CODE_TOKEN_OK = -1  # توکن صادر شد، منتظر ارسال به بانک
_CODE_ALREADY_SENT = -25  # تراکنش قبلا انجام و قابل ارسال نیست
_CODE_DUPLICATE = -49  # تراکنش تکراری
_CODE_REFUND_OK = -90  # عودت/لغو موفق

_DUPLICATE_CODES = (_CODE_ALREADY_SENT, _CODE_DUPLICATE)


class NextPayGateway(BaseGateway):
    slug = "nextpay"
    requires = ("api_key",)

    @property
    def _token_url(self):
        return self.config.get("token_url", _TOKEN_URL)

    @property
    def _verify_url(self):
        return self.config.get("verify_url", _VERIFY_URL)

    @property
    def _payment_url(self):
        return self.config.get("payment_url", _PAYMENT_URL)

    @staticmethod
    def _as_int_code(code):
        """code گاهی رشته و گاهی عدد می‌آید؛ ایمن به int تبدیل می‌کنیم."""
        try:
            return int(code)
        except (TypeError, ValueError):
            return None

    # ---------- initiate ----------

    def initiate(self, request: PaymentRequest) -> InitiateResult:
        fee_result = request.resolve_amount()
        amount_to_send = fee_result.amount_to_send

        payload = {
            "api_key": self.config["api_key"],
            "order_id": str(request.order_id),
            "amount": amount_to_send,  # ریال — همراه currency=IRR پایین
            "callback_uri": request.callback_url,
            "currency": "IRR",  # امن: مبلغ را ریالی اعلام می‌کنیم تا تبدیل لازم نباشد
        }
        if request.mobile:
            payload["customer_phone"] = request.mobile
        if request.description:
            payload["payer_desc"] = request.description

        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        result = self._post(self._token_url, json=payload, headers=headers)

        code = self._as_int_code(result.get("code"))
        # ⚠️ موفقیت ساخت توکن code == -1 است (نه 0).
        if code != _CODE_TOKEN_OK:
            raise GatewayPaymentError(
                f"نکست‌پی توکن نداد. کد: {code}",
                gateway=self.slug,
                code=str(code),
                raw=result,
            )

        trans_id = result.get("trans_id")
        if not trans_id:
            raise GatewayPaymentError(
                "نکست‌پی با کد موفق ولی بدون trans_id پاسخ داد.",
                gateway=self.slug,
                code=str(code),
                raw=result,
            )

        return InitiateResult(
            redirect_url=f"{self._payment_url}/{trans_id}",
            authority=trans_id,
            amount_to_send=amount_to_send,
            fee=fee_result.fee,
            raw=result,
        )

    # ---------- verify ----------

    def verify(
        self, *, authority: str, amount: int, order_id: str, extra: dict = None
    ) -> PaymentResult:
        payload = {
            "api_key": self.config["api_key"],
            "trans_id": authority,  # همان trans_id که در initiate برگشت
            "amount": amount,  # همان amount_to_send ریالی
            "currency": "IRR",
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        result = self._post(self._verify_url, json=payload, headers=headers)

        code = self._as_int_code(result.get("code"))

        if code == _CODE_VERIFY_OK:
            return PaymentResult(
                status=PaymentStatus.SUCCESS,
                gateway_slug=self.slug,
                order_id=order_id,
                reference_id=str(result.get("Shaparak_Ref_Id")),
                amount=amount,
                card_number=result.get("card_holder"),
                raw=result,
            )

        if code in _DUPLICATE_CODES:
            return PaymentResult(
                status=PaymentStatus.DUPLICATE,
                gateway_slug=self.slug,
                order_id=order_id,
                reference_id=str(result.get("Shaparak_Ref_Id")),
                amount=amount,
                card_number=result.get("card_holder"),
                raw=result,
            )

        return PaymentResult(
            status=PaymentStatus.FAILED,
            gateway_slug=self.slug,
            order_id=order_id,
            error_code=str(code),
            error_message=f"verify نکست‌پی ناموفق (کد {code})",
            raw=result,
        )

    # ---------- refund (عودت/لغو) ----------

    def refund(
        self, *, authority: str, amount: int, order_id: str = ""
    ) -> PaymentResult:
        """
        عودت یک تراکنش موفق. تا ۲۰ دقیقه پس از تأیید. روی همان endpoint verify
        با refund_request="yes_money_back". کد موفقیت عودت -90 است.
        """
        payload = {
            "api_key": self.config["api_key"],
            "trans_id": authority,
            "amount": amount,
            "currency": "IRR",
            "refund_request": "yes_money_back",
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        result = self._post(self._verify_url, json=payload, headers=headers)

        code = self._as_int_code(result.get("code"))
        if code == _CODE_REFUND_OK:
            return PaymentResult(
                status=PaymentStatus.CANCELLED,
                gateway_slug=self.slug,
                order_id=order_id or str(result.get("order_id")),
                reference_id=str(result.get("Shaparak_Ref_Id")),
                amount=amount,
                raw=result,
            )
        return PaymentResult(
            status=PaymentStatus.FAILED,
            gateway_slug=self.slug,
            order_id=order_id,
            error_code=str(code),
            error_message=f"عودت نکست‌پی ناموفق (کد {code})",
            raw=result,
        )
