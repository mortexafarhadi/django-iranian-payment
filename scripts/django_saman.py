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
        "currency": "rial",   # واحد ورودی مبلغ: "rial" (پیش‌فرض) یا "toman"
        "sandbox": False,   # پیش‌فرض سراسری
        "gateways": {
            "saman": {
                "terminal_id": "123456789",  # شماره ترمینال از پرداخت الکترونیک سامان
                # اختیاری: "redirect_url" برای neo-pg (X-IPG-Url header)
                # "redirect_url": "https://sep.shaparak.ir/OnlinePG/SendToken",
                # ⚠️ ویژه‌ی سامان: URL سندباکس جدا ندارد؛ فلگ "sandbox" برای سامان
                # بی‌اثر است. تست با ترمینال واقعی روی همان آدرس عملیاتی انجام می‌شود.
            },
        },
    }

    # sandbox مجزای هر درگاه: برای درگاه‌هایی که URL سندباکس جدا دارند
    # (زرین‌پال/ملت/دیجی‌پی) کلید "sandbox" داخل config درگاه بر مقدار سراسری
    # اولویت دارد. سامان از این قاعده مستثناست (بالا را ببین).

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


# ═════════════════════════════════════════════════════════════
#  سامان — دو حالت مدیریت دیتابیس
# ═════════════════════════════════════════════════════════════
#
# حالت ۱ (پکیج DB را مدیریت می‌کند): همان checkout/payment_result بالا.
#
# حالت ۲ (خودت DB را مدیریت می‌کنی): کد زیر. مشخصات سامان در این حالت:
#   • هدایت: GET ساده به redirect_url (مستند POST توصیه می‌کند ولی پیاده‌سازی GET).
#   • callback: POST — سامان State, Status, RefNum, ResNum, RRN می‌فرستد.
#   • ⚠️ مهم: callback توکن (authority) را برنمی‌گرداند! رکوردت را با
#     order_id(==ResNum که خودت فرستادی) پیدا کن، نه با authority.
#   • verify به Token نیاز ندارد بلکه به RefNum؛ extra={"ref_num": RefNum,
#     "state": State} بده. یکتایی RefNum مسئولیت توست (سامان یک RefNum را بارها
#     verify می‌کند) — پس idempotency (چک status=="complete") حیاتی است.
#   • amount در verify باید amount_sent ذخیره‌شده باشد، نه مبلغ پایه.
# مدل نمونه‌ی MyPayment و توضیح کامل در scripts/django_custom_db.py است.

from django_iranian_payment import get_gateway
from django_iranian_payment.core.models import PaymentRequest


def checkout_self_managed(request):
    """حالت ۲ سامان — شروع پرداخت با مدل خودت (MyPayment)."""
    from yourapp.models import MyPayment

    order_id = "SAMAN-ORDER-001"  # همین به‌عنوان ResNum می‌رود و در callback برمی‌گردد
    amount = 300_000  # ریال
    callback_url = request.build_absolute_uri(
        reverse("mypay-callback", kwargs={"slug": "saman"})
    )

    record = MyPayment.objects.create(
        gateway_slug="saman",
        order_id=order_id,
        amount=amount,
        callback_url=callback_url,
        status="waiting",
    )

    gw = get_gateway("saman")
    try:
        result = gw.initiate(
            PaymentRequest(amount=amount, callback_url=callback_url, order_id=order_id)
        )
    except GatewayError as e:
        record.status = "failed"
        record.error_message = str(e)
        record.save()
        return HttpResponse(f"خطا در اتصال به سامان: {e}", status=502)

    record.authority = result.authority  # Token (در callback برنمی‌گردد، ولی نگه‌دار)
    record.amount_sent = result.amount_to_send
    record.status = "redirect"
    record.save()
    return HttpResponseRedirect(result.redirect_url)


def callback_self_managed(request):
    """حالت ۲ سامان — پیدا کردن رکورد با ResNum، verify با RefNum از POST."""
    from yourapp.models import MyPayment

    p = request.POST
    res_num = p.get("ResNum")  # == order_id ما
    if not res_num:
        return HttpResponse("ResNum در callback نبود.", status=400)

    record = MyPayment.objects.filter(gateway_slug="saman", order_id=res_num).first()
    if record is None:
        return HttpResponse("رکورد یافت نشد.", status=404)
    if record.status == "complete":  # idempotency حیاتی برای سامان
        return HttpResponse("قبلاً تأیید شده.")

    gw = get_gateway("saman")
    result = gw.verify(
        authority=record.authority,
        amount=record.amount_sent,  # ← نه record.amount
        order_id=record.order_id,
        extra={"ref_num": p.get("RefNum"), "state": p.get("State")},
    )

    if result.is_success:
        record.status = "complete"
        record.reference_id = result.reference_id or ""  # RRN
        record.card_number = result.card_number or ""
        record.save()
        return HttpResponse(f"پرداخت موفق! RefNum/RRN: {record.reference_id}")
    record.status = "failed"
    record.error_message = result.error_message or ""
    record.save()
    return HttpResponse(f"پرداخت ناموفق: {record.error_message}")


if __name__ == "__main__":
    print(
        "این فایل راهنمای Django درگاه سامان است.\n"
        "برای تست sandbox: uv run python scripts/test_saman.py\n"
        "⚠️  نیاز به TerminalId واقعی و IP ثبت‌شده نزد سامان."
    )
