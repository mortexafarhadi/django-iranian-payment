"""
درگاه به‌پرداخت ملی (سداد) (melli) — REST — تجربی و تست‌نشده.

⚠️ این اسکلت بدون اطلاعات/ترمینال واقعی نوشته شده و با هیچ تراکنشی تست نشده.
در registry عمومی نیست. فقط با import صریح در دسترس است:
    from django_iranian_payment.experimental import MelliGateway

نکات این درگاه: رمزنگاری Triple-DES روی داده‌ها لازم است — هنگام تست با مستندات سداد پر شود. callback از نوع POST.

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
    requires = ('terminal_id', 'merchant_id', 'terminal_key')

    # TODO: آدرس‌های واقعی request/verify/startpay را از مستندات بگذار
    _REQUEST_URL = ""   # TODO
    _VERIFY_URL = ""    # TODO
    _STARTPAY_URL = ""  # TODO

    def initiate(self, request: PaymentRequest) -> InitiateResult:
        # TODO: payload را طبق مستندات به‌پرداخت ملی (سداد) بساز.
        #       فیلدهای رایج: مبلغ (ریال)، callback، شناسه‌ی سفارش، توضیحات.
        #       امضا/رمزنگاری در صورت نیاز اینجا اعمال شود.
        # payload = {...}
        # result = self._post(self._REQUEST_URL, json=payload, headers={...}).json()
        #
        # if <خطا>:
        #     raise GatewayPaymentError("...", gateway=self.slug, code="...", raw=result)
        #
        # authority = result.get(...)
        # return InitiateResult(
        #     redirect_url=f"{self._STARTPAY_URL}/{authority}",
        #     authority=authority,
        #     raw=result,
        # )
        raise NotImplementedError(
            "initiate درگاه melli هنوز با اطلاعات واقعی پیاده‌سازی و تست نشده است."
        )

    def verify(self, *, authority: str, amount: int, order_id: str) -> PaymentResult:
        # TODO: verify را طبق مستندات به‌پرداخت ملی (سداد) پیاده کن.
        #       کد موفقیت و فیلد reference_id را از مستندات استخراج کن.
        #       اگر verify دومرحله‌ای است (مثل پاسارگاد/پارسیان)، هر دو مرحله اینجا.
        raise NotImplementedError(
            "verify درگاه melli هنوز با اطلاعات واقعی پیاده‌سازی و تست نشده است."
        )
