"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 راهنمای کامل استفاده از درگاه ملت (به‌پرداخت) در Django
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ملت از پروتکل SOAP (zeep) استفاده می‌کند و یک ویژگی مهم دارد:
کاربر باید با فرم HTML (POST) به صفحه‌ی پرداخت فرستاده شود، نه redirect ساده.
پکیج این فرم را به‌صورت خودکار در view go_to_gateway می‌سازد.

⚠️ وضعیت: تجربی (experimental) — کد کامل از مستند نگارش ۱.۳۸، ولی هنوز با
ترمینال/sandbox واقعی تأیید نشده. برای استفاده در production نیاز به:
  ۱. قرارداد پذیرندگی با بانک ملت
  ۲. ثبت IP سرور نزد ملت (نامه‌ی رسمی)
  ۳. دسترسی شبکه به bpm.shaparak.ir از داخل ایران

━━ قدم ۱: نصب پکیج و وابستگی SOAP ━━━━━━━━━━━━━━━━━━━━━━━━━

    pip install "django-iranian-payment[soap]"
    # zeep برای ارتباط SOAP نیاز است

━━ قدم ۲: تنظیمات settings.py ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    INSTALLED_APPS = [
        ...
        "django_iranian_payment.contrib.django",
    ]

    TEMPLATES = [
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": [],
            "APP_DIRS": True,   # ← لازم است تا template فرم POST پیدا شود
            "OPTIONS": {"context_processors": [...]},
        }
    ]

    IRANIAN_PAYMENT = {
        "sandbox": True,   # False در production (bpm.shaparak.ir)
        "gateways": {
            "mellat": {
                "terminal_id": "1234567",        # شماره ترمینال از ملت
                "username": "your-username",     # نام کاربری از ملت
                "password": "your-password",     # رمز از ملت
                "settle_mode": "verify_settle",  # توصیه: تأیید+واریز اتمیک
                # یا "verify_only" برای verify جداگانه (نیاز به settle() بعداً)
            },
        },
    }

━━ قدم ۳: ثبت درگاه ملت در registry پکیج ━━━━━━━━━━━━━━━━━━

    ملت در registry عمومی نیست (تجربی است). برای استفاده از لایه‌ی Django
    پکیج (services) باید آن را موقتاً register کنی. این کار را در
    AppConfig.ready() app خودت انجام بده:

    # yourapp/apps.py
    from django.apps import AppConfig

    class YourAppConfig(AppConfig):
        name = "yourapp"

        def ready(self):
            # ثبت درگاه ملت در registry پکیج
            from django_iranian_payment.core.gateways import _REGISTRY
            from django_iranian_payment.core.experimental.mellat import MellatGateway
            _REGISTRY["mellat"] = MellatGateway

━━ قدم ۴: URL های پکیج ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # project/urls.py
    urlpatterns = [
        ...
        path("payment/", include("django_iranian_payment.contrib.django.urls")),
    ]

    # مسیرهای ساخته‌شده:
    #   GET  /payment/go/<payment_id>/           → صفحه‌ی فرم POST به ملت
    #   POST /payment/callback/mellat/           → برگشت از بانک (POST)

━━ قدم ۵: callBackUrl در ملت ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    ملت callBackUrl را باید ثبت کنی:
        https://yoursite.com/payment/callback/mellat/

    ملت بعد از پرداخت با POST برمی‌گردد و این فیلدها را می‌فرستد:
        RefId, ResCode, SaleOrderId, SaleReferenceId

    پکیج SaleReferenceId و SaleOrderId را از POST می‌خواند و به verify می‌دهد.

━━ نکات مهم ملت ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • برخلاف زرین‌پال، هدایت کاربر به ملت با فرم POST است (نه redirect ساده).
    پکیج view go_to_gateway را به‌صورت خودکار فرم auto-submit می‌سازد.
  • کاربر را به /payment/go/<payment_id>/ بفرست — پکیج بقیه را مدیریت می‌کند.
  • verify_settle پیش‌فرض است: تأیید و واریز اتمیک در یک فراخوانی.
  • در verify_only: بعد از verify باید settle() را هم صدا بزنی وگرنه پول در
    ۳ ساعت به مشتری برمی‌گردد (Autoreversal).
