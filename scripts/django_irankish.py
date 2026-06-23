"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 راهنمای کامل استفاده از درگاه ایران‌کیش در Django
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ایران‌کیش (IranKish) درگاه پرداخت اینترنتی گروه توسن/شاپرک است. از رمزنگاری
AES+RSA برای ساخت authenticationEnvelope استفاده می‌کند.

⚠️ وضعیت: تجربی (experimental) — نیاز به ترمینال واقعی، کلید عمومی RSA بانک
و ثبت IP.

━━ قدم ۱: نصب با وابستگی رمزنگاری ━━━━━━━━━━━━━━━━━━━━━━━━━

    pip install "django-iranian-payment[irankish]"
    # pycryptodome + rsa برای رمزنگاری نیاز است

━━ قدم ۲: تنظیمات settings.py ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    INSTALLED_APPS = [
        ...
        "django_iranian_payment.contrib.django",
    ]

    IRANIAN_PAYMENT = {
        "sandbox": True,
        "gateways": {
            "irankish": {
                "terminal_id": "xxxxxxxx",       # hex — از ایران‌کیش
                "acceptor_id": "xxxxxxxx",       # hex — از ایران‌کیش
                "pass_phrase": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",  # hex ۳۲+ کاراکتر
                "public_key": "/path/to/irankish_public.pem",  # مسیر کلید RSA بانک
            },
        },
    }

━━ قدم ۳: دریافت کلید عمومی RSA ━━━━━━━━━━━━━━━━━━━━━━━━━━━

    کلید عمومی RSA ایران‌کیش را از پورتال ایران‌کیش یا از تیم فنی
    بانک بگیر و در مسیری مشخص ذخیره کن. مسیر را در public_key بده.

━━ قدم ۴: ثبت درگاه در registry ━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # yourapp/apps.py
    class YourAppConfig(AppConfig):
        name = "yourapp"

        def ready(self):
            from django_iranian_payment.core.gateways import _REGISTRY
            from django_iranian_payment.core.experimental.irankish import IrankishGateway
            _REGISTRY["irankish"] = IrankishGateway

━━ قدم ۵: URL های پکیج ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    urlpatterns = [
        ...
        path("payment/", include("django_iranian_payment.contrib.django.urls")),
    ]

    # مسیرها:
    #   GET  /payment/go/<payment_id>/        → هدایت به درگاه
    #   POST /payment/callback/irankish/      → برگشت از بانک (POST)

━━ نکات مهم ایران‌کیش ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • verify به token و reference_id نیاز دارد که در callbackِ POST برمی‌گردند.
    پکیج آن‌ها را از extra استخراج می‌کند.
  • برخلاف کد مرجع، پکیج SSL را هیچ‌گاه خاموش نمی‌کند — امنیتی‌تر است.
  • اگر IP ثبت نشده باشد یا کلید اشتباه باشد، GatewayPaymentError می‌گیری.
  • بانک ملی → ایران‌کیش (درگاه مستقل تجارت حذف و به این ادغام شده).
"""

from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse

from django_iranian_payment.contrib.django.services import start_payment
from django_iranian_payment.contrib.django.models import Payment, PaymentStatus
from django_iranian_payment.core.exceptions import GatewayError


def checkout(request):
    """
    شروع پرداخت با ایران‌کیش.

    initiate با AES+RSA رمزنگاری می‌کند و Token برمی‌گرداند.
    redirect_url ساخته‌شده کاربر را با GET به درگاه می‌برد.
    """
    order_id = "IK-ORDER-001"
    amount = 250_000  # ریال

    callback_url = request.build_absolute_uri(
        reverse("iranian_payment:callback", kwargs={"slug": "irankish"})
    )

    try:
        payment, redirect_url = start_payment(
            slug="irankish",
            amount=amount,
            callback_url=callback_url,
            order_id=order_id,
            description="خرید از سایت",
        )
    except GatewayError as e:
        return HttpResponse(f"خطا در اتصال به ایران‌کیش: {e}", status=502)

    request.session["pending_payment_id"] = payment.id

    # کاربر را به درگاه ایران‌کیش هدایت کن
    return HttpResponseRedirect(redirect_url)


def payment_result(request):
    """نتیجه‌ی پرداخت ایران‌کیش."""
    status = request.GET.get("payment_status")
    order_id = request.GET.get("order_id", "")

    if status == "success":
        payment = Payment.objects.filter(
            order_id=order_id, status=PaymentStatus.COMPLETE
        ).first()
        if payment:
            return HttpResponse(f"پرداخت موفق! کد پیگیری: {payment.reference_id}")
    elif status == "failed":
        return HttpResponse("پرداخت ناموفق. لطفاً دوباره تلاش کنید.")

    return HttpResponse("وضعیت نامشخص.", status=400)


if __name__ == "__main__":
    print(
        "این فایل راهنمای Django درگاه ایران‌کیش است.\n"
        "برای تست sandbox: uv run python scripts/test_irankish.py\n"
        "⚠️  نیاز به کلید RSA بانک، ترمینال واقعی و IP ثبت‌شده."
    )
