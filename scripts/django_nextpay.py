"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 راهنمای کامل استفاده از درگاه نکست‌پی در Django
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

نکست‌پی (NextPay) یک درگاه پرداخت اینترنتی با REST API است که برای SME ها و
استارت‌آپ‌ها محبوب است.

⚠️ وضعیت: تجربی (experimental) — کد از مستند رسمی، sandbox هنوز تأیید نشده.
نیاز به api_key واقعی و دامنه ثبت‌شده در پنل نکست‌پی.

━━ قدم ۱: نصب ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    pip install django-iranian-payment

━━ قدم ۲: تنظیمات settings.py ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    INSTALLED_APPS = [
        ...
        "django_iranian_payment.contrib.django",
    ]

    IRANIAN_PAYMENT = {
        "currency": "rial",   # واحد ورودی مبلغ: "rial" (پیش‌فرض) یا "toman"
        "sandbox": False,   # پیش‌فرض سراسری
        "gateways": {
            "nextpay": {
                "api_key": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                # api_key را از پنل نکست‌پی (https://nextpay.org) بگیر.
                # هنگام ثبت، دامنه/IP سرورت را وارد کن وگرنه code=-33 می‌گیری.
                # ⚠️ ویژه‌ی نکست‌پی: URL سندباکس جدا ندارد؛ فلگ "sandbox" بی‌اثر است.
            },
        },
    }

    # sandbox مجزای هر درگاه: کلید "sandbox" داخل config درگاه بر مقدار سراسری
    # اولویت دارد — برای درگاه‌هایی که URL سندباکس جدا دارند. نکست‌پی مستثناست.

━━ قدم ۳: ثبت درگاه در registry ━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # yourapp/apps.py
    class YourAppConfig(AppConfig):
        name = "yourapp"

        def ready(self):
            from django_iranian_payment.core.gateways import _REGISTRY
            from django_iranian_payment.core.experimental.nextpay import NextPayGateway
            _REGISTRY["nextpay"] = NextPayGateway

━━ قدم ۴: URL های پکیج ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    urlpatterns = [
        ...
        path("payment/", include("django_iranian_payment.contrib.django.urls")),
    ]

    # مسیرها:
    #   GET  /payment/go/<payment_id>/       → هدایت به درگاه
    #   GET  /payment/callback/nextpay/      → برگشت از بانک (GET)

━━ نکات مهم نکست‌پی ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • واحد ارز: پکیج ریال می‌فرستد (currency=IRR). در پنل نکست‌پی مبلغ‌ها
    به تومان نمایش داده می‌شوند — این طبیعی است (تبدیل سمت نکست‌پی).
  • کد موفقیت ساخت توکن code=-1 است (عجیب ولی طبق مستند رسمی).
    کد code=0 یعنی ناموفق.
  • trans_id در callback GET: /callback/nextpay/?trans_id=<id>&order_id=...&amount=...
  • کدهای DUPLICATE: code=-25 و code=-49 (قبلاً تأیید شده).
  • نکست‌پی refund() هم دارد (بازگشت وجه پس از verify).
