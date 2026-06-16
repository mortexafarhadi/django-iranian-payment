"""
درگاه زیبال — REST/JSON. برای sandbox مقدار merchant را "zibal" بگذار.
زیبال با ریال کار می‌کند.
"""

from ..base import BaseGateway
from ..exceptions import GatewayPaymentError
from ..models import (
    InitiateResult,
    PaymentRequest,
    PaymentResult,
    PaymentStatus,
)


class ZibalGateway(BaseGateway):
    slug = "zibal"
    requires = ("merchant",)

    _REQUEST = "https://gateway.zibal.ir/v1/request"
    _VERIFY = "https://gateway.zibal.ir/v1/verify"
    _STARTPAY = "https://gateway.zibal.ir/start"

    def initiate(self, request: PaymentRequest) -> InitiateResult:
        payload = {
            "merchant": self.config["merchant"],
            "amount": request.amount,          # ریال
            "callbackUrl": request.callback_url,
            "orderId": request.order_id,
            "description": request.description,
        }
        if request.mobile:
            payload["mobile"] = request.mobile

        result = self._post(self._REQUEST, json=payload).json()

        if result.get("result") != 100:
            raise GatewayPaymentError(
                f"زیبال درخواست را رد کرد: {result.get('message')}",
                gateway=self.slug,
                code=str(result.get("result")),
                raw=result,
            )

        track_id = result.get("trackId")
        return InitiateResult(
            redirect_url=f"{self._STARTPAY}/{track_id}",
            authority=str(track_id),
            raw=result,
        )

    def verify(self, *, authority: str, amount: int, order_id: str) -> PaymentResult:
        payload = {
            "merchant": self.config["merchant"],
            "trackId": int(authority),
        }
        result = self._post(self._VERIFY, json=payload).json()
        code = result.get("result")

        if code == 100:
            return PaymentResult(
                status=PaymentStatus.SUCCESS,
                gateway_slug=self.slug,
                order_id=order_id,
                reference_id=str(result.get("refNumber")),
                amount=result.get("amount", amount),
                card_number=result.get("cardNumber"),
                raw=result,
            )
        if code == 201:  # قبلاً تأیید شده
            return PaymentResult(
                status=PaymentStatus.DUPLICATE,
                gateway_slug=self.slug,
                order_id=order_id,
                reference_id=str(result.get("refNumber")),
                amount=result.get("amount", amount),
                raw=result,
            )

        return PaymentResult(
            status=PaymentStatus.FAILED,
            gateway_slug=self.slug,
            order_id=order_id,
            error_code=str(code),
            error_message=str(result.get("message") or "verify ناموفق"),
            raw=result,
        )
