"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 راهنمای کامل استفاده از درگاه سامان (SEP) در Django
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

سامان (SEP — Saman Electronic Payment) درگاه پرداخت اینترنتی بانک سامان است.
از REST API و Token-based flow استفاده می‌کند.

⚠️ وضعیت: تجربی (experimental) — کد از مستند رسمی، ولی sandbox تست نشده.
نیاز به TerminalId واقعی و ثبت IP سرور نزد سامان.

━━ قدم ۱: نصب ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    pip install django-iranian-payment

━━ قدم ۲: تنظیمات settings.py ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    INSTALLED_APPS = [
        ...
        "django_iranian_payment.contrib.django",
    ]

    IRANIAN_PAYMENT = {
        "sandbox": True,
        "gateways": {
            "saman": {
                "terminal_id": "123456789",  # شماره ترمینال از پرداخت الکترونیک سامان
                # اختیاری: "redirect_url" برای neo-pg (X-IPG-Url header)
                # "redirect_url": "https://sep.shaparak.ir/OnlinePG/SendToken",
            },
        },
    }

━━ قدم ۳: ثبت درگاه سامان در registry ━━━━━━━━━━━━━━━━━━━━━

    # yourapp/apps.py
    class YourAppConfig(AppConfig):
        name = "yourapp"

        def ready(self):
            from django_iranian_payment.core.gateways import _REGISTRY
            from django_iranian_payment.core.experimental.saman import SamanGateway
            _REGISTRY["saman"] = SamanGateway

━━ قدم ۴: URL های پکیج ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    urlpatterns = [
        ...
        path("payment/", include("django_iranian_payment.contrib.django.urls")),
    ]

    # مسیرها:
    #   GET  /payment/go/<payment_id>/       → هدایت به درگاه
    #   POST /payment/callback/saman/        → برگشت از بانک

━━ نکات مهم سامان ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • مرحله‌ی ۱ (initiate) یک Token برمی‌گرداند، نه URL آماده.
    redirect_url ساخته‌شده شکل: .../SendToken?token=<token>
    کاربر با GET redirect ساده می‌رود (نیازی به POST form نیست).
  • callback با POST برمی‌گردد. پکیج RefNum و State را از POST استخراج می‌کند.
  • verify به RefNum نیاز دارد (نه Token). پکیج آن را از extra می‌گیرد.
  • ثبت IP سرور: بدون آن، در دریافت Token کد ۸ می‌گیری.
    (MerchantIpAddressIsInvalid)
"""

from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse

from django_iranian_payment.contrib.django.services import start_payment
from django_iranian_payment.contrib.django.models import Payment, PaymentStatus
from django_iranian_payment.core.exceptions import GatewayError


def checkout(request):
    """
    شروع پرداخت با سامان.
    initiate یک Token برمی‌گرداند؛ redirect_url را برای هدایت کاربر استفاده کن.
    """
    order_id = "SAMAN-ORDER-001"  # ResNum — شناسه‌ی سفارش
    amount = 300_000  # ریال

    callback_url = request.build_absolute_uri(
        reverse("iranian_payment:callback", kwargs={"slug": "saman"})
    )

    try:
        payment, redirect_url = start_payment(
            slug="saman",
            amount=amount,
            callback_url=callback_url,
            order_id=order_id,
            description="خرید از سایت",
            mobile="09120000000",  # اختیاری
        )
    except GatewayError as e:
        return HttpResponse(f"خطا در اتصال به سامان: {e}", status=502)

    request.session["pending_payment_id"] = payment.id

    # کاربر را به درگاه سامان هدایت کن (GET redirect ساده)
    return HttpResponseRedirect(redirect_url)


def payment_result(request):
    """نتیجه‌ی پرداخت سامان."""
    status = request.GET.get("payment_status")
    order_id = request.GET.get("order_id", "")

    if status == "success":
        payment = Payment.objects.filter(
            order_id=order_id, status=PaymentStatus.COMPLETE
        ).first()
        if payment:
            return HttpResponse(
                f"پرداخت سامان موفق! "
                f"RefNum: {payment.reference_id} | "
                f"مبلغ: {payment.amount_sent:,} ریال"
            )
    elif status == "failed":
        payment = Payment.objects.filter(order_id=order_id).first()
        err = payment.error_message if payment else ""
        return HttpResponse(f"پرداخت ناموفق. {err}")

    return HttpResponse("وضعیت نامشخص.", status=400)


# ─────────────────────────────────────────────────────────────
#  استفاده از reverse() برای برگشت وجه سامان
# ─────────────────────────────────────────────────────────────
#
# سامان متد برگشت وجه دارد:
#
#   from django_iranian_payment import get_gateway
#
#   def reverse_saman(ref_num):
#       gw = get_gateway("saman")
#       result = gw.reverse(ref_num=ref_num)
#       return result.is_success


if __name__ == "__main__":
    print(
        "این فایل راهنمای Django درگاه سامان است.\n"
        "برای تست sandbox: uv run python scripts/test_saman.py\n"
        "⚠️  نیاز به TerminalId واقعی و IP ثبت‌شده نزد سامان."
    )
