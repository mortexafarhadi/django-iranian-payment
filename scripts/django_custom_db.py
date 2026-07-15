"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 راهنمای مشترک: استفاده در Django وقتی «خودت» دیتابیس را مدیریت می‌کنی
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

این فایل مکملِ فایل‌های scripts/django_<gateway>.py است. آن فایل‌ها حالتی را نشان
می‌دهند که «پکیج» ذخیره‌سازی را مدیریت می‌کند (مدل Payment پکیج + سرویس‌های
start_payment/verify_payment + view و url داخلی). این فایل حالت دوم را پوشش می‌دهد:

    تو خودت رکورد پرداخت را در مدل خودت ذخیره می‌کنی و فقط از «هسته‌ی بدون state»
    پکیج (get_gateway + PaymentRequest + initiate/verify) استفاده می‌کنی.

این راهنما برای «همه‌ی درگاه‌ها» نوشته شده: یک مسیر کد واحد که با یک جدول مشخصات
(CALLBACK_SPEC) تفاوت‌های هر درگاه را مدیریت می‌کند.

━━ دو حالت در یک نگاه ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  حالت ۱ — پکیج DB را مدیریت می‌کند (فایل‌های django_<gateway>.py):
    • "django_iranian_payment.contrib.django" را به INSTALLED_APPS اضافه می‌کنی.
    • python manage.py migrate می‌زنی (جدول iranian_payment_payment ساخته می‌شود).
    • از services.start_payment / services.verify_payment استفاده می‌کنی.
    • url های داخلی پکیج (/payment/go/... و /payment/callback/...) را mount می‌کنی.
    • مزیت: تقریباً هیچ کدی برای state/verify/callback نمی‌نویسی (جعبه‌سیاه).

  حالت ۲ — تو DB را مدیریت می‌کنی (همین فایل):
    • نیازی به افزودن اپ پکیج به INSTALLED_APPS نیست.
    • نیازی به migrate پکیج نیست (مدل Payment پکیج ساخته نمی‌شود).
    • مدل خودت را داری؛ هر فیلدی می‌خواهی کنارش نگه می‌داری (سفارش، کاربر، ...).
    • view و url و callback را خودت می‌نویسی (نمونه‌ی کامل پایین همین فایل).
    • مزیت: کنترل کامل روی schema و جریان؛ مناسب وقتی پرداخت بخشی از مدل
      بزرگ‌تر توست یا نمی‌خواهی جدول جدا و وابستگی به لایه‌ی contrib داشته باشی.
    • این حالت حتی در FastAPI/Flask/اسکریپت هم کار می‌کند چون هسته بدون state و
      بدون وابستگی به Django است؛ اینجا فقط با Django نشانش می‌دهیم.

━━ قانون طلایی حالت ۲ (اگر یکی را رعایت نکنی پول گم می‌شود) ━━

  1. amount_to_send مرجع یکتاست. عددی که initiate برگرداند (result.amount_to_send)
     را ذخیره کن و «همان» را در verify بده — نه مبلغ پایه‌ی سفارش. اگر کارمزد از
     مشتری گرفته باشی این دو فرق دارند و verify با مبلغ غلط رد می‌شود
     (زرین‌پال/پی‌پینگ سخت‌گیرند).
  2. authority را از initiate ذخیره کن. در callback لازم است.
  3. در verify از روی نتیجه‌ی واقعی بانک تصمیم بگیر، نه از پارامتر بازگشتی مرورگر.
     پارامتر callback قابل دستکاری است؛ فقط result.is_success معتبر است.
  4. یکتایی و idempotency مسئولیت توست: اگر رکورد قبلاً COMPLETE شده، دوباره
     verify نزن (بعضی درگاه‌ها مثل سامان یک RefNum را بارها verify می‌کنند).
  5. واحد بانک همیشه ریال است. اگر می‌خواهی ورودی را تومان بدهی، در حالت ۲ واحد را
     روی خود درخواست بده: PaymentRequest(amount=15_000, currency="toman", ...). پکیج
     خودکار به ریال تبدیل می‌کند (۱ تومان = ۱۰ ریال) و amount_to_send ریالی می‌شود.
     برای خواندن واحد سراسری از settings: from django_iranian_payment import
     get_default_currency. مقادیر ذخیره/بازگشتی همیشه ریال‌اند.

