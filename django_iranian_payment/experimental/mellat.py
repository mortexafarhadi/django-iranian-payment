"""
درگاه ملت (به‌پرداخت ملت) — SOAP — تجربی و تست‌نشده.

⚠️ این کد بدون ترمینال واقعی بانکی تست نشده است. در registry عمومی نیست.
فقط با import صریح در دسترس است:
    from django_iranian_payment.experimental import MellatGateway

برای SOAP به کتابخانه‌ی zeep نیاز است:
    pip install zeep

ساختار طبق مستندات ملت بازنویسی شده، ولی مقادیر برگشتی و کدهای خطا
باید پس از تست با ترمینال واقعی تأیید شوند.
"""

from ..base import BaseGateway
from ..exceptions import GatewayConfigurationError, GatewayPaymentError
from ..models import (
    InitiateResult,
    PaymentRequest,
    PaymentResult,
    PaymentStatus,
)

_WSDL = "https://bpm.shaparak.ir/pgwchannel/services/pgw?wsdl"
_STARTPAY = "https://bpm.shaparak.ir/pgwchannel/startpay.mellat"


class MellatGateway(BaseGateway):
    slug = "mellat"
    requires = ("terminal_id", "username", "password")

    def _client(self):
        try:
            from zeep import Client
        except ImportError as e:
            raise GatewayConfigurationError(
                "درگاه ملت به zeep نیاز دارد: pip install zeep",
                gateway=self.slug,
            ) from e
        return Client(_WSDL)

    def initiate(self, request: PaymentRequest) -> InitiateResult:
        # توجه: ملت مبلغ را به ریال می‌گیرد و order_id باید عددی باشد.
        client = self._client()
        result = client.service.bpPayRequest(
            terminalId=int(self.config["terminal_id"]),
            userName=self.config["username"],
            userPassword=self.config["password"],
            orderId=int(request.order_id),
            amount=request.amount,             # ریال
            localDate="",   # TODO: قالب YYYYMMDD هنگام تست پر شود
            localTime="",   # TODO: قالب HHMMSS هنگام تست پر شود
            additionalData=request.description,
            callBackUrl=request.callback_url,
            payerId=0,
        )
        # خروجی به شکل "ResCode,RefId" است
        parts = str(result).split(",")
        if parts[0] != "0":
            raise GatewayPaymentError(
                f"ملت درخواست را رد کرد. کد: {parts[0]}",
                gateway=self.slug,
                code=parts[0],
                raw={"raw": result},
            )
        ref_id = parts[1]
        # ⚠️ ملت با POST به startpay می‌رود (فرم auto-submit)، نه redirect ساده.
        # این بخش هنگام تست واقعی باید با فرم HTML تکمیل شود.
        return InitiateResult(
            redirect_url=f"{_STARTPAY}?RefId={ref_id}",
            authority=ref_id,
            raw={"raw": result},
        )

    def verify(self, *, authority: str, amount: int, order_id: str) -> PaymentResult:
        # ملت verify دومرحله‌ای دارد: bpVerifyRequest سپس bpSettleRequest
        # این منطق باید پس از تست با ترمینال واقعی نهایی شود.
        raise NotImplementedError(
            "verify ملت هنوز با ترمینال واقعی تست و نهایی نشده است."
        )
