"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 راهنمای کامل استفاده از درگاه زیبال در پروژه‌ی Django
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

زیبال یک درگاه پرداخت اینترنتی ایرانی با REST API است. sandbox آن با
merchant="zibal" بدون ثبت‌نام و از هر IP قابل تست است. این درگاه در registry
عمومی پکیج قرار دارد.

━━ قدم ۱: نصب پکیج ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    pip install django-iranian-payment

━━ قدم ۲: تنظیمات settings.py ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    INSTALLED_APPS = [
        ...
        "django_iranian_payment.contrib.django",
    ]

    IRANIAN_PAYMENT = {
        "sandbox": True,   # False در production
        "gateways": {
            "zibal": {
                "merchant": "zibal",
                # برای sandbox از "zibal" استفاده کن (نیاز به ثبت‌نام ندارد).
                # در production، merchant را از پنل زیبال (https://zibal.ir) بگیر.
            },
        },
    }

━━ قدم ۳: migration ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    python manage.py migrate

━━ قدم ۴: URL های پکیج ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # project/urls.py
    urlpatterns = [
        ...
        path("payment/", include("django_iranian_payment.contrib.django.urls")),
    ]

    # مسیرهای ساخته‌شده:
    #   GET  /payment/go/<payment_id>/        → هدایت به درگاه
    #   GET  /payment/callback/zibal/         → برگشت از بانک (GET)

━━ قدم ۵: کانفیگ callback در زیبال ━━━━━━━━━━━━━━━━━━━━━━━━━

    آدرس callback را در پنل زیبال ثبت کن:
        https://yoursite.com/payment/callback/zibal/

    زیبال در callback، trackId را به صورت GET می‌فرستد:
        /payment/callback/zibal/?trackId=<id>&success=1&status=1

━━ تفاوت زیبال با زرین‌پال ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • authority در زیبال trackId نام دارد (پکیج آن را خودکار mapping می‌کند).
  • callback با GET برمی‌گردد — نیاز به POST form نیست.
  • مبلغ همیشه به ریال است.
"""

from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse

from django_iranian_payment.contrib.django.services import start_payment
from django_iranian_payment.contrib.django.models import Payment, PaymentStatus
from django_iranian_payment.core.exceptions import GatewayError


def checkout(request):
    """
    شروع فرایند پرداخت با زیبال.

    این view سفارش کاربر را می‌گیرد، یک رکورد Payment می‌سازد،
    با زیبال ارتباط برقرار می‌کند و کاربر را به درگاه هدایت می‌کند.
    """
    order_id = "ORDER-3001"
    amount = 200_000  # ریال

    callback_url = request.build_absolute_uri(
        reverse("iranian_payment:callback", kwargs={"slug": "zibal"})
    )

    try:
        payment, redirect_url = start_payment(
            slug="zibal",
            amount=amount,
            callback_url=callback_url,
            order_id=order_id,
            description="خرید از فروشگاه",
            mobile="09120000000",  # اختیاری — برای نمایش اطلاعات کارت در درگاه
        )
    except GatewayError as e:
        return HttpResponse(f"خطا در اتصال به زیبال: {e}", status=502)

    # ذخیره‌ی payment.id در session برای ردیابی بعدی
    request.session["pending_payment_id"] = payment.id

    # کاربر را به درگاه زیبال هدایت کن (redirect ساده — GET)
    return HttpResponseRedirect(redirect_url)


def payment_result(request):
    """
    نمایش نتیجه‌ی پرداخت — کاربر بعد از callback پکیج به اینجا هدایت می‌شود.

    پکیج پس از verify، کاربر را به callback_url سفارش می‌فرستد با:
        ?payment_status=success&order_id=ORDER-3001
        ?payment_status=failed&order_id=ORDER-3001
    """
    status = request.GET.get("payment_status")
    order_id = request.GET.get("order_id", "")

    if status == "success":
        payment = Payment.objects.filter(
            order_id=order_id, status=PaymentStatus.COMPLETE
        ).first()
        if payment:
            return HttpResponse(
                f"پرداخت موفق! "
                f"کد پیگیری: {payment.reference_id} | "
                f"مبلغ: {payment.amount_sent:,} ریال"
            )
    elif status == "failed":
        payment = Payment.objects.filter(order_id=order_id).first()
        err = payment.error_message if payment else "نامشخص"
        return HttpResponse(f"پرداخت ناموفق: {err}")

    return HttpResponse("وضعیت پرداخت نامشخص است.", status=400)


# ─────────────────────────────────────────────────────────────
#  نمونه‌ی استفاده از go_to_gateway (الگوی دو مرحله‌ای)
# ─────────────────────────────────────────────────────────────
#
# اگر می‌خواهی payment را بسازی ولی کاربر را هنوز به درگاه نفرستی
# (مثلاً پس از تأیید قرارداد / احراز هویت):
#
#   payment, _ = start_payment(slug="zibal", ...)
#   # در response نمایش بده که "برای رفتن به درگاه کلیک کن"
#   # با لینک: /payment/go/<payment.id>/
#
# view go_to_gateway از URL patterns پکیج این کار را خودکار انجام می‌دهد.


if __name__ == "__main__":
    print(
        "این فایل یک راهنمای یکپارچه‌سازی Django است.\n"
        "برای تست sandbox core: uv run python scripts/test_zibal.py"
    )