"""

from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse

from django_iranian_payment.contrib.django.services import start_payment, verify_payment
from django_iranian_payment.contrib.django.models import Payment, PaymentStatus
from django_iranian_payment.core.exceptions import GatewayError


def checkout(request):
    """
    شروع پرداخت با ملت.

    بعد از start_payment، کاربر را به /payment/go/<id>/ بفرست.
    آن view صفحه‌ی فرم POST به ملت را می‌سازد و ارسال می‌کند.
    """
    order_id = "1001"  # ملت orderId عددی می‌خواهد (یکتا)
    amount = 500_000  # ریال

    # ⚠️ مهم: callback باید آدرس کاملِ /payment/callback/mellat/ باشد
    # و در سیستم ملت ثبت شده باشد
    callback_url = request.build_absolute_uri(
        reverse("iranian_payment:callback", kwargs={"slug": "mellat"})
    )

    try:
        payment, _ = start_payment(
            slug="mellat",
            amount=amount,
            callback_url=callback_url,
            order_id=order_id,
            description="خرید از فروشگاه",
        )
    except GatewayError as e:
        return HttpResponse(f"خطا در اتصال به ملت: {e}", status=502)

    # کاربر را به view go_to_gateway بفرست — این view فرم POST auto-submit می‌سازد
    return HttpResponseRedirect(
        reverse("iranian_payment:go-to-gateway", kwargs={"payment_id": payment.id})
    )


def payment_result(request):
    """
    نتیجه‌ی پرداخت پس از callback ملت.

    پکیج بعد از verify، با payment_status=success/failed به callback_url
    سفارش redirect می‌کند.
    """
    status = request.GET.get("payment_status")
    order_id = request.GET.get("order_id", "")

    if status == "success":
        payment = Payment.objects.filter(
            order_id=order_id, status=PaymentStatus.COMPLETE
        ).first()
        if payment:
            return HttpResponse(
                f"پرداخت ملت موفق! " f"شماره پیگیری: {payment.reference_id}"
            )
    elif status == "failed":
        payment = Payment.objects.filter(order_id=order_id).first()
        err = payment.error_message if payment else ""
        return HttpResponse(f"پرداخت ناموفق. {err}")

    return HttpResponse("نتیجه نامشخص.", status=400)


# ─────────────────────────────────────────────────────────────
#  نمونه‌ی settle() برای حالت verify_only
# ─────────────────────────────────────────────────────────────
#
# اگر settle_mode = "verify_only" باشد، بعد از موفق شدن verify باید
# settle بزنی تا پول واریز شود. این کار را در یک task/celery انجام بده:
#
#   from django_iranian_payment import get_gateway
#
#   def settle_mellat_payment(order_id, sale_order_id, sale_reference_id):
#       gw = get_gateway("mellat")
#       result = gw.settle(
#           order_id=order_id,
#           sale_order_id=sale_order_id,
#           sale_reference_id=sale_reference_id,
#       )
#       return result.is_success
#
# ─────────────────────────────────────────────────────────────
#  نمونه‌ی reverse() برای برگشت وجه
# ─────────────────────────────────────────────────────────────
#
# اگر بعد از verify وضعیت مشخص نشد یا می‌خواهی پول برگردد:
#
#   from django_iranian_payment import get_gateway
#
#   def reverse_mellat_payment(order_id, sale_order_id, sale_reference_id):
#       gw = get_gateway("mellat")
#       result = gw.reverse(
#           order_id=order_id,
#           sale_order_id=sale_order_id,
#           sale_reference_id=sale_reference_id,
#       )
#       return result.is_success


if __name__ == "__main__":
    print(
        "این فایل راهنمای یکپارچه‌سازی Django درگاه ملت است.\n"
        "برای تست sandbox core: uv run python scripts/test_mellat.py\n"
        "⚠️  تست sandbox ملت نیاز به IP ثبت‌شده نزد بانک دارد."
    )
