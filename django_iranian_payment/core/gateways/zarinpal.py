"""
درگاه زرین‌پال — REST/JSON، sandbox واقعی دارد.

اصلاح‌ها نسبت به نسخه‌ی قبل:
- startpay در حالت live روی همان دامنه‌ی payment.zarinpal.com است (نه www).
- استخراج code از errors هم برای dict و هم برای list ایمن شد.
- initiate حالا کارمزد را اعمال می‌کند: amount_to_send به بانک می‌رود و در
  خروجی برمی‌گردد تا در verify همان عدد استفاده شود.
"""

from ..base import BaseGateway
from ..exceptions import GatewayPaymentError
from ..models import (
    InitiateResult,
    PaymentRequest,
    PaymentResult,
    PaymentStatus,
)


class ZarinpalGateway(BaseGateway):
    slug = "zarinpal"
    requires = ("merchant_id",)

    _LIVE = {
        "request": "https://payment.zarinpal.com/pg/v4/payment/request.json",
        "verify": "https://payment.zarinpal.com/pg/v4/payment/verify.json",
        "startpay": "https://payment.zarinpal.com/pg/StartPay",
    }
    _SANDBOX = {
        "request": "https://sandbox.zarinpal.com/pg/v4/payment/request.json",
        "verify": "https://sandbox.zarinpal.com/pg/v4/payment/verify.json",
        "startpay": "https://sandbox.zarinpal.com/pg/StartPay",
    }

    @property
    def _urls(self):
        return self._SANDBOX if self.sandbox else self._LIVE

    @staticmethod
    def _extract_error_code(errors):
        """code را از errors بیرون می‌کشد، چه dict باشد چه list چه چیز دیگر."""
        if isinstance(errors, dict):
            return str(errors.get("code"))
        if isinstance(errors, list) and errors:
            first = errors[0]
            if isinstance(first, dict):
                return str(first.get("code"))
            return str(first)
        return str(errors)

    def initiate(self, request: PaymentRequest) -> InitiateResult:
        fee_result = request.resolve_amount()
        amount_to_send = fee_result.amount_to_send

        payload = {
            "merchant_id": self.config["merchant_id"],
            "amount": amount_to_send,  # ریال، با کارمزد در صورت وجود
            "currency": "IRR",
            "callback_url": request.callback_url,
            "description": request.description or f"پرداخت سفارش {request.order_id}",
        }
        if request.mobile:
            payload.setdefault("metadata", {})["mobile"] = request.mobile
        if request.email:
            payload.setdefault("metadata", {})["email"] = request.email

        headers = {"Content-Type": "application/json"}
        result = self._post(self._urls["request"], json=payload, headers=headers)

        errors = result.get("errors")
        if errors:
            raise GatewayPaymentError(
                f"زرین‌پال درخواست را رد کرد: {errors}",
                gateway=self.slug,
                code=self._extract_error_code(errors),
                raw=result,
            )

        data = result.get("data", {}) or {}
        authority = data.get("authority")
        return InitiateResult(
            redirect_url=f"{self._urls['startpay']}/{authority}",
            authority=authority,
            amount_to_send=amount_to_send,
            fee=fee_result.fee,
            raw=result,
        )

    def verify(self, *, authority: str, amount: int, order_id: str, extra: dict = None) -> PaymentResult:
        payload = {
            "merchant_id": self.config["merchant_id"],
            "amount": amount,  # همان amount_to_send که در initiate رفت
            "authority": authority,
        }
        headers = {"Content-Type": "application/json"}
        result = self._post(self._urls["verify"], json=payload, headers=headers)

        data = result.get("data", {}) or {}
        code = data.get("code")

        if code == 100:
            return PaymentResult(
                status=PaymentStatus.SUCCESS,
                gateway_slug=self.slug,
                order_id=order_id,
                reference_id=str(data.get("ref_id")),
                amount=amount,
                card_number=data.get("card_pan"),
                raw=result,
            )
        if code == 101:
            return PaymentResult(
                status=PaymentStatus.DUPLICATE,
                gateway_slug=self.slug,
                order_id=order_id,
                reference_id=str(data.get("ref_id")),
                amount=amount,
                raw=result,
            )

        return PaymentResult(
            status=PaymentStatus.FAILED,
            gateway_slug=self.slug,
            order_id=order_id,
            error_code=str(code),
            error_message=str(result.get("errors") or "verify ناموفق"),
            raw=result,
        )