"""
درگاه پی‌آی‌آر (Pay.ir) — معلق (suspended). موقتاً از registry عمومی خارج شد.

⚠️ این درگاه قبلاً تست‌شده و کارکرد صحیح داشت، اما در عمل با خطای دسترسی مواجه شد
و وضعیت عملیاتی/حقوقی شبکهٔ پرداخت پی بی‌ثبات گزارش شده است (دوره‌های مسدودیت
ترمینال‌ها توسط شاپرک/مراجع قضایی). طبق قانون طلایی پروژه — «هیچ درگاهی عمومی
نمی‌ماند مگر تست واقعی موفق» — تا تأیید مجدد پایداری سرویس، از registry خارج است.

کد سالم و کامل است؛ این انتقال صرفاً به‌دلیل پایداری سرویس است، نه نقص پیاده‌سازی.

در registry عمومی نیست. فقط با import صریح و با مسئولیت خودت:
    from django_iranian_payment.core.experimental import PayIrGateway

برای بازگردانی به registry عمومی پس از تأیید پایداری سرویس:
    ۱. با sandbox/ترمینال واقعی دوباره تست کن (scripts/test_pay_ir.py).
    ۲. فایل را به core/gateways/pay_ir.py برگردان.
    ۳. در core/gateways/__init__.py دوباره import و به _REGISTRY اضافه کن.
    ۴. خط آن را از core/experimental/__init__.py حذف کن.

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
        fee_result = request.resolve_amount()
        amount_to_send = fee_result.amount_to_send

        payload = {
            "api": self.config["api"],
            "amount": amount_to_send,  # ریال
            "redirect": request.callback_url,
            "factorNumber": request.order_id,
            "description": request.description,
        }
        if request.mobile:
            payload["mobile"] = request.mobile

        result = self._post(self._REQUEST, json=payload)

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
            amount_to_send=amount_to_send,
            fee=fee_result.fee,
            raw=result,
        )

    def verify(self, *, authority: str, amount: int, order_id: str) -> PaymentResult:
        payload = {"api": self.config["api"], "token": authority}
        result = self._post(self._VERIFY, json=payload)

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
