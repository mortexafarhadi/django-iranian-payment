"""
درگاه آیدی‌پی (IDPay) — معلق (suspended). موقتاً از registry عمومی خارج شد.

⚠️ این درگاه قبلاً تست‌شده بود و کدش سالم است، اما در عمل از کار افتاده گزارش شد
(آخرین فعالیت پشتیبانی سرویس حوالی 2025-11-20). طبق قانون طلایی پروژه — «هیچ
درگاهی عمومی نمی‌ماند مگر تست واقعی موفق» — تا تأیید مجدد در دسترس بودن سرویس،
از registry خارج است.

کد کامل و سالم است؛ این انتقال صرفاً به‌دلیل از کار افتادن سرویس است، نه نقص پیاده‌سازی.

در registry عمومی نیست. فقط با import صریح و با مسئولیت خودت:
    from django_iranian_payment.core.experimental import IDPayGateway

برای بازگردانی به registry عمومی پس از تأیید فعال‌شدن سرویس:
    ۱. با sandbox/api_key واقعی دوباره تست کن (scripts/test_idpay.py).
    ۲. فایل را به core/gateways/idpay.py برگردان.
    ۳. در core/gateways/__init__.py دوباره import و به _REGISTRY اضافه کن.
    ۴. خط آن را از core/experimental/__init__.py حذف کن.

اصلاحات تاریخی این درگاه (نباید برگردند):
- status گاهی رشته برمی‌گردد ("100")؛ قبل از مقایسه به int تبدیل می‌شود.
- کارمزد اعمال می‌شود.
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

    @staticmethod
    def _as_int(value):
        """status را ایمن به int تبدیل می‌کند؛ اگر نشد None."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def initiate(self, request: PaymentRequest) -> InitiateResult:
        fee_result = request.resolve_amount()
        amount_to_send = fee_result.amount_to_send

        payload = {
            "order_id": request.order_id,
            "amount": amount_to_send,  # ریال
            "callback": request.callback_url,
            "desc": request.description,
        }
        if request.mobile:
            payload["phone"] = request.mobile
        if request.email:
            payload["mail"] = request.email

        result = self._post(self._REQUEST, json=payload, headers=self._headers())

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
            amount_to_send=amount_to_send,
            fee=fee_result.fee,
            raw=result,
        )

    def verify(self, *, authority: str, amount: int, order_id: str) -> PaymentResult:
        payload = {"id": authority, "order_id": order_id}
        result = self._post(self._VERIFY, json=payload, headers=self._headers())

        status = self._as_int(result.get("status"))
        if status in (100, 101):
            return PaymentResult(
                status=(
                    PaymentStatus.SUCCESS if status == 100 else PaymentStatus.DUPLICATE
                ),
                gateway_slug=self.slug,
                order_id=order_id,
                reference_id=str(result.get("track_id")),
                amount=self._as_int(result.get("amount")) or amount,
                card_number=(result.get("payment") or {}).get("card_no"),
                raw=result,
            )

        return PaymentResult(
            status=PaymentStatus.FAILED,
            gateway_slug=self.slug,
            order_id=order_id,
            error_code=str(status if status is not None else result.get("error_code")),
            error_message=str(result.get("error_message") or "verify ناموفق"),
            raw=result,
        )