━━ نصب و settings (حالت ۲) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    pip install django-iranian-payment
    # وابستگی اختیاری هر درگاه را در صورت نیاز نصب کن:
    #   ملت:       pip install "django-iranian-payment[soap]"
    #   ایران‌کیش:  pip install "django-iranian-payment[irankish]"
    #   سداد:      pip install "django-iranian-payment[sadad]"

    # settings.py — توجه: اپ contrib.django لازم نیست به INSTALLED_APPS برود.
    # فقط بلوک config درگاه‌ها را بده؛ get_gateway از همین می‌خواند.
    IRANIAN_PAYMENT = {
        "currency": "rial",   # واحد ورودی مبلغ: "rial" (پیش‌فرض) یا "toman"
        "sandbox": True,   # False در production
        "gateways": {
            "zarinpal": {"merchant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"},
            "zibal":    {"merchant_id": "zibal"},
            "mellat":   {"terminal_id": "...", "username": "...", "password": "...",
                          "settle_mode": "verify_settle"},
            "saman":    {"terminal_id": "..."},
            "irankish": {"terminal_id": "...", "acceptor_id": "...",
                          "pass_phrase": "...", "public_key": "/path/to/key.pem"},
            "nextpay":  {"api_key": "..."},
            "sadad":    {"merchant_id": "...", "terminal_id": "...", "terminal_key": "..."},
            "digipay":  {"username": "...", "password": "...", "client_id": "...",
                          "client_secret": "...", "provider_id": "..."},
        },
    }

⚠️ درگاه‌های تجربی (irankish/nextpay/sadad/digipay) در registry عمومی نیستند.
   برای اینکه get_gateway آن‌ها را بشناسد باید یک‌بار register کنی (در AppConfig.ready):

    # yourapp/apps.py
    from django.apps import AppConfig

    class YourAppConfig(AppConfig):
        name = "yourapp"
        def ready(self):
            from django_iranian_payment.core.gateways import _REGISTRY
            from django_iranian_payment.core.experimental.irankish import IrankishGateway
            from django_iranian_payment.core.experimental.nextpay import NextPayGateway
            from django_iranian_payment.core.experimental.sadad import SadadGateway
            from django_iranian_payment.core.experimental.digipay import DigipayGateway
            _REGISTRY.setdefault("irankish", IrankishGateway)
            _REGISTRY.setdefault("nextpay", NextPayGateway)
            _REGISTRY.setdefault("sadad", SadadGateway)
            _REGISTRY.setdefault("digipay", DigipayGateway)
   # zarinpal/zibal/mellat/saman در registry عمومی هستند و نیازی به این کار ندارند.

━━ مدل نمونه‌ی خودت ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

