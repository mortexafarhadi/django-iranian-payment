"""
درگاه آیدی‌پی — REST/JSON. sandbox با هدر X-SANDBOX:1 فعال می‌شود.
آیدی‌پی با ریال کار می‌کند و callback آن POST است.
authority اینجا همان id تراکنش است.
"""

from ..base import BaseGateway
from ..exceptions import GatewayPaymentError
from ..models import (
    InitiateResult,
    PaymentRequest,
    PaymentResult,
    PaymentStatus,
)


class IDPayGateway(BaseGateway):
    slug = "idpay"
    requires = ("api_key",)

    _REQUEST = "https://api.idpay.ir/v1.1/payment"
    _VERIFY = "https://api.idpay.ir/v1.1/payment/verify"

    def _headers(self):
        headers = {
            "Content-Type": "application/json",
            "X-API-KEY": self.config["api_key"],
        }
        if self.sandbox:
            headers["X-SANDBOX"] = "1"
        return headers

    def initiate(self, request: PaymentRequest) -> InitiateResult:
        payload = {
            "order_id": request.order_id,
            "amount": request.amount,          # ریال
            "callback": request.callback_url,
            "desc": request.description,
        }
        if request.mobile:
            payload["phone"] = request.mobile
        if request.email:
            payload["mail"] = request.email

        result = self._post(
            self._REQUEST, json=payload, headers=self._headers()
        ).json()

        if "error_code" in result:
            raise GatewayPaymentError(
                f"آیدی‌پی درخواست را رد کرد: {result.get('error_message')}",
                gateway=self.slug,
                code=str(result.get("error_code")),
                raw=result,
            )

        return InitiateResult(
            redirect_url=result.get("link"),
            authority=result.get("id"),
            raw=result,
        )

    def verify(self, *, authority: str, amount: int, order_id: str) -> PaymentResult:
        payload = {"id": authority, "order_id": order_id}
        result = self._post(
            self._VERIFY, json=payload, headers=self._headers()
        ).json()

        # status 100 = پرداخت تأییدشده در آیدی‌پی
        status = result.get("status")
        if status in (100, 101):
            return PaymentResult(
                status=PaymentStatus.SUCCESS if status == 100 else PaymentStatus.DUPLICATE,
                gateway_slug=self.slug,
                order_id=order_id,
                reference_id=str(result.get("track_id")),
                amount=result.get("amount", amount),
                card_number=(result.get("payment") or {}).get("card_no"),
                raw=result,
            )

        return PaymentResult(
            status=PaymentStatus.FAILED,
            gateway_slug=self.slug,
            order_id=order_id,
            error_code=str(status or result.get("error_code")),
            error_message=str(result.get("error_message") or "verify ناموفق"),
            raw=result,
        )
