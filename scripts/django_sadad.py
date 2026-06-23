"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 راهنمای کامل استفاده از درگاه سداد (بانک ملی) در Django
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

سداد (Sadad) درگاه پرداخت اینترنتی بانک ملی ایران است. از REST API و امضای
3DES (ECB, PKCS7) برای SignData استفاده می‌کند.

⚠️ وضعیت: تجربی (experimental) — کد از مستند رسمی، sandbox تأیید نشده.
نیاز به MerchantId، TerminalId، TerminalKey (Base64) و ثبت IP.

━━ قدم ۱: نصب با وابستگی رمزنگاری ━━━━━━━━━━━━━━━━━━━━━━━━━

    pip install "django-iranian-payment[sadad]"
    # pycryptodome برای 3DES نیاز است

━━ قدم ۲: تنظیمات settings.py ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    INSTALLED_APPS = [
        ...
        "django_iranian_payment.contrib.django",
    ]

    IRANIAN_PAYMENT = {
        "sandbox": True,
        "gateways": {
            "sadad": {
                "merchant_id": "1234",          # شناسه پذیرنده از سداد
                "terminal_id": "5678",          # شناسه ترمینال از سداد
                "terminal_key": "BASE64_KEY==", # کلید پذیرنده به‌صورت Base64
                # کلید را از پورتال سداد (https://sadad.shaparak.ir) بگیر.
                # بعد از دیکد باید ۱۶ یا ۲۴ بایت باشد (3DES).
            },
        },
    }

━━ قدم ۳: ثبت درگاه در registry ━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # yourapp/apps.py
    class YourAppConfig(AppConfig):
        name = "yourapp"

        def ready(self):
            from django_iranian_payment.core.gateways import _REGISTRY
            from django_iranian_payment.core.experimental.sadad import SadadGateway
            _REGISTRY["sadad"] = SadadGateway

━━ قدم ۴: URL های پکیج ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    urlpatterns = [
        ...
        path("payment/", include("django_iranian_payment.contrib.django.urls")),
    ]

    # مسیرها:
    #   GET  /payment/go/<payment_id>/      → هدایت به درگاه
    #   POST /payment/callback/sadad/       → برگشت از بانک (POST)

━━ نکات مهم سداد ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • مرحله‌ی ۱ Token برمی‌گرداند. redirect_url شکل:
    .../Purchase?Token=<token>
  • کاربر با GET redirect ساده می‌رود (نیازی به POST form نیست).
  • callback با POST برمی‌گردد. Token را از POST می‌خوانیم.
  • verify باید ظرف ۱۵ دقیقه پس از پرداخت زده شود — وگرنه مبلغ برمی‌گردد.
  • ResCode=100 در verify یعنی DUPLICATE (قبلاً تأیید شده).
  • orderId باید عددی باشد.
"""

from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse

from django_iranian_payment.contrib.django.services import start_payment
from django_iranian_payment.contrib.django.models import Payment, PaymentStatus
from django_iranian_payment.core.exceptions import GatewayError


def checkout(request):
    """
    شروع پرداخت با سداد (بانک ملی).
    ظرف ۱۵ دقیقه پس از شروع، verify باید انجام شود.
    """
    order_id = "5001"  # باید عددی باشد
    amount = 400_000  # ریال

    callback_url = request.build_absolute_uri(
        reverse("iranian_payment:callback", kwargs={"slug": "sadad"})
    )

    try:
        payment, redirect_url = start_payment(
            slug="sadad",
            amount=amount,
            callback_url=callback_url,
            order_id=order_id,
            description="خرید آنلاین",
        )
    except GatewayError as e:
        return HttpResponse(f"خطا در اتصال به سداد: {e}", status=502)

    request.session["pending_payment_id"] = payment.id

    # کاربر را به درگاه سداد هدایت کن (GET redirect)
    return HttpResponseRedirect(redirect_url)


def payment_result(request):
    """نتیجه‌ی پرداخت سداد."""
    status = request.GET.get("payment_status")
    order_id = request.GET.get("order_id", "")

    if status == "success":
        payment = Payment.objects.filter(
            order_id=order_id, status=PaymentStatus.COMPLETE
        ).first()
        if payment:
            return HttpResponse(f"پرداخت سداد موفق! کد پیگیری: {payment.reference_id}")
    elif status == "failed":
        payment = Payment.objects.filter(order_id=order_id).first()
        err = payment.error_message if payment else ""
        return HttpResponse(f"پرداخت ناموفق. {err}")

    return HttpResponse("وضعیت نامشخص.", status=400)


if __name__ == "__main__":
    print(
        "این فایل راهنمای Django درگاه سداد (بانک ملی) است.\n"
        "برای تست sandbox: uv run python scripts/test_sadad.py\n"
        "⚠️  نیاز به MerchantId، TerminalId، TerminalKey و IP ثبت‌شده."
    )
