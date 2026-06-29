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
        "currency": "rial",   # واحد ورودی مبلغ: "rial" (پیش‌فرض) یا "toman"
        "sandbox": False,   # پیش‌فرض سراسری
        "gateways": {
            "sadad": {
                "merchant_id": "1234",          # شناسه پذیرنده از سداد
                "terminal_id": "5678",          # شناسه ترمینال از سداد
                "terminal_key": "BASE64_KEY==", # کلید پذیرنده به‌صورت Base64
                # کلید را از پورتال سداد (https://sadad.shaparak.ir) بگیر.
                # بعد از دیکد باید ۱۶ یا ۲۴ بایت باشد (3DES).
                # ⚠️ ویژه‌ی سداد: URL سندباکس جدا ندارد؛ فلگ "sandbox" بی‌اثر است.
            },
        },
    }

    # sandbox مجزای هر درگاه: کلید "sandbox" داخل config درگاه بر مقدار سراسری
    # اولویت دارد — برای درگاه‌هایی که URL سندباکس جدا دارند. سداد مستثناست.

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


# ═════════════════════════════════════════════════════════════
#  سداد — دو حالت مدیریت دیتابیس
# ═════════════════════════════════════════════════════════════
#
# حالت ۱ (پکیج DB را مدیریت می‌کند): همان checkout/payment_result بالا.
#
# حالت ۲ (خودت DB را مدیریت می‌کنی): کد زیر. مشخصات سداد در این حالت:
#   • هدایت: GET ساده به Purchase?Token=<token>.
#   • callback: POST — سداد Token و ResCode و OrderId را برمی‌گرداند.
#   • رکوردت را با authority(==Token) پیدا کن (OrderId هم برمی‌گردد).
#   • verify خودش با Token کار می‌کند؛ extra اختیاری است: اگر ResCode را بدهی و
#     ناموفق باشد، بدون تماس با بانک نتیجه‌ی ناموفق می‌گیری.
#   • ⚠️ verify باید ظرف ۱۵ دقیقه زده شود وگرنه مبلغ برمی‌گردد.
#   • amount در verify باید amount_sent ذخیره‌شده باشد، نه مبلغ پایه.
# مدل نمونه‌ی MyPayment و توضیح کامل در scripts/django_custom_db.py است.

from django_iranian_payment import get_gateway
from django_iranian_payment.core.models import PaymentRequest


def checkout_self_managed(request):
    """حالت ۲ سداد — شروع پرداخت با مدل خودت (MyPayment)."""
    from yourapp.models import MyPayment

    order_id = "5001"  # سداد order_id عددی می‌خواهد
    amount = 400_000  # ریال
    callback_url = request.build_absolute_uri(
        reverse("mypay-callback", kwargs={"slug": "sadad"})
    )

    record = MyPayment.objects.create(
        gateway_slug="sadad",
        order_id=order_id,
        amount=amount,
        callback_url=callback_url,
        status="waiting",
    )

    gw = get_gateway("sadad")
    try:
        result = gw.initiate(
            PaymentRequest(amount=amount, callback_url=callback_url, order_id=order_id)
        )
    except GatewayError as e:
        record.status = "failed"
        record.error_message = str(e)
        record.save()
        return HttpResponse(f"خطا در اتصال به سداد: {e}", status=502)

    record.authority = result.authority  # Token
    record.amount_sent = result.amount_to_send
    record.status = "redirect"
    record.save()
    return HttpResponseRedirect(result.redirect_url)


def callback_self_managed(request):
    """حالت ۲ سداد — verify با Token از POST و به‌روزرسانی مدل خودت."""
    from yourapp.models import MyPayment

    p = request.POST
    token = p.get("Token")
    if not token:
        return HttpResponse("Token در callback نبود.", status=400)

    record = MyPayment.objects.filter(gateway_slug="sadad", authority=token).first()
    if record is None:
        return HttpResponse("رکورد یافت نشد.", status=404)
    if record.status == "complete":
        return HttpResponse("قبلاً تأیید شده.")

    gw = get_gateway("sadad")
    extra = {"res_code": p.get("ResCode")} if p.get("ResCode") else None
    result = gw.verify(
        authority=token,
        amount=record.amount_sent,  # ← نه record.amount
        order_id=record.order_id,
        extra=extra,
    )

    if result.is_success:
        record.status = "complete"
        record.reference_id = result.reference_id or ""  # RetrivalRefNo
        record.card_number = result.card_number or ""
        record.save()
        return HttpResponse(f"پرداخت سداد موفق! کد پیگیری: {record.reference_id}")
    record.status = "failed"
    record.error_message = result.error_message or ""
    record.save()
    return HttpResponse(f"پرداخت ناموفق: {record.error_message}")


if __name__ == "__main__":
    print(
        "این فایل راهنمای Django درگاه سداد (بانک ملی) است.\n"
        "برای تست sandbox: uv run python scripts/test_sadad.py\n"
        "⚠️  نیاز به MerchantId، TerminalId، TerminalKey و IP ثبت‌شده."
    )
