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
        "currency": "rial",   # واحد ورودی مبلغ: "rial" (پیش‌فرض) یا "toman"
        "sandbox": False,   # پیش‌فرض سراسری
        "gateways": {
            "mellat": {
                "terminal_id": "1234567",        # شماره ترمینال از ملت
                "username": "your-username",     # نام کاربری از ملت
                "password": "your-password",     # رمز از ملت
                "settle_mode": "verify_settle",  # توصیه: تأیید+واریز اتمیک
                # یا "verify_only" برای verify جداگانه (نیاز به settle() بعداً)
                "sandbox": True,   # ← sandbox مجزای ملت (pgw.dev.bpmellat.ir)
                # False = محیط عملیاتی (bpm.shaparak.ir). با این کلید می‌توانی ملت
                # را sandbox بگذاری و درگاه دیگری را live، هم‌زمان.
                # ⚠️ در عمل sandbox ملت پاسخ‌گو نبود؛ تست واقعی روی live انجام شد.
            },
        },
    }

    # sandbox مجزای هر درگاه: کلید "sandbox" داخل config درگاه بر مقدار سراسری
    # اولویت دارد (اولویت کامل: آرگومان get_gateway > config درگاه > سراسری > False).

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
from django_iranian_payment.core.exceptions import GatewayError, GatewayConnectionError


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

    elif status == "pending":
        # درگاه هنگام verify در دسترس نبود؛ رکورد معلق مانده و reverify_pending بعداً تمامش می‌کند.
        return HttpResponse(
            f"پرداخت شما در حال بررسی است (سفارش {order_id}). نتیجه به‌زودی مشخص می‌شود."
        )
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


# ═════════════════════════════════════════════════════════════
#  ملت — دو حالت مدیریت دیتابیس
# ═════════════════════════════════════════════════════════════
#
# حالت ۱ (پکیج DB را مدیریت می‌کند): همان checkout/payment_result بالا.
#   • کاربر را به /payment/go/<id>/ می‌فرستی؛ view پکیج فرم POST auto-submit را
#     می‌سازد (از template). callback پکیج SaleReferenceId/SaleOrderId را از POST
#     می‌خواند و verify می‌زند.
#
# حالت ۲ (خودت DB را مدیریت می‌کنی): کد زیر. ملت سخت‌ترین حالت است چون:
#   • هدایت: POST فرم (نه redirect ساده). result.redirect_method == "POST" و
#     result.redirect_fields == {"RefId": ...}. در حالت ۲ template پکیج در دسترس
#     نیست (اپ در INSTALLED_APPS نیست)، پس باید فرم auto-submit را خودت بسازی.
#   • callback: POST — ملت RefId, ResCode, SaleOrderId, SaleReferenceId و گاهی
#     CardHolderPan/FinalAmount می‌فرستد.
#   • رکوردت را با authority(==RefId، یکتا per-transaction) پیدا کن، نه SaleOrderId
#     که در retry تکرار می‌شود (منطبق با _CALLBACK_SPEC پکیج). SaleOrderId فقط برای extra.
#   • verify به extra نیاز دارد: res_code, sale_reference_id, sale_order_id و
#     اختیاری card_number/final_amount. اگر کاربر کنسل کرد (ResCode=17) پکیج بدون
#     تماس SOAP نتیجه‌ی ناموفق برمی‌گرداند.
#   • amount در verify باید amount_sent ذخیره‌شده باشد، نه مبلغ پایه.
# مدل نمونه‌ی MyPayment و توضیح کامل در scripts/django_custom_db.py است.

from django.utils.html import escape

from django_iranian_payment import get_gateway
from django_iranian_payment.core.models import PaymentRequest