"""

from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse

from django_iranian_payment.contrib.django.services import start_payment
from django_iranian_payment.contrib.django.models import Payment, PaymentStatus
from django_iranian_payment.core.exceptions import GatewayError


def checkout(request):
    """
    شروع پرداخت با نکست‌پی.
    callback با GET برمی‌گردد و trans_id را می‌فرستد.
    """
    order_id = "NP-ORDER-001"
    amount = 180_000  # ریال (نکست‌پی آن را به تومان نمایش می‌دهد)

    callback_url = request.build_absolute_uri(
        reverse("iranian_payment:callback", kwargs={"slug": "nextpay"})
    )

    try:
        payment, redirect_url = start_payment(
            slug="nextpay",
            amount=amount,
            callback_url=callback_url,
            order_id=order_id,
            description="خرید آنلاین",
            mobile="09120000000",  # اختیاری
        )
    except GatewayError as e:
        return HttpResponse(f"خطا در اتصال به نکست‌پی: {e}", status=502)

    request.session["pending_payment_id"] = payment.id

    # کاربر را به درگاه نکست‌پی هدایت کن (GET redirect ساده)
    return HttpResponseRedirect(redirect_url)


def payment_result(request):
    """نتیجه‌ی پرداخت نکست‌پی."""
    status = request.GET.get("payment_status")
    order_id = request.GET.get("order_id", "")

    if status == "success":
        payment = Payment.objects.filter(
            order_id=order_id, status=PaymentStatus.COMPLETE
        ).first()
        if payment:
            return HttpResponse(f"پرداخت موفق! شماره پیگیری: {payment.reference_id}")
    elif status == "failed":
        return HttpResponse("پرداخت ناموفق.")

    return HttpResponse("وضعیت نامشخص.", status=400)


# ─────────────────────────────────────────────────────────────
#  استرداد وجه (refund) نکست‌پی
# ─────────────────────────────────────────────────────────────
#
# نکست‌پی برخلاف درگاه‌های دیگر، متد refund() دارد:
#
#   from django_iranian_payment import get_gateway
#
#   def refund_nextpay(trans_id, amount):
#       gw = get_gateway("nextpay")
#       result = gw.refund(trans_id=trans_id, amount=amount)
#       return result.is_success


# ═════════════════════════════════════════════════════════════
#  نکست‌پی — دو حالت مدیریت دیتابیس
# ═════════════════════════════════════════════════════════════
#
# حالت ۱ (پکیج DB را مدیریت می‌کند): همان checkout/payment_result بالا.
#
# حالت ۲ (خودت DB را مدیریت می‌کنی): کد زیر. مشخصات نکست‌پی در این حالت:
#   • هدایت: GET ساده به redirect_url.
#   • callback: GET — نکست‌پی trans_id, order_id, amount را برمی‌گرداند.
#   • authority همان trans_id است؛ رکوردت را با authority(==trans_id) پیدا کن.
#   • verify هیچ extra لازم ندارد.
#   • amount در verify باید amount_sent ذخیره‌شده باشد، نه مبلغ پایه.
# مدل نمونه‌ی MyPayment و توضیح کامل در scripts/django_custom_db.py است.

from django_iranian_payment import get_gateway
from django_iranian_payment.core.models import PaymentRequest


def checkout_self_managed(request):
    """حالت ۲ نکست‌پی — شروع پرداخت با مدل خودت (MyPayment)."""
    from yourapp.models import MyPayment

    order_id = "NP-ORDER-001"
    amount = 180_000  # ریال
    callback_url = request.build_absolute_uri(
        reverse("mypay-callback", kwargs={"slug": "nextpay"})
    )

    record = MyPayment.objects.create(
        gateway_slug="nextpay",
        order_id=order_id,
        amount=amount,
        callback_url=callback_url,
        status="waiting",
    )

    gw = get_gateway("nextpay")
    try:
        result = gw.initiate(
            PaymentRequest(amount=amount, callback_url=callback_url, order_id=order_id)
        )
    except GatewayError as e:
        record.status = "failed"
        record.error_message = str(e)
        record.save()
        return HttpResponse(f"خطا در اتصال به نکست‌پی: {e}", status=502)

    record.authority = result.authority  # trans_id
    record.amount_sent = result.amount_to_send
    record.status = "redirect"
    record.save()
    return HttpResponseRedirect(result.redirect_url)


def callback_self_managed(request):
    """حالت ۲ نکست‌پی — verify و به‌روزرسانی مدل خودت."""
    from yourapp.models import MyPayment

    trans_id = request.GET.get("trans_id")
    if not trans_id:
        return HttpResponse("trans_id در callback نبود.", status=400)

    record = MyPayment.objects.filter(
        gateway_slug="nextpay", authority=trans_id
    ).first()
    if record is None:
        return HttpResponse("رکورد یافت نشد.", status=404)
    if record.status == "complete":
        return HttpResponse("قبلاً تأیید شده.")

    gw = get_gateway("nextpay")
    result = gw.verify(
        authority=trans_id,
        amount=record.amount_sent,  # ← نه record.amount
        order_id=record.order_id,
    )

    if result.is_success:
        record.status = "complete"
        record.reference_id = result.reference_id or ""
        record.card_number = result.card_number or ""
        record.save()
        return HttpResponse(f"پرداخت موفق! شماره پیگیری: {record.reference_id}")
    record.status = "failed"
    record.error_message = result.error_message or ""
    record.save()
    return HttpResponse(f"پرداخت ناموفق: {record.error_message}")


if __name__ == "__main__":
    print(
        "این فایل راهنمای Django درگاه نکست‌پی است.\n"
        "برای تست sandbox: uv run python scripts/test_nextpay.py\n"
        "⚠️  نیاز به api_key واقعی و دامنه ثبت‌شده در پنل نکست‌پی."
    )
