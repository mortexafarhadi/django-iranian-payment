"""
درگاه سامان کیش (saman) — تجربی و تست‌نشده.

⚠️ این اسکلت بدون اطلاعات/ترمینال واقعی نوشته شده و با هیچ تراکنشی تست نشده.
در registry عمومی نیست. فقط با import صریح:
    from django_iranian_payment.core.experimental import SamanGateway

نکات این درگاه: initiate توکن می‌گیرد سپس فرم POST. callback POST.

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


class SamanGateway(BaseGateway):
    slug = "saman"
    requires = ("terminal_id", "password")

    # TODO: آدرس‌های واقعی request/verify/startpay را از مستندات بگذار
    _REQUEST_URL = ""  # TODO
    _VERIFY_URL = ""  # TODO
    _STARTPAY_URL = ""  # TODO

    def initiate(self, request: PaymentRequest) -> InitiateResult:
        # TODO: payload را طبق مستندات سامان کیش بساز. مبلغ ریال است؛ کارمزد را با
        #       request.resolve_amount().amount_to_send بگیر، نه request.amount.
        raise NotImplementedError(
            "initiate درگاه saman هنوز با اطلاعات واقعی پیاده‌سازی و تست نشده است."
        )

    def verify(self, *, authority: str, amount: int, order_id: str) -> PaymentResult:
        # TODO: verify را طبق مستندات سامان کیش پیاده کن.
        #       اگر دومرحله‌ای است، هر دو مرحله اینجا.
        raise NotImplementedError(
            "verify درگاه saman هنوز با اطلاعات واقعی پیاده‌سازی و تست نشده است."
        )
