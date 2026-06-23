"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 راهنمای کامل استفاده از درگاه دیجی‌پی در Django
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

دیجی‌پی (DigiPay) درگاه پرداخت دیجی‌کالا است. از OAuth2 برای احراز هویت و
REST API برای پرداخت استفاده می‌کند. محیط staging آن (sandbox) با اطلاعات
uat.mydigipay.info قابل تست است.

⚠️ وضعیت: تجربی (experimental) — کد کامل از مستند رسمی + sandbox تأیید نشده.
نیاز به: username/password/client_id/client_secret/provider_id از دیجی‌پی.

━━ قدم ۱: نصب ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    pip install django-iranian-payment

━━ قدم ۲: تنظیمات settings.py ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    INSTALLED_APPS = [
        ...
        "django_iranian_payment.contrib.django",
    ]

    IRANIAN_PAYMENT = {
        "sandbox": True,   # محیط UAT/staging دیجی‌پی
        "gateways": {
            "digipay": {
                "username": "your-username",          # از پورتال دیجی‌پی
                "password": "your-password",          # از پورتال دیجی‌پی
                "client_id": "your-client-id",        # OAuth2 client
                "client_secret": "your-client-secret",
                "provider_id": "your-provider-id",    # شناسه‌ی کسب‌وکار شما
                # اختیاری:
                # "ticket_type": 11,   # پیش‌فرض ۱۱ (UPG). انواع دیگر: ۳۸ (QR)
            },
        },
    }

━━ قدم ۳: ثبت درگاه در registry ━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # yourapp/apps.py
    class YourAppConfig(AppConfig):
        name = "yourapp"

        def ready(self):
            from django_iranian_payment.core.gateways import _REGISTRY
            from django_iranian_payment.core.experimental.digipay import DigipayGateway
            _REGISTRY["digipay"] = DigipayGateway

━━ قدم ۴: URL های پکیج ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    urlpatterns = [
        ...
        path("payment/", include("django_iranian_payment.contrib.django.urls")),
    ]

    # مسیرها:
    #   GET  /payment/go/<payment_id>/        → هدایت به درگاه
    #   POST /payment/callback/digipay/       → برگشت از بانک

━━ نکات مهم دیجی‌پی ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • هر بار initiate/verify، ابتدا OAuth2 token تازه می‌گیرد (بدون state).
    هر درخواست = یک token جدید. این از مستند رسمی است.
  • کلید موفقیت result.status==0 است (نه HTTP status code).
  • verify به trackingCode (از callback) نیاز دارد — در extra["tracking_code"].
  • providerId در verify باید با order_id تراکنش تطبیق داشته باشد.
    پکیج آن را از order_id سفارش می‌گیرد.
  • redirect_url از پاسخ API خوانده می‌شود (نه ساخته می‌شود).
"""

from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse

from django_iranian_payment.contrib.django.services import start_payment
from django_iranian_payment.contrib.django.models import Payment, PaymentStatus
from django_iranian_payment.core.exceptions import GatewayError


def checkout(request):
    """
    شروع پرداخت با دیجی‌پی.

    دیجی‌پی ابتدا OAuth2 token می‌گیرد، سپس ticket می‌سازد و redirect_url
    برمی‌گرداند. کاربر با GET redirect به صفحه‌ی پرداخت می‌رود.
    """
    order_id = "DIGIPAY-ORDER-001"
    amount = 350_000  # ریال

    callback_url = request.build_absolute_uri(
        reverse("iranian_payment:callback", kwargs={"slug": "digipay"})
    )

    try:
        payment, redirect_url = start_payment(
            slug="digipay",
            amount=amount,
            callback_url=callback_url,
            order_id=order_id,
            description="خرید آنلاین",
            mobile="09120000000",  # اختیاری
        )
    except GatewayError as e:
        return HttpResponse(f"خطا در اتصال به دیجی‌پی: {e}", status=502)

    request.session["pending_payment_id"] = payment.id

    # کاربر را به درگاه دیجی‌پی هدایت کن
    return HttpResponseRedirect(redirect_url)


def payment_result(request):
    """
    نتیجه‌ی پرداخت دیجی‌پی.

    دیجی‌پی trackingCode را در callback برمی‌گرداند. پکیج آن را از extra
    می‌خواند و به verify می‌دهد.
    """
    status = request.GET.get("payment_status")
    order_id = request.GET.get("order_id", "")

    if status == "success":
        payment = Payment.objects.filter(
            order_id=order_id, status=PaymentStatus.COMPLETE
        ).first()
        if payment:
            return HttpResponse(f"پرداخت موفق! کد پیگیری: {payment.reference_id}")
    elif status == "failed":
        return HttpResponse("پرداخت ناموفق.")

    return HttpResponse("وضعیت نامشخص.", status=400)


# ─────────────────────────────────────────────────────────────
#  نکته‌ی مهم درباره‌ی callback دیجی‌پی
# ─────────────────────────────────────────────────────────────
#
# دیجی‌پی trackingCode را در پارامتر callback می‌فرستد.
# پکیج callback view این مقدار را در extra["tracking_code"] قرار می‌دهد
# و به verify() پاس می‌دهد.
#
# بررسی کن که در _extract_extra (views.py پکیج) trackingCode خوانده می‌شود.
# اگر نام پارامتر callback در API دیجی‌پی تغییر کرد، آن را به‌روز کن.


if __name__ == "__main__":
    print(
        "این فایل راهنمای Django درگاه دیجی‌پی است.\n"
        "برای تست sandbox: uv run python scripts/test_digipay.py\n"
        "⚠️  نیاز به اعتبارنامه‌ی کامل از پورتال دیجی‌پی."
    )
