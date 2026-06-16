"""
درگاه به‌پرداخت ملی (سداد) (melli) — تجربی و تست‌نشده.

⚠️ این اسکلت بدون اطلاعات/ترمینال واقعی نوشته شده و با هیچ تراکنشی تست نشده.
در registry عمومی نیست. فقط با import صریح:
    from django_iranian_payment.core.experimental import MelliGateway

نکات این درگاه: رمزنگاری Triple-DES لازم است. callback از نوع POST.

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


class MelliGateway(BaseGateway):
    slug = "melli"
    requires = ("terminal_id", "merchant_id", "terminal_key")

    # TODO: آدرس‌های واقعی request/verify/startpay را از مستندات بگذار
    _REQUEST_URL = ""  # TODO
    _VERIFY_URL = ""  # TODO
    _STARTPAY_URL = ""  # TODO

    def initiate(self, request: PaymentRequest) -> InitiateResult:
        # TODO: payload را طبق مستندات به‌پرداخت ملی (سداد) بساز. مبلغ ریال است؛ کارمزد را با
        #       request.resolve_amount().amount_to_send بگیر، نه request.amount.
        raise NotImplementedError(
            "initiate درگاه melli هنوز با اطلاعات واقعی پیاده‌سازی و تست نشده است."
        )

    def verify(self, *, authority: str, amount: int, order_id: str) -> PaymentResult:
        # TODO: verify را طبق مستندات به‌پرداخت ملی (سداد) پیاده کن.
        #       اگر دومرحله‌ای است، هر دو مرحله اینجا.
        raise NotImplementedError(
            "verify درگاه melli هنوز با اطلاعات واقعی پیاده‌سازی و تست نشده است."
        )
