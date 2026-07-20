<div dir="rtl">

# راهنمای اتصال درگاه سامان (SEP — Saman Electronic Payment)

سامان درگاه پرداخت اینترنتی بانک سامان با REST/JSON و flow مبتنی بر Token است.

- **وضعیت:** ✅ **registry عمومی** — با **تراکنش واقعی روی ترمینال واقعی** تست شد و
  طبق قانون طلایی عمومی شد. با `get_gateway("saman")` مستقیماً در دسترس است.
- **هدایت کاربر:** **فرم POST** (فیلد `Token`) به درگاه کلاسیک `OnlinePG/OnlinePG`
  (`result.redirect_method == "POST"`، `result.redirect_fields == {"Token": ...}`).
  مستند بانک صریح است: هدایت باید از طریق فرم/لینکِ سایت پذیرنده باشد تا مرورگر
  هدر `Referrer` را بفرستد، وگرنه ورود به درگاه ممکن نیست. در حالت پکیج، view
  `go_to_gateway` این فرم را خودکار می‌سازد؛ در حالت خودمدیریت، خودت می‌سازی.
- **دو حالت (config `mode`):**
  - `"classic"` (**پیش‌فرض**): توکن به درگاه کلاسیک `OnlinePG/OnlinePG` POST می‌شود.
    ورود مستقیم صفحه‌ی کارت، بدون مودال. هدر `X-IPG-Url` نادیده گرفته می‌شود.
  - `"neo_pg"` (بلوپی/BluPay): توکن به آدرس هدر `X-IPG-Url`
    (`neo-pg.sep.ir/...`) POST می‌شود؛ مودال «درگاه اینترنتی / بلوپی». نیازمند
    فعال‌بودن neo-pg روی ترمینال نزد سامان — وگرنه هدر نمی‌آید و initiate خطای
    `neo_pg_not_enabled` می‌دهد.
- **callback:** POST با فیلدهای `State`، `Status`، `RefNum`، `ResNum`، `RRN`.
- **sandbox:** ⛔ سامان **sandbox واقعی ندارد**. `sandbox=True` (مستقیم یا از ارث‌بریِ
  `sandbox` سراسری) باعث `GatewayConfigurationError` می‌شود و **برنامه اجرا نمی‌شود** —
  عمدی، تا کاربر گمان نکند در محیط تست است. تست فقط با ترمینال واقعی روی آدرس عملیاتی.
  اگر `sandbox` سراسری `True` است، برای سامان صریحاً `"sandbox": False` بگذار.
- **پیش‌نیاز:** `TerminalId` واقعی + ثبت IP سرور نزد سامان (وگرنه در ساخت Token کد ۸).
- **مبلغ:** ریال.

> ⚠️ **نکته‌ی مهم سامان:** callback **توکن (authority) را برنمی‌گرداند** و verify به
> `RefNum` نیاز دارد، نه توکن. پس رکورد را باید با `ResNum`(==`order_id` که خودت
> فرستادی) پیدا کنی. همچنین سامان در برابر double-spending مسئولیتی نمی‌پذیرد و یک
> `RefNum` را بارها verify می‌کند؛ یکتایی و idempotency مسئولیت توست.

