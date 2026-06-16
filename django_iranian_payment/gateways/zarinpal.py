"""
درگاه زرین‌پال — REST/JSON، sandbox واقعی دارد، پس کامل تست‌پذیر است.

این بازنویسی کد اصلی توست، با این تفاوت‌ها:
- بدون state روی کلاس
- amount داخلاً به ریال نگه داشته می‌شود
- خطای شبکه به GatewayConnectionError تبدیل می‌شود
- در sandbox محاسبه‌ی کارمزد رد می‌شود (سرویس feeCalculation در sandbox پایدار نیست)
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
        "startpay": "https://www.zarinpal.com/pg/StartPay",
    }
    _SANDBOX = {
        "request": "https://sandbox.zarinpal.com/pg/v4/payment/request.json",
        "verify": "https://sandbox.zarinpal.com/pg/v4/payment/verify.json",
        "startpay": "https://sandbox.zarinpal.com/pg/StartPay",
    }

    @property
    def _urls(self):
        return self._SANDBOX if self.sandbox else self._LIVE

    def initiate(self, request: PaymentRequest) -> InitiateResult:
        payload = {
            "merchant_id": self.config["merchant_id"],
            "amount": request.amount,          # ریال
            "currency": "IRR",
            "callback_url": request.callback_url,
            "description": request.description or f"پرداخت سفارش {request.order_id}",
        }
        if request.mobile:
            payload.setdefault("metadata", {})["mobile"] = request.mobile
        if request.email:
            payload.setdefault("metadata", {})["email"] = request.email

        headers = {"Content-Type": "application/json"}
        result = self._post(
            self._urls["request"], json=payload, headers=headers
        ).json()

        errors = result.get("errors")
        if errors:
            raise GatewayPaymentError(
                f"زرین‌پال درخواست را رد کرد: {errors}",
                gateway=self.slug,
                code=str(errors.get("code") if isinstance(errors, dict) else errors),
                raw=result,
            )

        data = result.get("data", {})
        authority = data.get("authority")
        return InitiateResult(
            redirect_url=f"{self._urls['startpay']}/{authority}",
            authority=authority,
            raw=result,
        )

    def verify(self, *, authority: str, amount: int, order_id: str) -> PaymentResult:
        payload = {
            "merchant_id": self.config["merchant_id"],
            "amount": amount,                  # ریال — همان مبلغی که در initiate فرستادی
            "authority": authority,
        }
        headers = {"Content-Type": "application/json"}
        result = self._post(
            self._urls["verify"], json=payload, headers=headers
        ).json()

        data = result.get("data", {}) or {}
        code = data.get("code")

        # 100 = موفق، 101 = قبلاً تأیید شده
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
