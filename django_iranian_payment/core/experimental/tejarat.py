"""
درگاه تجارت (مبنا) (tejarat) — تجربی و تست‌نشده.

⚠️ این اسکلت بدون اطلاعات/ترمینال واقعی نوشته شده و با هیچ تراکنشی تست نشده.
در registry عمومی نیست. فقط با import صریح:
    from django_iranian_payment.core.experimental import TejaratGateway

نکات این درگاه: callback از نوع POST.

پیش از استفاده، هر TODO را با مستندات رسمی همین بانک پر و سپس تست کن.
"""

from ..base import BaseGateway
from ..exceptions import GatewayPaymentError
from ..models import (
    InitiateResult,
    PaymentRequest,
    PaymentResult,
    PaymentStatus,
)


class TejaratGateway(BaseGateway):
    slug = "tejarat"
    requires = ("terminal_id",)

    # TODO: آدرس‌های واقعی request/verify/startpay را از مستندات بگذار
    _REQUEST_URL = ""  # TODO
    _VERIFY_URL = ""  # TODO
    _STARTPAY_URL = ""  # TODO

    def initiate(self, request: PaymentRequest) -> InitiateResult:
        # TODO: payload را طبق مستندات تجارت (مبنا) بساز. مبلغ ریال است؛ کارمزد را با
        #       request.resolve_amount().amount_to_send بگیر، نه request.amount.
        raise NotImplementedError(
            "initiate درگاه tejarat هنوز با اطلاعات واقعی پیاده‌سازی و تست نشده است."
        )

    def verify(self, *, authority: str, amount: int, order_id: str) -> PaymentResult:
        # TODO: verify را طبق مستندات تجارت (مبنا) پیاده کن.
        #       اگر دومرحله‌ای است، هر دو مرحله اینجا.
        raise NotImplementedError(
            "verify درگاه tejarat هنوز با اطلاعات واقعی پیاده‌سازی و تست نشده است."
        )