def checkout_self_managed(request):
    """حالت ۲ ملت — شروع پرداخت و ساخت فرم POST auto-submit به دست خودت."""
    from yourapp.models import MyPayment

    order_id = "1001"  # ملت orderId عددی یکتا می‌خواهد
    amount = 500_000  # ریال
    callback_url = request.build_absolute_uri(
        reverse("mypay-callback", kwargs={"slug": "mellat"})
    )

    record = MyPayment.objects.create(
        gateway_slug="mellat",
        order_id=order_id,
        amount=amount,
        callback_url=callback_url,
        status="waiting",
    )

    gw = get_gateway("mellat")
    try:
        result = gw.initiate(
            PaymentRequest(amount=amount, callback_url=callback_url, order_id=order_id)
        )
    except GatewayError as e:
        record.status = "failed"
        record.error_message = str(e)
        record.save()
        return HttpResponse(f"خطا در اتصال به ملت: {e}", status=502)

    record.authority = result.authority  # RefId
    record.amount_sent = result.amount_to_send
    record.redirect_url = result.redirect_url
    record.redirect_fields = result.redirect_fields  # {"RefId": ...}
    record.status = "redirect"
    record.save()

    # ملت POST می‌خواهد → فرم auto-submit بساز (در حالت ۲ template پکیج نیست).
    inputs = "".join(
        f'<input type="hidden" name="{escape(k)}" value="{escape(str(v))}">'
        for k, v in (result.redirect_fields or {}).items()
    )
    html = (
        "<!doctype html><html><head><meta charset='utf-8'></head>"
        "<body onload='document.forms[0].submit()'>در حال انتقال به بانک ملت…"
        f"<form method='post' action='{escape(result.redirect_url)}'>{inputs}"
        "<noscript><button type='submit'>ادامه</button></noscript>"
        "</form></body></html>"
    )
    return HttpResponse(html)


def callback_self_managed(request):
    """حالت ۲ ملت — استخراج extra از POST، verify، و به‌روزرسانی مدل خودت."""
    from yourapp.models import MyPayment

    p = request.POST
    sale_order_id = p.get("SaleOrderId")  # برای extra لازم است
    ref_id = p.get("RefId")
    if not ref_id:
        return HttpResponse("RefId در callback نبود.", status=400)

    # ملت با authority(==RefId، یکتا per-transaction) پیدا می‌شود، نه SaleOrderId که در
    # retry تکرار می‌شود (منطبق با _CALLBACK_SPEC پکیج و docs/gateways/mellat.md).
    record = MyPayment.objects.filter(gateway_slug="mellat", authority=ref_id).first()
    if record is None:
        return HttpResponse("رکورد یافت نشد.", status=404)
    if record.status == "complete":
        return HttpResponse("قبلاً تأیید شده.")

    # extra لازم ملت برای verify (فقط مقادیر پرشده):
    extra = {
        k: v
        for k, v in {
            "res_code": p.get("ResCode"),
            "sale_reference_id": p.get("SaleReferenceId"),
            "sale_order_id": sale_order_id,
            "card_number": p.get("CardHolderPan"),
            "final_amount": p.get("FinalAmount"),
        }.items()
        if v
    }

    # پیش‌علامت: «returned» + ذخیره‌ی extra در raw، پیش از تماس با بانک، تا خطای شبکه
    # رکورد را گم نکند و reverify_pending با همین extra بعداً بگیردش.
    record.status = "returned"
    record.raw = {**(record.raw or {}), "callback_extra": extra}
    record.save(update_fields=["status", "raw", "updated_at"])

    gw = get_gateway("mellat")
    try:
        result = gw.verify(
            authority=record.authority,  # RefId
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
        record.raw = result.raw or {}  # شامل sale_*_id برای settle/reverse بعدی
        record.save()
        return HttpResponse(f"پرداخت موفق! SaleReferenceId: {record.reference_id}")
    record.status = "failed"
    record.error_message = result.error_message or ""
    record.save()
    return HttpResponse(f"پرداخت ناموفق: {record.error_message}")


def reverify_pending():
    """رکوردهای معلق (درگاه در callback بی‌پاسخ داده بود) را دوباره verify می‌کند. cron."""
    from yourapp.models import MyPayment

    for record in MyPayment.objects.filter(gateway_slug="mellat", status="returned"):
        extra = (record.raw or {}).get("callback_extra")
        try:
            result = get_gateway("mellat").verify(
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
            record.raw = result.raw or {}
            record.save()
        else:
            record.status = "failed"
            record.error_message = result.error_message or ""
            record.save()


if __name__ == "__main__":
    print(
        "این فایل راهنمای یکپارچه‌سازی Django درگاه ملت است.\n"
        "برای تست sandbox core: uv run python scripts/test_mellat.py\n"
        "⚠️  تست sandbox ملت نیاز به IP ثبت‌شده نزد بانک دارد."
    )