این مدلِ توست (نه پکیج). آن را در yourapp/models.py بگذار و migrate کن. حداقل
فیلدهای لازم را دارد؛ هر فیلد دیگری (ForeignKey به User/Order و ...) آزادانه اضافه کن.

    # yourapp/models.py
    from django.db import models

    class MyPayment(models.Model):
        # ── شناسه‌ها ──────────────────────────────────────────────
        gateway_slug = models.CharField(max_length=32, db_index=True)
        order_id     = models.CharField(max_length=128, db_index=True, unique=True)

        # ── مبالغ (ریال) ─────────────────────────────────────────
        amount       = models.BigIntegerField(help_text="مبلغ پایه‌ی سفارش")
        # amount_sent: مبلغی که واقعاً به بانک رفت (با کارمزد). همین در verify می‌رود.
        amount_sent  = models.BigIntegerField(default=0)

        # ── state بازگشتی از initiate ─────────────────────────────
        authority       = models.CharField(max_length=255, blank=True, db_index=True)
        redirect_url    = models.URLField(max_length=1000, blank=True)
        redirect_method = models.CharField(max_length=8, default="GET")  # GET یا POST
        redirect_fields = models.JSONField(default=dict, blank=True)     # فرم POST (ملت)

        # ── وضعیت ─────────────────────────────────────────────────
        # waiting → redirect → complete/failed ؛ رشته‌ی ساده، هرچه می‌خواهی
        status       = models.CharField(max_length=16, default="waiting", db_index=True)

        # ── نتیجه‌ی verify ───────────────────────────────────────
        reference_id  = models.CharField(max_length=255, blank=True)
        card_number   = models.CharField(max_length=32, blank=True)
        error_code    = models.CharField(max_length=64, blank=True)
        error_message = models.TextField(blank=True)

        callback_url = models.URLField(max_length=500)
        raw          = models.JSONField(default=dict, blank=True)
        created_at   = models.DateTimeField(auto_now_add=True)
        updated_at   = models.DateTimeField(auto_now=True)

        @property
        def is_success(self):
            return self.status == "complete"

━━ url های خودت ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # yourapp/urls.py
    from django.urls import path
    from . import views

    urlpatterns = [
        path("pay/<slug:slug>/",            views.checkout,  name="mypay-checkout"),
        path("pay/callback/<slug:slug>/",   views.callback,  name="mypay-callback"),
    ]
    # توجه: callbackِ بانک باید دقیقاً به همین mypay-callback اشاره کند (نه به
    # url پکیج). در درگاه‌هایی که callback را در پنل ثبت می‌کنی (ملت/سامان/...)
    # همین آدرس کامل را ثبت کن.

━━ مرجع تفاوت درگاه‌ها در حالت مدیریت دستی ━━━━━━━━━━━━━━━━━━

این تفاوت‌ها در CALLBACK_SPEC پایین کدگذاری شده‌اند تا یک مسیر کد واحد همه را
پوشش دهد. (همه با مدرک از کد هر درگاه استخراج شده‌اند.)

  درگاه     | هدایت  | callback | رکورد را با چه پیدا کنی | verify چه extra می‌خواهد
  ----------|--------|----------|------------------------|--------------------------
  zarinpal  | GET    | GET      | authority == Authority | —
  zibal     | GET    | GET      | authority == trackId   | —
  nextpay   | GET    | GET      | authority == trans_id  | —
  sadad     | GET    | POST     | authority == Token     | (res_code اختیاری)
  mellat    | POST!  | POST     | order_id == SaleOrderId| res_code, sale_reference_id,
            |        |          |                        | sale_order_id, card, final
  saman     | GET*   | POST     | order_id == ResNum     | ref_num(RefNum), state
  irankish  | GET*   | POST     | authority == token     | reference_id, token, result_code
  digipay   | GET    | GET/POST | order_id == providerId | tracking_code, result

  • هدایت «POST!» (ملت): باید فرم HTML auto-submit بسازی (نمونه پایین). در حالت
    ۲ template پکیج در دسترس نیست چون اپ در INSTALLED_APPS نیست.
  • «GET*» (سامان/ایران‌کیش): مستند بانک فرم POST توصیه می‌کند ولی پیاده‌سازی
    redirect_url آماده‌ی GET می‌دهد؛ go_to_gateway همان را redirect می‌کند.
  • «رکورد را با چه پیدا کنی»: مهم! callbackِ سامان/دیجی‌پی توکن را برنمی‌گرداند
    پس باید با order_id (که خودت ساختی و بانک echo می‌کند) رکورد را پیدا کنی؛
    callbackِ زرین‌پال/ایران‌کیش order_id ندارد پس با authority پیدا می‌شود.