این راهنما دو حالت دارد و هر حالت کامل و مستقل است:
- [حالت ۱: پکیج دیتابیس را مدیریت می‌کند](#حالت-۱)
- [حالت ۲: خودت دیتابیس را مدیریت می‌کنی](#حالت-۲)

---

## نصب

<div dir="ltr">

```bash
pip install django-iranian-payment
```
</div>

---

<a id="حالت-۱"></a>
## حالت ۱: پکیج دیتابیس را مدیریت می‌کند

### قدم ۱: settings.py

<div dir="ltr">

```python
INSTALLED_APPS = [
    # ...
    "django_iranian_payment.contrib.django",
]

IRANIAN_PAYMENT = {
    "currency": "rial",  # واحد ورودی مبلغ: "rial" (پیش‌فرض) یا "toman"
    "sandbox": False,
    "gateways": {
        "saman": {
            "terminal_id": "123456789",   # شماره ترمینال از پرداخت الکترونیک سامان
            "mode": "classic",            # "classic" (پیش‌فرض) یا "neo_pg" (بلوپی)
            # ⛔ سامان sandbox ندارد. "sandbox": True اینجا (یا ارث از سراسری) خطا
            #    می‌دهد و برنامه اجرا نمی‌شود. اگر sandbox سراسری True است، اینجا
            #    "sandbox": False بگذار.
        },
    },
}
```
</div>

### قدم ۲: migration و url ها

<div dir="ltr">

```bash
python manage.py migrate
```
</div>

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
GET  /payment/go/<payment_id>/      → هدایت به درگاه (فرم POST auto-submit)
POST /payment/callback/saman/       → برگشت از بانک (POST)
```
</div>

### قدم ۳: view های خودت

<div dir="ltr">

```python
# yourapp/views.py
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse

from django_iranian_payment.contrib.django.services import start_payment
from django_iranian_payment.contrib.django.models import Payment, PaymentStatus
from django_iranian_payment.core.exceptions import GatewayError, GatewayConnectionError


def checkout(request):
    order_id = "SAMAN-ORDER-001"   # این به‌عنوان ResNum می‌رود و در callback برمی‌گردد
    amount = 300_000               # ریال
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
        )
    except GatewayError as e:
        return HttpResponse(f"خطا در اتصال به سامان: {e}", status=502)

    # سامان هدایت با فرم POST می‌خواهد → به view go_to_gateway بفرست (فرم
    # auto-submit می‌سازد و Referrer را می‌فرستد). redirect_url را مستقیم GET نکن.
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
            return HttpResponse(f"پرداخت موفق! RefNum/RRN: {payment.reference_id}")
    elif status == "failed":
        return HttpResponse("پرداخت ناموفق.")
    elif status == "pending":
        # درگاه هنگام verify در دسترس نبود؛ رکورد معلق مانده و reverify_pending بعداً
        # تمامش می‌کند. کاربر را در انتظار بگذار — نه موفق، نه ناموفق.
        return HttpResponse(
            f"پرداخت شما در حال بررسی است (سفارش {order_id}). نتیجه به‌زودی مشخص می‌شود."
        )
    return HttpResponse("نتیجه نامشخص.", status=400)
```
</div>

### جریان کامل حالت ۱

1. `checkout` → `start_payment` رکورد با `authority`(=token) و `amount_sent` ذخیره
   می‌کند → کاربر به `go_to_gateway` می‌رود که فرم POST auto-submit به سامان می‌سازد.
2. کاربر پرداخت می‌کند → سامان با **POST** به `/payment/callback/saman/` برمی‌گردد
   (State, Status, RefNum, ResNum, ...).
3. view callback پکیج رکورد را با `ResNum`(==order_id) پیدا می‌کند، `RefNum`/`State`
   را به‌عنوان `extra` به verify می‌دهد، و نتیجه را ذخیره می‌کند.

---

<a id="حالت-۲"></a>
## حالت ۲: خودت دیتابیس را مدیریت می‌کنی

### قدم ۱: settings.py (بدون افزودن اپ پکیج)

<div dir="ltr">

```python
IRANIAN_PAYMENT = {
    "currency": "rial",  # واحد ورودی مبلغ: "rial" (پیش‌فرض) یا "toman"
    "sandbox": False,
    "gateways": {
        "saman": {"terminal_id": "123456789", "mode": "classic"},  # یا "neo_pg"
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
    gateway_slug = models.CharField(max_length=32, db_index=True)
    order_id     = models.CharField(max_length=128, db_index=True)   # == ResNum
    amount       = models.BigIntegerField()
    amount_sent  = models.BigIntegerField(default=0)
    authority    = models.CharField(max_length=255, blank=True, db_index=True)  # token
    status       = models.CharField(max_length=16, default="waiting", db_index=True)
    reference_id = models.CharField(max_length=255, blank=True)   # RRN
    card_number  = models.CharField(max_length=32, blank=True)
    error_message = models.TextField(blank=True)
    callback_url = models.URLField(max_length=500)
    created_at   = models.DateTimeField(auto_now_add=True)
```
</div>

### قدم ۳: url های خودت

<div dir="ltr">

```python
# yourapp/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("pay/saman/",          views.checkout, name="sm-checkout"),
    path("pay/callback/saman/", views.callback, name="sm-callback"),
]
```
</div>

### قدم ۴: view شروع پرداخت

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
    order_id = "SAMAN-ORDER-001"   # همین در callback به‌عنوان ResNum برمی‌گردد
    amount = 300_000               # ریال
    callback_url = request.build_absolute_uri(reverse("sm-callback"))

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

    record.authority = result.authority        # token (در callback برنمی‌گردد)
    record.amount_sent = result.amount_to_send  # مرجع یکتا برای verify
    record.status = "redirect"
    record.save()

    # سامان POST می‌خواهد → فرم auto-submit بساز (action همان درگاه کلاسیک است).
    inputs = "".join(
        f'<input type="hidden" name="{escape(k)}" value="{escape(str(v))}">'
        for k, v in (result.redirect_fields or {}).items()   # {"Token": ...}
    )
    return HttpResponse(
        "<!doctype html><html><head><meta charset='utf-8'></head>"
        "<body onload='document.forms[0].submit()'>در حال انتقال به درگاه سامان…"
        f"<form method='post' action='{escape(result.redirect_url)}'>{inputs}"
        "<noscript><button type='submit'>ادامه</button></noscript>"
        "</form></body></html>"
    )
```
</div>

### قدم ۵: view بازگشت (POST) و verify با RefNum

<div dir="ltr">

```python
def callback(request):
    p = request.POST   # سامان با POST برمی‌گردد
    res_num = p.get("ResNum")   # == order_id ما
    if not res_num:
        return HttpResponse("ResNum در callback نبود.", status=400)

    # ⚠️ سامان توکن را برنمی‌گرداند → با order_id(==ResNum) پیدا کن.
    record = MyPayment.objects.filter(gateway_slug="saman", order_id=res_num).first()
    if record is None:
        return HttpResponse("رکورد یافت نشد.", status=404)
    if record.status == "complete":   # idempotency حیاتی برای سامان
        return HttpResponse("قبلاً تأیید شده.")

    extra = {k: v for k, v in {"ref_num": p.get("RefNum"), "state": p.get("State")}.items() if v}

    # پیش‌علامت: «returned» + ذخیره‌ی extra در raw، پیش از تماس با بانک، تا خطای شبکه
    # رکورد را گم نکند و reverify_pending با همین extra (ref_num) بگیردش.
    record.status = "returned"
    record.raw = {**(record.raw or {}), "callback_extra": extra}
    record.save(update_fields=["status", "raw", "updated_at"])

    gw = get_gateway("saman")
    try:
        result = gw.verify(
            authority=record.authority,
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
        record.reference_id = result.reference_id or ""   # RRN
        record.card_number = result.card_number or ""
        record.save()
        return HttpResponse(f"پرداخت موفق! RefNum/RRN: {record.reference_id}")

    record.status = "failed"
    record.error_message = result.error_message or ""
    record.save()
    return HttpResponse(f"پرداخت ناموفق: {record.error_message}")


def reverify_pending():
    """رکوردهای معلق سامان (درگاه در callback بی‌پاسخ داده بود) را دوباره verify می‌کند. cron."""
    for record in MyPayment.objects.filter(gateway_slug="saman", status="returned"):
        extra = (record.raw or {}).get("callback_extra")
        try:
            result = get_gateway("saman").verify(
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
            record.save()
        else:
            record.status = "failed"
            record.error_message = result.error_message or ""
            record.save()
```
</div>

### برگشت وجه (reverse)

<div dir="ltr">

```python
gw = get_gateway("saman")
result = gw.reverse(ref_num="RN50")   # RefNum همان تراکنش
```
</div>

### نکات اختصاصی سامان در حالت ۲

- **هدایت:** فرم POST auto-submit با فیلد `Token` به `result.redirect_url` (درگاه
  کلاسیک) — نه GET ساده و نه neo-pg. Referrer باید از فرمِ سایت خودت برود.
- **پیدا کردن رکورد:** با `order_id`(==`ResNum`) — چون توکن در callback نیست.
- **`extra`:** ضروری — `ref_num`(==`RefNum`) و `state`. verify با `RefNum` انجام
  می‌شود نه توکن.
- **idempotency:** حتماً قبل از verify چک کن `status == "complete"` نباشد (سامان یک
  `RefNum` را بارها verify می‌کند).

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

جزئیات کامل و نمونه‌ی management command + cron:
[README.md](README.md#در-دسترس-نبودن-درگاه-هنگام-verify-مهم--برای-همهی-درگاهها).

## کد آماده‌ی اجرا

- [`scripts/django_saman.py`](../../scripts/django_saman.py) — کد هر دو حالت.
- [`scripts/test_saman.py`](../../scripts/test_saman.py) — تست با ترمینال واقعی + IP ثبت‌شده.
</div>
