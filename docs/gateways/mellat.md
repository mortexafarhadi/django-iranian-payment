<div dir="rtl">

# راهنمای اتصال درگاه ملت / به‌پرداخت (Mellat / BehPardakht)

ملت درگاه پرداخت بانک ملت است و از پروتکل **SOAP** (zeep) استفاده می‌کند. در
**registry عمومی** پکیج قرار دارد و **با تراکنش live واقعی روی محیط عملیاتی
(bpm.shaparak.ir) تأیید شده** است.

- **وضعیت:** registry عمومی — ✅ تراکنش live تست‌شده (موفق + سناریوی کنسل کاربر).
- **هدایت کاربر:** ⚠️ **فرم POST** (نه redirect ساده). باید فرم HTML auto-submit
  به کاربر داده شود.
- **callback:** POST با فیلدهای `RefId`، `ResCode`، `SaleOrderId`، `SaleReferenceId`
  و گاهی `CardHolderPan`/`FinalAmount`.
- **وابستگی اختیاری:** `[soap]` (zeep) — برای فراخوانی SOAP لازم است.
- **پیش‌نیاز عملیاتی:** قرارداد پذیرندگی + ثبت IP سرور نزد ملت + دسترسی شبکه به
  bpm.shaparak.ir.
- **مبلغ:** ریال. `order_id` باید عددی و یکتا باشد.

