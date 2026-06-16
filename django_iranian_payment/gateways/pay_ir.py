"""
درگاه پی‌آی‌آر (Pay.ir) — REST/JSON. برای sandbox مقدار api را "test" بگذار.
پی‌آی‌آر با ریال کار می‌کند. authority همان token است.
"""

from ..base import BaseGateway
from ..exceptions import GatewayPaymentError
from ..models import (
    InitiateResult,
    PaymentRequest,
    PaymentResult,
    PaymentStatus,
)


class PayIrGateway(BaseGateway):
    slug = "pay_ir"
    requires = ("api",)

    _REQUEST = "https://pay.ir/pg/send"
    _VERIFY = "https://pay.ir/pg/verify"
    _STARTPAY = "https://pay.ir/pg"

    def initiate(self, request: PaymentRequest) -> InitiateResult:
        payload = {
            "api": self.config["api"],
            "amount": request.amount,          # ریال
            "redirect": request.callback_url,
            "factorNumber": request.order_id,
            "description": request.description,
        }
        if request.mobile:
            payload["mobile"] = request.mobile

        result = self._post(self._REQUEST, json=payload).json()

        if result.get("status") != 1:
            raise GatewayPaymentError(
                f"پی‌آی‌آر درخواست را رد کرد: {result.get('errorMessage')}",
                gateway=self.slug,
                code=str(result.get("errorCode")),
                raw=result,
            )

        token = result.get("token")
        return InitiateResult(
            redirect_url=f"{self._STARTPAY}/{token}",
            authority=token,
            raw=result,
        )

    def verify(self, *, authority: str, amount: int, order_id: str) -> PaymentResult:
        payload = {"api": self.config["api"], "token": authority}
        result = self._post(self._VERIFY, json=payload).json()

        if result.get("status") == 1:
            return PaymentResult(
                status=PaymentStatus.SUCCESS,
                gateway_slug=self.slug,
                order_id=order_id,
                reference_id=str(result.get("transId")),
                amount=result.get("amount", amount),
                card_number=result.get("cardNumber"),
                raw=result,
            )

        return PaymentResult(
            status=PaymentStatus.FAILED,
            gateway_slug=self.slug,
            order_id=order_id,
            error_code=str(result.get("errorCode")),
            error_message=str(result.get("errorMessage") or "verify ناموفق"),
            raw=result,
        )
