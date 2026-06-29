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
        "currency": "rial",   # واحد ورودی مبلغ: "rial" (پیش‌فرض) یا "toman"
        # sandbox سراسری: پیش‌فرض برای درگاه‌هایی که خودشان مشخص نکرده‌اند.
        "sandbox": False,
        "gateways": {
            "zarinpal": {
                "merchant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                # merchant_id را از پنل زرین‌پال (https://www.zarinpal.com) بگیر.
                # برای sandbox می‌توانی هر UUID ۳۶ کاراکتری بدهی.
                "sandbox": True,   # ← sandbox مجزای همین درگاه
                # زرین‌پال sandbox واقعی دارد (sandbox.zarinpal.com). با True اینجا،
                # این درگاه روی sandbox می‌رود حتی اگر sandbox سراسری False باشد.
                # این یعنی می‌توانی زرین‌پال را تست کنی و هم‌زمان درگاه دیگری live باشد.
            },
        },
    }

    # sandbox مجزای هر درگاه: کلید "sandbox" داخل config همان درگاه بر مقدار
    # سراسری اولویت دارد. اولویت کامل: آرگومان get_gateway(..., sandbox=...) >
    # config درگاه > sandbox سراسری > False.

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


# ═════════════════════════════════════════════════════════════
#  زرین‌پال — دو حالت مدیریت دیتابیس
# ═════════════════════════════════════════════════════════════
#
# حالت ۱ (پکیج DB را مدیریت می‌کند): همان checkout/payment_result بالا.
#   • از services.start_payment / verify_payment و مدل Payment پکیج استفاده می‌کنی.
#   • اپ "django_iranian_payment.contrib.django" را به INSTALLED_APPS اضافه و
#     migrate می‌کنی. url داخلی /payment/callback/zarinpal/ کار verify را می‌کند.
#
# حالت ۲ (خودت DB را مدیریت می‌کنی): کد زیر. مشخصات زرین‌پال در این حالت:
#   • هدایت: GET ساده (redirect به result.redirect_url). فرم POST لازم نیست.
#   • callback: GET — زرین‌پال ?Authority=...&Status=OK می‌فرستد.
#   • رکوردت را با authority پیدا کن (زرین‌پال order_id را در callback echo نمی‌کند).
#   • verify هیچ extra لازم ندارد (Status را خودت چک کن: "OK" یعنی کاربر پرداخت کرد).
#   • amount در verify باید amount_sent ذخیره‌شده باشد، نه مبلغ پایه.
# مدل نمونه‌ی MyPayment و توضیح کامل در scripts/django_custom_db.py است.

from django_iranian_payment import get_gateway
from django_iranian_payment.core.models import PaymentRequest


def checkout_self_managed(request):
    """حالت ۲ زرین‌پال — شروع پرداخت با مدل خودت (MyPayment)."""
    from yourapp.models import MyPayment  # مدل خودت (نه پکیج)

    order_id = "ORDER-2001"
    amount = 150_000  # ریال
    callback_url = request.build_absolute_uri(
        reverse("mypay-callback", kwargs={"slug": "zarinpal"})
    )

    record = MyPayment.objects.create(
        gateway_slug="zarinpal",
        order_id=order_id,
        amount=amount,
        callback_url=callback_url,
        status="waiting",
    )

    gw = get_gateway("zarinpal")  # sandbox از settings همین درگاه خوانده می‌شود
    try:
        result = gw.initiate(
            PaymentRequest(amount=amount, callback_url=callback_url, order_id=order_id)
        )
    except GatewayError as e:
        record.status = "failed"
        record.error_message = str(e)
        record.save()
        return HttpResponse(f"خطا در اتصال به زرین‌پال: {e}", status=502)

    record.authority = result.authority  # ← برای پیدا کردن رکورد در callback
    record.amount_sent = result.amount_to_send  # ← مرجع یکتا برای verify
    record.status = "redirect"
    record.save()
    return HttpResponseRedirect(result.redirect_url)


def callback_self_managed(request):
    """حالت ۲ زرین‌پال — verify و به‌روزرسانی مدل خودت."""
    from yourapp.models import MyPayment

    authority = request.GET.get("Authority")
    if not authority:
        return HttpResponse("Authority در callback نبود.", status=400)

    record = MyPayment.objects.filter(
        gateway_slug="zarinpal", authority=authority
    ).first()
    if record is None:
        return HttpResponse("رکورد یافت نشد.", status=404)
    if record.status == "complete":  # idempotent
        return HttpResponse("قبلاً تأیید شده.")

    gw = get_gateway("zarinpal")
    result = gw.verify(
        authority=authority,
        amount=record.amount_sent,  # ← نه record.amount
        order_id=record.order_id,
    )

    if result.is_success:
        record.status = "complete"
        record.reference_id = result.reference_id or ""
        record.card_number = result.card_number or ""
        record.save()
        return HttpResponse(f"پرداخت موفق! کد پیگیری: {record.reference_id}")
    record.status = "failed"
    record.error_message = result.error_message or ""
    record.save()
    return HttpResponse(f"پرداخت ناموفق: {record.error_message}")


if __name__ == "__main__":
    print(
        "این فایل یک راهنمای یکپارچه‌سازی Django است.\n"
        "کد view ها را در views.py app خودت کپی کن.\n"
        "برای تست sandbox core: uv run python scripts/test_zarinpal.py"
    )