این راهنما دو حالت دارد و هر حالت کامل و مستقل است:
- [حالت ۱: پکیج دیتابیس را مدیریت می‌کند](#حالت-۱)
- [حالت ۲: خودت دیتابیس را مدیریت می‌کنی](#حالت-۲)

> **دومرحله‌ای بودن ملت:** پیش‌فرض `settle_mode="verify_settle"` است که تأیید و واریز
> را اتمیک انجام می‌دهد (توصیه‌شده). اگر `settle_mode="verify_only"` بگذاری، بعد از
> verify موفق باید خودت `settle()` را صدا بزنی وگرنه بانک در ۳ ساعت
> Autoreversal می‌زند (پول برمی‌گردد). متدهای کمکی: `settle()`، `reverse()`،
> `inquiry()`.

---
## نصب

<div dir="ltr">

```bash
pip install "django-iranian-payment[soap]"
# zeep برای ارتباط SOAP نیاز است.
```
---
</div>

<a id="حالت-۱"></a>
## حالت ۱: پکیج دیتابیس را مدیریت می‌کند

در این حالت پکیج خودکار فرم POST را می‌سازد و `SaleReferenceId`/`SaleOrderId` را از
callback می‌خواند و به verify می‌دهد.

### قدم ۱: settings.py


<div dir="ltr">

```python
INSTALLED_APPS = [
    # ...
    "django_iranian_payment.contrib.django",
]

# برای ساخت فرم POST، APP_DIRS باید True باشد تا template پکیج پیدا شود:
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,   # ← لازم
        "OPTIONS": {"context_processors": []},
    }
]

IRANIAN_PAYMENT = {
    "currency": "rial",  # واحد ورودی مبلغ: "rial" (پیش‌فرض) یا "toman"
    "sandbox": False,
    "gateways": {
        "mellat": {
            "terminal_id": "1234567",        # شماره ترمینال از ملت
            "username": "your-username",     # نام کاربری از ملت
            "password": "your-password",     # رمز از ملت
            "settle_mode": "verify_settle",  # توصیه: تأیید+واریز اتمیک
            # یا "verify_only" (نیاز به settle() جداگانه بعداً)
            # ⛔ ملت sandbox واقعی ندارد. "sandbox": True (اینجا یا ارث از سراسری)
            #    باعث GatewayConfigurationError می‌شود و برنامه اجرا نمی‌شود. ملت
            #    فقط live است (bpm.shaparak.ir). اگر sandbox سراسری True است، اینجا
            #    صریحاً "sandbox": False بگذار.
        },
    },
}
```
</div>

### قدم ۲: اجرای migration

<div dir="ltr">

```bash
python manage.py migrate
```
</div>

### قدم ۳: mount کردن url های پکیج

<div dir="ltr">

```python
# project/urls.py
from django.urls import path, include

urlpatterns = [
    # ...
    path("payment/", include("django_iranian_payment.contrib.django.urls")),
]
```
</div>

مسیرها:

<div dir="ltr">

```
GET  /payment/go/<payment_id>/        → صفحه‌ی فرم POST auto-submit به ملت
POST /payment/callback/mellat/        → برگشت از بانک (POST)
```
</div>

### قدم ۴: ثبت callBackUrl در ملت

آدرس زیر را نزد ملت ثبت کن:

<div dir="ltr">

```
https://yoursite.com/payment/callback/mellat/
```
</div>

### قدم ۵: view های خودت

<div dir="ltr">

```python
# yourapp/views.py
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse

from django_iranian_payment.contrib.django.services import start_payment
from django_iranian_payment.contrib.django.models import Payment, PaymentStatus
from django_iranian_payment.core.exceptions import GatewayError, GatewayConnectionError


def checkout(request):
    order_id = "1001"   # ملت orderId عددی و یکتا می‌خواهد
    amount = 500_000    # ریال
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

    # ⚠️ ملت redirect ساده ندارد. کاربر را به go_to_gateway بفرست؛ پکیج فرم POST
    # auto-submit را می‌سازد.
    return HttpResponseRedirect(
        reverse("iranian_payment:go-to-gateway", kwargs={"payment_id": payment.id})
    )


def payment_result(request):
    status = request.GET.get("payment_status")
    order_id = request.GET.get("order_id", "")
    if status == "success":
        payment = Payment.objects.filter(
            order_id=order_id, status=PaymentStatus.COMPLETE
        ).first()
        if payment:
            return HttpResponse(f"پرداخت موفق! SaleReferenceId: {payment.reference_id}")
    elif status == "failed":
        payment = Payment.objects.filter(order_id=order_id).first()
        err = payment.error_message if payment else ""
        return HttpResponse(f"پرداخت ناموفق. {err}")
    elif status == "pending":
        # درگاه هنگام verify در دسترس نبود؛ رکورد معلق مانده و reverify_pending بعداً
        # تمامش می‌کند. کاربر را در انتظار بگذار — نه موفق، نه ناموفق.
        return HttpResponse(
            f"پرداخت شما در حال بررسی است (سفارش {order_id}). نتیجه به‌زودی مشخص می‌شود."
        )
    return HttpResponse("نتیجه نامشخص.", status=400)
```

</div>

### قدم ۶: url های app خودت

<div dir="ltr">

```python
# yourapp/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("payment/result/", views.payment_result, name="payment-result"),
]
```

</div>

### settle برای حالت verify_only (اختیاری)

اگر `settle_mode="verify_only"` گذاشتی، بعد از verify موفق در یک task/celery:

<div dir="ltr">

```python
from django_iranian_payment import get_gateway

def settle_mellat(order_id, sale_order_id, sale_reference_id):
    gw = get_gateway("mellat")
    result = gw.settle(
        order_id=order_id,
        sale_order_id=sale_order_id,
        sale_reference_id=sale_reference_id,
    )
    return result.is_success
```

</div>

`sale_order_id`/`sale_reference_id` در `payment.raw` ذخیره شده‌اند (پکیج بعد از
verify آن‌ها را در raw می‌گذارد).

### جریان کامل حالت ۱

1. `checkout` → `start_payment` (SOAP bpPayRequest) → رکورد با `authority`(=`RefId`)
   ذخیره می‌شود → کاربر به `/payment/go/<id>/`.
2. view `go_to_gateway` فرم POST auto-submit با فیلد `RefId` به صفحه‌ی ملت می‌سازد.
3. کاربر پرداخت می‌کند → ملت با **POST** به `/payment/callback/mellat/` برمی‌گردد
   (RefId, ResCode, SaleOrderId, SaleReferenceId, ...).
4. view callback پکیج رکورد را با `RefId` پیدا می‌کند، `ResCode` را چک می‌کند (اگر
   کاربر کنسل کرده باشد `ResCode=17`، بدون تماس SOAP ناموفق برمی‌گرداند)، و در غیر
   این صورت bpVerifySettleRequest می‌زند.

---

<a id="حالت-۲"></a>
## حالت ۲: خودت دیتابیس را مدیریت می‌کنی

ملت در این حالت سخت‌ترین است چون هدایت با **فرم POST** است و در حالت ۲ template
پکیج در دسترس نیست (اپ در `INSTALLED_APPS` نیست) — پس فرم را خودت می‌سازی.

### قدم ۱: settings.py (بدون افزودن اپ پکیج)

<div dir="ltr">

```python
IRANIAN_PAYMENT = {
    "currency": "rial",  # واحد ورودی مبلغ: "rial" (پیش‌فرض) یا "toman"
    "sandbox": False,
    "gateways": {
        "mellat": {
            "terminal_id": "1234567",
            "username": "your-username",
            "password": "your-password",
            "settle_mode": "verify_settle",
            # ⛔ ملت sandbox ندارد؛ "sandbox": True خطا می‌دهد. فقط live.
        },
    },
}
```

</div>

### قدم ۲: مدل خودت

<div dir="ltr">

```python
# yourapp/models.py
from django.db import models


class MyPayment(models.Model):
    gateway_slug    = models.CharField(max_length=32, db_index=True)
    order_id        = models.CharField(max_length=128, db_index=True)
    amount          = models.BigIntegerField()
    amount_sent     = models.BigIntegerField(default=0)
    authority       = models.CharField(max_length=255, blank=True, db_index=True)  # RefId
    redirect_url    = models.URLField(max_length=1000, blank=True)
    redirect_fields = models.JSONField(default=dict, blank=True)   # {"RefId": ...}
    status          = models.CharField(max_length=16, default="waiting", db_index=True)
    reference_id    = models.CharField(max_length=255, blank=True)
    card_number     = models.CharField(max_length=32, blank=True)
    error_message   = models.TextField(blank=True)
    callback_url    = models.URLField(max_length=500)
    raw             = models.JSONField(default=dict, blank=True)   # sale_*_id برای settle
    created_at      = models.DateTimeField(auto_now_add=True)
```

</div>

### قدم ۳: url های خودت

<div dir="ltr">

```python
# yourapp/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("pay/mellat/",          views.checkout, name="ml-checkout"),
    path("pay/callback/mellat/", views.callback, name="ml-callback"),
]
```

</div>

> `callBackUrl` ملت را به همین `ml-callback` (آدرس کامل) ثبت کن.

### قدم ۴: view شروع پرداخت + ساخت فرم POST به دست خودت

<div dir="ltr">

```python
# yourapp/views.py
from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import escape

from django_iranian_payment import get_gateway
from django_iranian_payment.core.models import PaymentRequest
from django_iranian_payment.core.exceptions import GatewayError, GatewayConnectionError
from .models import MyPayment


def checkout(request):
    order_id = "1001"   # عددی و یکتا
    amount = 500_000    # ریال
    callback_url = request.build_absolute_uri(reverse("ml-callback"))

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

    record.authority = result.authority           # RefId
    record.amount_sent = result.amount_to_send     # مرجع یکتا برای verify
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
```

</div>

### قدم ۵: view بازگشت (POST)، استخراج extra و verify

<div dir="ltr">

```python
def callback(request):
    p = request.POST   # ملت با POST برمی‌گردد
    sale_order_id = p.get("SaleOrderId")
    ref_id = p.get("RefId")
    if not ref_id:
        return HttpResponse("RefId در callback نبود.", status=400)

    # ملت را با authority(==RefId) پیدا کن (یکتا per-transaction).
    record = MyPayment.objects.filter(gateway_slug="mellat", authority=ref_id).first()
    if record is None:
        return HttpResponse("رکورد یافت نشد.", status=404)
    if record.status == "complete":
        return HttpResponse("قبلاً تأیید شده.")

    # extra لازم ملت برای verify (فقط مقادیر پرشده):
    extra = {k: v for k, v in {
        "res_code": p.get("ResCode"),
        "sale_reference_id": p.get("SaleReferenceId"),
        "sale_order_id": sale_order_id,
        "card_number": p.get("CardHolderPan"),
        "final_amount": p.get("FinalAmount"),
    }.items() if v}

    # پیش‌علامت: «returned» + ذخیره‌ی extra در raw، پیش از تماس با بانک، تا خطای شبکه
    # رکورد را گم نکند و reverify_pending با همین extra (sale_reference_id) بگیردش.
    record.status = "returned"
    record.raw = {**(record.raw or {}), "callback_extra": extra}
    record.save(update_fields=["status", "raw", "updated_at"])

    gw = get_gateway("mellat")
    try:
        result = gw.verify(
            authority=ref_id,
            amount=record.amount_sent,   # ⚠️ نه record.amount
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
        record.raw = result.raw or {}   # شامل sale_*_id برای settle/reverse بعدی
        record.save()
        return HttpResponse(f"پرداخت موفق! SaleReferenceId: {record.reference_id}")

    record.status = "failed"
    record.error_message = result.error_message or ""
    record.save()
    return HttpResponse(f"پرداخت ناموفق: {record.error_message}")


def reverify_pending():
    """رکوردهای معلق ملت (درگاه در callback بی‌پاسخ داده بود) را دوباره verify می‌کند. cron."""
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
            continue
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
```

</div>

### settle / reverse در حالت verify_only (حالت ۲)

<div dir="ltr">

```python
gw = get_gateway("mellat")
raw = record.raw  # شامل sale_order_id و sale_reference_id

# واریز با تأخیر:
gw.settle(order_id=record.order_id,
          sale_order_id=raw["sale_order_id"],
          sale_reference_id=raw["sale_reference_id"])

# برگشت وجه:
gw.reverse(order_id=record.order_id,
           sale_order_id=raw["sale_order_id"],
           sale_reference_id=raw["sale_reference_id"])
```

</div>

### نکات اختصاصی ملت در حالت ۲

- **هدایت:** فرم POST auto-submit (نمونه‌ی بالا). redirect ساده کار نمی‌کند.
- **پیدا کردن رکورد:** با `authority`(==`RefId`) که در callback برمی‌گردد و یکتاست.
- **`extra`:** ضروری — `sale_reference_id` نباشد verify خطا می‌دهد. کنسل کاربر
  (`ResCode=17`) فاقد `SaleReferenceId` است؛ پکیج این را تشخیص می‌دهد و بدون تماس
  SOAP نتیجه‌ی ناموفق برمی‌گرداند.
- **settle:** اگر `verify_only` باشی، حتماً `settle()` را بزن وگرنه Autoreversal.

---

## در دسترس نبودن درگاه هنگام verify

اگر این درگاه هنگام verify بی‌پاسخ داد یا خطای شبکه/۵۰۰ برگرداند، پول ممکن است از
کاربر کم شده ولی تأیید نشده باشد. **خطای شبکه ≠ پرداخت ناموفق**:

- **حالت ۱ (پکیج DB):** خودکار مدیریت می‌شود — رکورد `RETURN_FROM_BANK` معلق می‌ماند
  (نه گم، نه منقضی) و کاربر `payment_status=pending` می‌گیرد. فقط یک job دوره‌ای بساز:
  `services.reverify_pending()` + `services.expire_stale(older_than_minutes=30)`.
- **حالت ۲ (DB خودت):** در callback هنگام `GatewayConnectionError` رکورد را
  `"returned"` (نه `"failed"`) بگذار و `extra` را در `raw` ذخیره کن؛ سپس یک job
  دوره‌ای معلق‌ها را دوباره verify کند.

> نکته‌ی ملت: verify به `sale_reference_id`/`sale_order_id` از callback نیاز دارد. در حالت ۱ اینها خودکار در `raw["callback_extra"]` ذخیره و در reverify بازخوانده می‌شوند؛ در حالت ۲ خودت باید همراه رکورد ذخیره‌شان کنی تا reverify کار کند.

جزئیات کامل و نمونه‌ی management command + cron:
[README.md](README.md#در-دسترس-نبودن-درگاه-هنگام-verify-مهم--برای-همهی-درگاهها).

## کد آماده‌ی اجرا

- [`scripts/django_mellat.py`](../../scripts/django_mellat.py) — کد هر دو حالت.
- [`scripts/test_mellat.py`](../../scripts/test_mellat.py) — تست core (نیاز به IP
  ثبت‌شده نزد بانک).
</div>