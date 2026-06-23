"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 راهنمای کامل استفاده از درگاه زرین‌پال در پروژه‌ی Django
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

زرین‌پال یک درگاه پرداخت اینترنتی ایرانی محبوب با REST API است. sandbox آن
بدون ثبت‌نام و از هر IP قابل تست است. این درگاه در registry عمومی پکیج قرار
دارد و با لایه‌ی کامل Django (مدل Payment + سرویس) کار می‌کند.

━━ قدم ۱: نصب پکیج ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    pip install django-iranian-payment
    # یا با uv:
    uv add django-iranian-payment

━━ قدم ۲: تنظیمات settings.py ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    INSTALLED_APPS = [
        ...
        "django_iranian_payment.contrib.django",   # لایه‌ی Django پکیج
    ]

    IRANIAN_PAYMENT = {
        "sandbox": True,   # False در محیط production
        "gateways": {
            "zarinpal": {
                "merchant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                # merchant_id را از پنل زرین‌پال (https://www.zarinpal.com) بگیر.
                # برای sandbox می‌توانی هر UUID ۳۶ کاراکتری بدهی.
            },
        },
    }

━━ قدم ۳: اجرای migration ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    python manage.py migrate

    # جدول iranian_payment_payment ساخته می‌شود.

━━ قدم ۴: اضافه کردن URL های پکیج در urls.py پروژه ━━━━━━━━━━

    # project/urls.py
    from django.urls import path, include

    urlpatterns = [
        ...
        path("payment/", include("django_iranian_payment.contrib.django.urls")),
    ]

    # این مسیرها ساخته می‌شوند:
    #   GET  /payment/go/<payment_id>/          → هدایت کاربر به درگاه
    #   GET|POST /payment/callback/zarinpal/    → برگشت از بانک

━━ قدم ۵: view پرداخت در app خودت ━━━━━━━━━━━━━━━━━━━━━━━━━━

    کد کامل view ها در بخش بعدی همین فایل است. آن را در views.py app
    خودت کپی و تنظیم کن.

━━ قدم ۶: URL های app خودت ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # yourapp/urls.py
    from django.urls import path
    from . import views

    urlpatterns = [
        path("checkout/", views.checkout, name="checkout"),
        path("payment/result/", views.payment_result, name="payment-result"),
    ]

━━ نکات مهم زرین‌پال ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • مبلغ همیشه به ریال است (نه تومان). مثلاً ۱۰۰۰۰۰ ریال = ۱۰۰۰۰ تومان.
  • redirect ساده است (GET) — نیازی به فرم POST نیست.
  • Authority در callback GET برمی‌گردد: /callback/zarinpal/?Authority=...&Status=OK
  • در verify، مبلغ باید دقیقاً همان مبلغ initiate باشد (نه مبلغ پایه سفارش اگر
    کارمزد از مشتری گرفتی). پکیج این را خودکار با amount_sent مدیریت می‌کند.
