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
        "currency": "rial",   # واحد ورودی مبلغ: "rial" (پیش‌فرض) یا "toman"
        "sandbox": False,   # پیش‌فرض سراسری
        "gateways": {
            "irankish": {
                "terminal_id": "xxxxxxxx",       # hex — از ایران‌کیش
                "acceptor_id": "xxxxxxxx",       # hex — از ایران‌کیش
                "pass_phrase": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",  # hex ۳۲+ کاراکتر
                "public_key": "/path/to/irankish_public.pem",  # مسیر کلید RSA بانک
                # ⚠️ ویژه‌ی ایران‌کیش: URL سندباکس جدا ندارد؛ فلگ "sandbox" بی‌اثر است.
            },
        },
    }

    # sandbox مجزای هر درگاه: کلید "sandbox" داخل config درگاه بر مقدار سراسری
    # اولویت دارد — برای درگاه‌هایی که URL سندباکس جدا دارند. ایران‌کیش مستثناست.

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
from django_iranian_payment.core.exceptions import GatewayError, GatewayConnectionError


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

    elif status == "pending":
        # درگاه هنگام verify در دسترس نبود؛ رکورد معلق مانده و reverify_pending بعداً تمامش می‌کند.
        return HttpResponse(
            f"پرداخت شما در حال بررسی است (سفارش {order_id}). نتیجه به‌زودی مشخص می‌شود."
        )
    return HttpResponse("وضعیت نامشخص.", status=400)


# ═════════════════════════════════════════════════════════════
#  ایران‌کیش — دو حالت مدیریت دیتابیس
# ═════════════════════════════════════════════════════════════
#
# حالت ۱ (پکیج DB را مدیریت می‌کند): همان checkout/payment_result بالا.
#
# حالت ۲ (خودت DB را مدیریت می‌کنی): کد زیر. مشخصات ایران‌کیش در این حالت:
#   • هدایت: redirect_url آماده (GET). مستند بانک فرم POST با فیلد tokenIdentity
#     توصیه می‌کند؛ اگر بانک به GET ساده ایراد گرفت، مثل ملت فرم POST بساز.
#   • callback: POST — ایران‌کیش resultCode, token, referenceId می‌فرستد.
#   • رکوردت را با authority(==token) پیدا کن.
#   • verify به هر دو token و referenceId نیاز دارد:
#     extra={"reference_id": referenceId, "token": token, "result_code": resultCode}.
#   • amount در verify باید amount_sent ذخیره‌شده باشد، نه مبلغ پایه.
# مدل نمونه‌ی MyPayment و توضیح کامل در scripts/django_custom_db.py است.

from django_iranian_payment import get_gateway
from django_iranian_payment.core.models import PaymentRequest


def checkout_self_managed(request):
    """حالت ۲ ایران‌کیش — شروع پرداخت با مدل خودت (MyPayment)."""
    from yourapp.models import MyPayment

    order_id = "IK-ORDER-001"
    amount = 250_000  # ریال
    callback_url = request.build_absolute_uri(
        reverse("mypay-callback", kwargs={"slug": "irankish"})
    )

    record = MyPayment.objects.create(
        gateway_slug="irankish",
        order_id=order_id,
        amount=amount,
        callback_url=callback_url,
        status="waiting",
    )

    gw = get_gateway("irankish")
    try:
        result = gw.initiate(
            PaymentRequest(amount=amount, callback_url=callback_url, order_id=order_id)
        )
    except GatewayError as e:
        record.status = "failed"
        record.error_message = str(e)
        record.save()
        return HttpResponse(f"خطا در اتصال به ایران‌کیش: {e}", status=502)

    record.authority = result.authority  # token
    record.amount_sent = result.amount_to_send
    record.status = "redirect"
    record.save()
    return HttpResponseRedirect(result.redirect_url)


def callback_self_managed(request):
    """حالت ۲ ایران‌کیش — verify با token و referenceId از POST."""
    from yourapp.models import MyPayment

    p = request.POST
    token = p.get("token")
    if not token:
        return HttpResponse("token در callback نبود.", status=400)

    record = MyPayment.objects.filter(gateway_slug="irankish", authority=token).first()
    if record is None:
        return HttpResponse("رکورد یافت نشد.", status=404)
    if record.status == "complete":
        return HttpResponse("قبلاً تأیید شده.")

    extra = {
        k: v
        for k, v in {
            "reference_id": p.get("referenceId"),
            "token": token,
            "result_code": p.get("resultCode"),
        }.items()
        if v
    }

    # پیش‌علامت: «returned» + ذخیره‌ی extra در raw، پیش از تماس با بانک، تا خطای شبکه
    # رکورد را گم نکند و reverify_pending با همین extra بعداً بگیردش.
    record.status = "returned"
    record.raw = {**(record.raw or {}), "callback_extra": extra}
    record.save(update_fields=["status", "raw", "updated_at"])

    gw = get_gateway("irankish")
    try:
        result = gw.verify(
            authority=token,
            amount=record.amount_sent,  # ← نه record.amount
            order_id=record.order_id,
            extra=extra,
        )
    except GatewayConnectionError:
        # درگاه در دسترس نیست؛ رکورد «returned» می‌ماند، reverify_pending بعداً verify می‌زند.
        return HttpResponse(
            f"پرداخت شما در حال بررسی است (سفارش {record.order_id}).", status=202
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


def reverify_pending():
    """رکوردهای معلق (درگاه در callback بی‌پاسخ داده بود) را دوباره verify می‌کند. cron."""
    from yourapp.models import MyPayment

    for record in MyPayment.objects.filter(gateway_slug="irankish", status="returned"):
        extra = (record.raw or {}).get("callback_extra")
        try:
            result = get_gateway("irankish").verify(
                authority=record.authority,
                amount=record.amount_sent,
                order_id=record.order_id,
                extra=extra,
            )
        except GatewayConnectionError:
            continue  # هنوز در دسترس نیست؛ دفعه‌ی بعد
        if result.is_success:
            record.status = "complete"
            record.reference_id = result.reference_id or ""
            record.card_number = result.card_number or ""
            record.save()
        else:
            record.status = "failed"
            record.error_message = result.error_message or ""
            record.save()


if __name__ == "__main__":
    print(
        "این فایل راهنمای Django درگاه ایران‌کیش است.\n"
        "برای تست sandbox: uv run python scripts/test_irankish.py\n"
        "⚠️  نیاز به کلید RSA بانک، ترمینال واقعی و IP ثبت‌شده."
    )
