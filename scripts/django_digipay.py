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
        "currency": "rial",   # واحد ورودی مبلغ: "rial" (پیش‌فرض) یا "toman"
        "sandbox": False,   # پیش‌فرض سراسری
        "gateways": {
            "digipay": {
                "username": "your-username",          # از پورتال دیجی‌پی
                "password": "your-password",          # از پورتال دیجی‌پی
                "client_id": "your-client-id",        # OAuth2 client
                "client_secret": "your-client-secret",
                "provider_id": "your-provider-id",    # شناسه‌ی کسب‌وکار شما
                "sandbox": True,   # ← sandbox مجزای دیجی‌پی (uat.mydigipay.info)
                # دیجی‌پی URL سندباکس واقعی دارد؛ True اینجا این درگاه را روی UAT
                # می‌برد حتی اگر sandbox سراسری False باشد.
                # اختیاری:
                # "ticket_type": 11,   # پیش‌فرض ۱۱ (UPG). انواع دیگر: ۳۸ (QR)
            },
        },
    }

    # sandbox مجزای هر درگاه: کلید "sandbox" داخل config درگاه بر مقدار سراسری
    # اولویت دارد (اولویت کامل: آرگومان get_gateway > config درگاه > سراسری > False).

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
from django_iranian_payment.core.exceptions import GatewayError, GatewayConnectionError


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

    elif status == "pending":
        # درگاه هنگام verify در دسترس نبود؛ رکورد معلق مانده و reverify_pending بعداً تمامش می‌کند.
        return HttpResponse(
            f"پرداخت شما در حال بررسی است (سفارش {order_id}). نتیجه به‌زودی مشخص می‌شود."
        )
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


# ═════════════════════════════════════════════════════════════
#  دیجی‌پی — دو حالت مدیریت دیتابیس
# ═════════════════════════════════════════════════════════════
#
# حالت ۱ (پکیج DB را مدیریت می‌کند): همان checkout/payment_result بالا.
#
# حالت ۲ (خودت DB را مدیریت می‌کنی): کد زیر. مشخصات دیجی‌پی در این حالت:
#   • هدایت: GET ساده به redirect_url (که از پاسخ API خوانده می‌شود، نه ساخته).
#   • callback: دیجی‌پی trackingCode, providerId, result را برمی‌گرداند.
#   • ⚠️ مهم: callback ticket (authority) را برنمی‌گرداند! رکوردت را با
#     order_id(==providerId که خودت فرستادی) پیدا کن، نه با authority.
#   • verify به trackingCode نیاز دارد و providerId را دوباره می‌فرستد (پکیج
#     providerId را از order_id می‌گیرد). extra={"tracking_code": trackingCode,
#     "result": result}.
#   • amount در verify باید amount_sent ذخیره‌شده باشد، نه مبلغ پایه.
# مدل نمونه‌ی MyPayment و توضیح کامل در scripts/django_custom_db.py است.

from django_iranian_payment import get_gateway
from django_iranian_payment.core.models import PaymentRequest


def checkout_self_managed(request):
    """حالت ۲ دیجی‌پی — شروع پرداخت با مدل خودت (MyPayment)."""
    from yourapp.models import MyPayment

    order_id = "DIGIPAY-ORDER-001"  # همین به‌عنوان providerId در callback برمی‌گردد
    amount = 350_000  # ریال
    callback_url = request.build_absolute_uri(
        reverse("mypay-callback", kwargs={"slug": "digipay"})
    )

    record = MyPayment.objects.create(
        gateway_slug="digipay",
        order_id=order_id,
        amount=amount,
        callback_url=callback_url,
        status="waiting",
    )

    gw = get_gateway("digipay")
    try:
        result = gw.initiate(
            PaymentRequest(amount=amount, callback_url=callback_url, order_id=order_id)
        )
    except GatewayError as e:
        record.status = "failed"
        record.error_message = str(e)
        record.save()
        return HttpResponse(f"خطا در اتصال به دیجی‌پی: {e}", status=502)

    record.authority = result.authority  # ticket (در callback برنمی‌گردد، ولی نگه‌دار)
    record.amount_sent = result.amount_to_send
    record.status = "redirect"
    record.save()
    return HttpResponseRedirect(result.redirect_url)


def callback_self_managed(request):
    """حالت ۲ دیجی‌پی — پیدا کردن رکورد با providerId، verify با trackingCode."""
    from yourapp.models import MyPayment

    params = request.POST if request.method == "POST" else request.GET
    provider_id = params.get("providerId")  # == order_id ما
    if not provider_id:
        return HttpResponse("providerId در callback نبود.", status=400)

    record = MyPayment.objects.filter(
        gateway_slug="digipay", order_id=provider_id
    ).first()
    if record is None:
        return HttpResponse("رکورد یافت نشد.", status=404)
    if record.status == "complete":
        return HttpResponse("قبلاً تأیید شده.")

    extra = {
        k: v
        for k, v in {
            "tracking_code": params.get("trackingCode"),
            "result": params.get("result"),
        }.items()
        if v
    }

    # پیش‌علامت: «returned» + ذخیره‌ی extra در raw، پیش از تماس با بانک، تا خطای شبکه
    # رکورد را گم نکند و reverify_pending با همین extra بعداً بگیردش.
    record.status = "returned"
    record.raw = {**(record.raw or {}), "callback_extra": extra}
    record.save(update_fields=["status", "raw", "updated_at"])

    gw = get_gateway("digipay")
    try:
        result = gw.verify(
            authority=record.authority,
            amount=record.amount_sent,  # ← نه record.amount
            order_id=record.order_id,  # == providerId برای verify
            extra=extra,
        )
    except GatewayConnectionError:
        # درگاه در دسترس نیست؛ رکورد «returned» می‌ماند، reverify_pending بعداً verify می‌زند.
        return HttpResponse(
            f"پرداخت شما در حال بررسی است (سفارش {record.order_id}).", status=202
        )

    if result.is_success:
        record.status = "complete"
        record.reference_id = result.reference_id or ""  # rrn
        record.save()
        return HttpResponse(f"پرداخت موفق! کد پیگیری: {record.reference_id}")
    record.status = "failed"
    record.error_message = result.error_message or ""
    record.save()
    return HttpResponse(f"پرداخت ناموفق: {record.error_message}")


def reverify_pending():
    """رکوردهای معلق (درگاه در callback بی‌پاسخ داده بود) را دوباره verify می‌کند. cron."""
    from yourapp.models import MyPayment

    for record in MyPayment.objects.filter(gateway_slug="digipay", status="returned"):
        extra = (record.raw or {}).get("callback_extra")
        try:
            result = get_gateway("digipay").verify(
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
            record.save()
        else:
            record.status = "failed"
            record.error_message = result.error_message or ""
            record.save()


if __name__ == "__main__":
    print(
        "این فایل راهنمای Django درگاه دیجی‌پی است.\n"
        "برای تست sandbox: uv run python scripts/test_digipay.py\n"
        "⚠️  نیاز به اعتبارنامه‌ی کامل از پورتال دیجی‌پی."
    )