"""

# ─────────────────────────────────────────────────────────────
#  کد view — این را در views.py app خودت کپی کن
# ─────────────────────────────────────────────────────────────

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse

from django_iranian_payment.contrib.django.services import start_payment, verify_payment
from django_iranian_payment.contrib.django.models import Payment, PaymentStatus
from django_iranian_payment.core.exceptions import GatewayError
from django_iranian_payment.core.fee import FeeConfig, FeePayer


def checkout(request):
    """
    قدم اول پرداخت: کاربر به صفحه‌ی checkout می‌آید، سبد خرید را تأیید می‌کند،
    و ما او را به زرین‌پال می‌فرستیم.

    در یک پروژه‌ی واقعی این view احتمالاً POST است و order را از سبد خرید می‌سازد.
    اینجا برای سادگی مقادیر ثابت داریم.
    """
    # ── تنظیمات سفارش ──────────────────────────────────────────────────────────
    order_id = "ORDER-2001"  # شناسه‌ی یکتای سفارش در سیستم تو
    amount = 150_000  # ریال — مبلغ سفارش

    # callback_url: آدرس کاملی که زرین‌پال کاربر را پس از پرداخت به آن می‌فرستد
    # این باید آدرس /payment/callback/zarinpal/ پکیج باشد، نه view خودت.
    callback_url = request.build_absolute_uri(
        reverse("iranian_payment:callback", kwargs={"slug": "zarinpal"})
    )

    # اگر می‌خواهی کارمزد از مشتری بگیری (مثلاً ۱٪):
    # fee = FeeConfig(rate_bps=100, who_pays=FeePayer.CUSTOMER)
    # در غیر این صورت fee=None بگذار (بدون کارمزد جداگانه)
    fee = None

    # ── شروع پرداخت ────────────────────────────────────────────────────────────
    try:
        payment, redirect_url = start_payment(
            slug="zarinpal",
            amount=amount,
            callback_url=callback_url,
            order_id=order_id,
            description="خرید محصول از فروشگاه ما",
            mobile="09120000000",  # اختیاری — شناسه‌ی کاربر در زرین‌پال
            email="user@example.com",  # اختیاری
            fee=fee,
        )
    except GatewayError as e:
        # خطای اتصال به زرین‌پال یا رد شدن درخواست
        return HttpResponse(
            f"خطا در اتصال به درگاه: {e}<br>کد: {e.code}",
            status=502,
        )

    # payment.id را در session ذخیره کن تا بعداً بتوانی وضعیت را نمایش دهی
    request.session["pending_payment_id"] = payment.id

    # کاربر را به درگاه زرین‌پال هدایت کن
    # یا از URL پکیج استفاده کن: /payment/go/<payment.id>/
    return HttpResponseRedirect(redirect_url)


def payment_result(request):
    """
    این view پس از callback زرین‌پال صدا می‌شود.
    پکیج callback را verify می‌زند و با payment_status به این آدرس redirect می‌کند:
        /payment/result/?payment_status=success&order_id=ORDER-2001
        /payment/result/?payment_status=failed&order_id=ORDER-2001

    توجه: این view را در callback_url نگذار. callback_url باید به مسیر
    /payment/callback/zarinpal/ پکیج اشاره کند. پکیج بعد از verify،
    redirect_url سفارش را از رکورد Payment می‌خواند و به آن می‌فرستد.

    برای تنظیم callback_url سفارش، در start_payment:
        callback_url = "https://yoursite.com/payment/callback/zarinpal/"

    و در settings IRANIAN_PAYMENT تنظیمی برای order_redirect_url ندارد —
    پکیج از payment.callback_url رکورد استفاده می‌کند.

    اگر می‌خواهی بعد از verify به /payment/result/ بروی، باید در view خودت
    redirect بزنی یا از services.verify_payment() مستقیم استفاده کنی.
    """
    # نمونه: خواندن نتیجه از query string که پکیج می‌فرستد
    status = request.GET.get("payment_status")  # "success" یا "failed"
    order_id = request.GET.get("order_id", "")

    if status == "success":
        # پرداخت موفق — سفارش را فعال کن، ایمیل ارسال کن، ...
        # برای گرفتن جزئیات بیشتر (reference_id، card_number) رکورد را بخوان:
        payment = Payment.objects.filter(
            order_id=order_id, status=PaymentStatus.COMPLETE
        ).first()
        if payment:
            ref = payment.reference_id
            return HttpResponse(
                f"پرداخت موفق! کد پیگیری: {ref} — سفارش {order_id} فعال شد."
            )
    elif status == "failed":
        return HttpResponse(
            f"پرداخت ناموفق برای سفارش {order_id}. لطفاً دوباره تلاش کنید."
        )

    return HttpResponse("نتیجه‌ی پرداخت نامشخص.", status=400)


# ─────────────────────────────────────────────────────────────
#  استفاده مستقیم از core (بدون لایه‌ی Django) — اختیاری
# ─────────────────────────────────────────────────────────────
#
# اگر نمی‌خواهی از مدل Payment و سرویس‌های لایه‌ی contrib استفاده کنی،
# می‌توانی مستقیم با هسته کار کنی:
#
#   from django_iranian_payment import get_gateway
#   from django_iranian_payment.core.models import PaymentRequest
#
#   gw = get_gateway("zarinpal")
#   result = gw.initiate(PaymentRequest(amount=150_000, callback_url="...", order_id="1"))
#   # result.redirect_url را ذخیره کن و کاربر را به آن هدایت کن
#
#   # در callback:
#   authority = request.GET.get("Authority")
#   verify_result = gw.verify(authority=authority, amount=150_000, order_id="1")
#   if verify_result.is_success:
#       ...


if __name__ == "__main__":
    print(
        "این فایل یک راهنمای یکپارچه‌سازی Django است.\n"
        "کد view ها را در views.py app خودت کپی کن.\n"
        "برای تست sandbox core: uv run python scripts/test_zarinpal.py"
    )
