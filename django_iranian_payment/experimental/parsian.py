"""
درگاه پارسیان (parsian) — SOAP — تجربی و تست‌نشده.

⚠️ این اسکلت بدون اطلاعات/ترمینال واقعی نوشته شده و با هیچ تراکنشی تست نشده.
در registry عمومی نیست. فقط با import صریح در دسترس است:
    from django_iranian_payment.experimental import ParsianGateway

نکات این درگاه: SOAP — به zeep نیاز دارد. verify دومرحله‌ای (confirm). callback از نوع POST.

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

# این درگاه SOAP است و به zeep نیاز دارد:
#     pip install "django-iranian-payment[soap]"
# from zeep import Client  # داخل متد import شود تا نبودش پکیج را نشکند


class ParsianGateway(BaseGateway):
    slug = "parsian"
    requires = ('login_account',)

    # TODO: آدرس‌های واقعی request/verify/startpay را از مستندات بگذار
    _REQUEST_URL = ""   # TODO
    _VERIFY_URL = ""    # TODO
    _STARTPAY_URL = ""  # TODO

    def initiate(self, request: PaymentRequest) -> InitiateResult:
        # TODO: payload را طبق مستندات پارسیان بساز.
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
            "initiate درگاه parsian هنوز با اطلاعات واقعی پیاده‌سازی و تست نشده است."
        )

    def verify(self, *, authority: str, amount: int, order_id: str) -> PaymentResult:
        # TODO: verify را طبق مستندات پارسیان پیاده کن.
        #       کد موفقیت و فیلد reference_id را از مستندات استخراج کن.
        #       اگر verify دومرحله‌ای است (مثل پاسارگاد/پارسیان)، هر دو مرحله اینجا.
        raise NotImplementedError(
            "verify درگاه parsian هنوز با اطلاعات واقعی پیاده‌سازی و تست نشده است."
        )