"""

from django.http import (
    HttpResponse,
    HttpResponseRedirect,
    HttpResponseNotFound,
)
from django.urls import reverse
from django.utils.html import escape

from django_iranian_payment import get_gateway
from django_iranian_payment.core.models import PaymentRequest
from django_iranian_payment.core.exceptions import GatewayError

# توجه: این import به مدل خودت اشاره می‌کند که در yourapp/models.py تعریفش کردی.
# اینجا داخل توابع import می‌شود تا این فایل راهنما بدون اپ تو هم قابل import بماند.
#   from yourapp.models import MyPayment


# ─────────────────────────────────────────────────────────────
#  جدول مشخصات callback هر درگاه — قلب مسیر کد واحد
# ─────────────────────────────────────────────────────────────
#
# lookup = (field, param):
#   رکورد را با MyPayment.objects.filter(gateway_slug=slug, <field>=request[<param>])
#   پیدا کن. field یکی از "authority" یا "order_id" است.
# extra  = {verify_key: (candidate_param, ...)}:
#   مقادیری که verify آن درگاه از callback لازم دارد. اولین param موجود برداشته می‌شود.

CALLBACK_SPEC = {
    "zarinpal": {"lookup": ("authority", "Authority"), "extra": {}},
    "zibal": {"lookup": ("authority", "trackId"), "extra": {}},
    "nextpay": {"lookup": ("authority", "trans_id"), "extra": {}},
    "sadad": {
        "lookup": ("authority", "Token"),  # callback سداد POST است با فیلد Token
        "extra": {"res_code": ("ResCode",)},
    },
    "mellat": {
        "lookup": ("order_id", "SaleOrderId"),
        "extra": {
            "res_code": ("ResCode",),
            "sale_reference_id": ("SaleReferenceId",),
            "sale_order_id": ("SaleOrderId",),
            "card_number": ("CardHolderPan",),
            "final_amount": ("FinalAmount",),
        },
    },
    "saman": {
        "lookup": ("order_id", "ResNum"),
        "extra": {"ref_num": ("RefNum",), "state": ("State",)},
    },
    "irankish": {
        "lookup": ("authority", "token"),
        "extra": {
            "reference_id": ("referenceId",),
            "token": ("token",),
            "result_code": ("resultCode",),
        },
    },
    "digipay": {
        "lookup": ("order_id", "providerId"),
        "extra": {"tracking_code": ("trackingCode",), "result": ("result", "status")},
    },
}


def _callback_params(request):
    """پارامترهای callback را از POST یا GET برمی‌گرداند (هر کدام پر باشد)."""
    return request.POST if request.method == "POST" else request.GET


def _find_record(slug, request):
    """رکورد MyPayment را طبق lookup همان درگاه پیدا می‌کند."""
    from yourapp.models import MyPayment  # noqa: مدل خودت

    spec = CALLBACK_SPEC[slug]
    field, param = spec["lookup"]
    value = _callback_params(request).get(param)
    if not value:
        return None
    return (
        MyPayment.objects.filter(gateway_slug=slug, **{field: value})
        .order_by("-created_at")
        .first()
    )


def _build_extra(slug, request):
    """extra لازم برای verify همان درگاه را از callback می‌سازد (یا None)."""
    spec = CALLBACK_SPEC[slug]
    params = _callback_params(request)
    extra = {}
    for verify_key, candidates in spec["extra"].items():
        for param in candidates:
            if params.get(param):
                extra[verify_key] = params[param]
                break
    return extra or None


# ─────────────────────────────────────────────────────────────
#  قدم ۱: شروع پرداخت (checkout) — برای همه‌ی درگاه‌ها یکسان
# ─────────────────────────────────────────────────────────────


def checkout(request, slug):
    """
    رکورد خودت را می‌سازی، initiate می‌زنی، authority/amount_sent را ذخیره می‌کنی،
    و کاربر را به درگاه می‌فرستی. هیچ کدی از لایه‌ی contrib.django استفاده نمی‌شود.
    """
    import uuid

    from yourapp.models import MyPayment  # مدل خودت

    # order_id را خودت یکتا بساز (uuid، شماره‌ی سفارش، ...). بانک آن را echo می‌کند.
    order_id = f"ORDER-{uuid.uuid4().hex[:16]}"
    amount = 150_000  # ریال — از سبد خرید واقعی بخوان

    # callback_url باید به view خودت اشاره کند (نه پکیج).
    callback_url = request.build_absolute_uri(
        reverse("mypay-callback", kwargs={"slug": slug})
    )

    # رکورد را قبل از تماس با بانک بساز تا اگر کاربر برگشت، چیزی برای پیدا کردن باشد.
    record = MyPayment.objects.create(
        gateway_slug=slug,
        order_id=order_id,
        amount=amount,
        callback_url=callback_url,
        status="waiting",
    )

    gw = get_gateway(slug)
    try:
        result = gw.initiate(
            PaymentRequest(
                amount=amount,
                callback_url=callback_url,
                order_id=order_id,
                description="خرید از فروشگاه",
                # اگر کارمزد می‌خواهی:
                #   from django_iranian_payment import FeeConfig, FeePayer
                #   fee=FeeConfig(rate_bps=100, who_pays=FeePayer.CUSTOMER),
            )
        )
    except GatewayError as e:
        record.status = "failed"
        record.error_message = str(e)
        record.save(update_fields=["status", "error_message", "updated_at"])
        return HttpResponse(f"خطا در اتصال به درگاه: {e} (کد: {e.code})", status=502)

    # ⚠️ مرجع یکتا: amount_sent همان amount_to_send است؛ همین در verify می‌رود.
    record.authority = result.authority or ""
    record.amount_sent = result.amount_to_send
    record.redirect_url = result.redirect_url or ""
    record.redirect_method = result.redirect_method  # "GET" یا "POST" (ملت)
    record.redirect_fields = result.redirect_fields or {}
    record.status = "redirect"
    record.save()

    return go_to_gateway(record)


# ─────────────────────────────────────────────────────────────
#  قدم ۲: هدایت به درگاه (GET ساده یا فرم POST برای ملت)
# ─────────────────────────────────────────────────────────────


def go_to_gateway(record):
    """
    اگر درگاه GET است redirect ساده؛ اگر POST است (ملت) فرم auto-submit می‌سازد.
    در حالت ۲ template پکیج در دسترس نیست، پس فرم را اینجا می‌سازیم.
    """
    if record.redirect_method == "POST":
        return _post_redirect(record.redirect_url, record.redirect_fields)
    return HttpResponseRedirect(record.redirect_url)


def _post_redirect(action, fields):
    """یک صفحه‌ی HTML که فوراً فرم POST را به درگاه submit می‌کند."""
    inputs = "".join(
        f'<input type="hidden" name="{escape(k)}" value="{escape(str(v))}">'
        for k, v in (fields or {}).items()
    )
    html = (
        "<!doctype html><html><head><meta charset='utf-8'></head>"
        "<body onload='document.forms[0].submit()'>"
        "<p>در حال انتقال به درگاه بانک…</p>"
        f"<form method='post' action='{escape(action)}'>{inputs}"
        "<noscript><button type='submit'>ادامه</button></noscript>"
        "</form></body></html>"
    )
    return HttpResponse(html)


# ─────────────────────────────────────────────────────────────
#  قدم ۳: callback — verify و به‌روزرسانی رکورد خودت
# ─────────────────────────────────────────────────────────────


def callback(request, slug):
    """
    بازگشت از بانک. رکورد را طبق CALLBACK_SPEC پیدا می‌کند، با amount_sent (نه
    مبلغ پایه) verify می‌زند، و وضعیت را در مدل خودت ذخیره می‌کند.

    این همان منطقی است که در حالت ۱ پکیج (services.verify_payment + view callback)
    برایت می‌نوشت؛ اینجا چون خودت DB را مدیریت می‌کنی، خودت نوشته‌ای.
    """
    record = _find_record(slug, request)
    if record is None:
        return HttpResponseNotFound("رکورد پرداختی برای این callback یافت نشد.")

    # idempotent: اگر قبلاً نهایی شده دوباره verify نزن.
    if record.status == "complete":
        return _result_redirect(record)

    gw = get_gateway(slug)
    result = gw.verify(
        authority=record.authority,
        amount=record.amount_sent,  # ⚠️ مرجع یکتا، نه record.amount
        order_id=record.order_id,
        extra=_build_extra(slug, request),  # برای ملت/سامان/ایران‌کیش/دیجی‌پی لازم
    )

    if result.is_success:
        record.status = "complete"
        record.reference_id = result.reference_id or ""
        record.card_number = result.card_number or ""
        record.raw = result.raw or {}
        record.save()
    else:
        record.status = "failed"
        record.error_code = result.error_code or ""
        record.error_message = result.error_message or ""
        record.raw = result.raw or {}
        record.save()

    return _result_redirect(record)


def _result_redirect(record):
    """کاربر را به صفحه‌ی نتیجه‌ی خودت می‌فرستد (یا مستقیم پاسخ می‌دهد)."""
    if record.is_success:
        return HttpResponse(
            f"پرداخت موفق! کد پیگیری: {record.reference_id} — سفارش {record.order_id}"
        )
    return HttpResponse(
        f"پرداخت ناموفق برای سفارش {record.order_id}. {record.error_message}"
    )


# ─────────────────────────────────────────────────────────────
#  حالت بدون مدل Django — مستقیم با هسته (FastAPI/Flask/اسکریپت)
# ─────────────────────────────────────────────────────────────
#
# اگر اصلاً ORM نمی‌خواهی، الگو همان است؛ فقط جای MyPayment، storage خودت را بگذار:
#
#   gw = get_gateway("zarinpal")
#   result = gw.initiate(PaymentRequest(amount=150_000, callback_url="https://...",
#                                       order_id="ORDER-1"))
#   your_storage.save(order_id="ORDER-1",
#                     authority=result.authority,
#                     amount_sent=result.amount_to_send)   # ← این دو را حتماً نگه‌دار
#   # کاربر را به result.redirect_url بفرست (یا فرم POST اگر redirect_method=="POST")
#
#   # در callback:
#   rec = your_storage.load(order_id_or_authority_from_callback)
#   verify_result = gw.verify(authority=rec["authority"],
#                             amount=rec["amount_sent"],      # نه مبلغ پایه
#                             order_id=rec["order_id"],
#                             extra=extra_from_callback_or_None)
#   if verify_result.is_success:
#       your_storage.mark_paid(rec, ref=verify_result.reference_id)


# ─────────────────────────────────────────────────────────────
#  ملت: settle / reverse در حالت verify_only (حالت ۲)
# ─────────────────────────────────────────────────────────────
#
# اگر settle_mode="verify_only" گذاشتی، بعد از verify موفق باید settle بزنی وگرنه
# پول در ۳ ساعت برمی‌گردد (Autoreversal). sale_order_id/sale_reference_id را از
# result.raw که در verify ذخیره کردی بردار:
#
#   gw = get_gateway("mellat")
#   raw = record.raw  # شامل sale_order_id و sale_reference_id
#   settle = gw.settle(order_id=record.order_id,
#                      sale_order_id=raw["sale_order_id"],
#                      sale_reference_id=raw["sale_reference_id"])
#   # برای برگشت وجه: gw.reverse(order_id=..., sale_order_id=..., sale_reference_id=...)


if __name__ == "__main__":
    print(
        "راهنمای حالت «مدیریت دستی دیتابیس» برای همه‌ی درگاه‌ها.\n"
        "مدل MyPayment را در yourapp/models.py بساز، view ها را کپی کن،\n"
        "و CALLBACK_SPEC را برای درگاه موردنظرت استفاده کن.\n"
        "حالت «پکیج DB را مدیریت کند» در scripts/django_<gateway>.py است."
    )
