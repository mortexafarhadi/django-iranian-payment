<div dir="rtl">

# راهنمای اتصال درگاه نکست‌پی (NextPay)

نکست‌پی درگاه پرداخت اینترنتی با REST/JSON است، محبوب برای SMEها و استارت‌آپ‌ها.

- **وضعیت:** ⚠️ **تجربی** — کد از مستند رسمی، با sandbox/کلید واقعی تست نشده. در
  registry عمومی نیست؛ باید صریحاً register شود.
- **هدایت کاربر:** redirect ساده (GET) به `gateway/payment/<trans_id>`.
- **callback:** GET با فیلدهای `trans_id`، `order_id`، `amount`.
- **sandbox:** ⚠️ URL سندباکس جدا ندارد؛ فلگ `sandbox` بی‌اثر است.
- **پیش‌نیاز:** `api_key` واقعی + دامنه/IP ثبت‌شده در پنل (وگرنه `code=-33`).
- **مبلغ:** ریال (پکیج `currency=IRR` می‌فرستد؛ در پنل نکست‌پی به تومان نمایش داده می‌شود).

> ⚠️ **عجیب ولی طبق مستند:** کد موفقیتِ ساخت توکن `code == -1` است (نه ۰).
> کدهای DUPLICATE: `-25` و `-49`. نکست‌پی `refund()` هم دارد. authority همان
> `trans_id` است و verify extra لازم ندارد.

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
    "yourapp",
]

IRANIAN_PAYMENT = {
    "currency": "rial",  # واحد ورودی مبلغ: "rial" (پیش‌فرض) یا "toman"
    "sandbox": False,
    "gateways": {
        "nextpay": {
            "api_key": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            # ⚠️ کلید "sandbox" برای نکست‌پی بی‌اثر است.
        },
    },
}
```
</div>

### قدم ۲: ثبت درگاه تجربی

<div dir="ltr">

```python
# yourapp/apps.py
from django.apps import AppConfig


class YourAppConfig(AppConfig):
    name = "yourapp"

    def ready(self):
        from django_iranian_payment.core.gateways import _REGISTRY
        from django_iranian_payment.core.experimental.nextpay import NextPayGateway
        _REGISTRY.setdefault("nextpay", NextPayGateway)
```
</div>

### قدم ۳: migration و url ها

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
    path("payment/", include("django_iranian_payment.contrib.django.urls")),
]
```
</div>

مسیرها:

<div dir="ltr">

```
GET  /payment/go/<payment_id>/      → هدایت به درگاه
GET  /payment/callback/nextpay/     → برگشت از بانک (GET)
```
</div>

### قدم ۴: view های خودت

<div dir="ltr">

```python
# yourapp/views.py
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse

from django_iranian_payment.contrib.django.services import start_payment
from django_iranian_payment.contrib.django.models import Payment, PaymentStatus
from django_iranian_payment.core.exceptions import GatewayError, GatewayConnectionError


def checkout(request):
    order_id = "NP-ORDER-001"
    amount = 180_000  # ریال
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

    return HttpResponseRedirect(redirect_url)


def payment_result(request):
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

1. `checkout` → `start_payment` رکورد با `authority`(=trans_id) ذخیره می‌کند → کاربر
   به نکست‌پی می‌رود.
2. کاربر پرداخت می‌کند → نکست‌پی به `/payment/callback/nextpay/?trans_id=...&order_id=...`
   برمی‌گردد (GET).
3. view callback پکیج رکورد را با `trans_id` پیدا می‌کند، verify می‌زند (currency=IRR).

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
        "nextpay": {"api_key": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"},
    },
}
```
</div>

### قدم ۲: ثبت درگاه تجربی

<div dir="ltr">

```python
# yourapp/apps.py
from django.apps import AppConfig


class YourAppConfig(AppConfig):
    name = "yourapp"

    def ready(self):
        from django_iranian_payment.core.gateways import _REGISTRY
        from django_iranian_payment.core.experimental.nextpay import NextPayGateway
        _REGISTRY.setdefault("nextpay", NextPayGateway)
```
</div>

### قدم ۳: مدل خودت

<div dir="ltr">

```python
# yourapp/models.py
from django.db import models


class MyPayment(models.Model):
    gateway_slug = models.CharField(max_length=32, db_index=True)
    order_id     = models.CharField(max_length=128, db_index=True)
    amount       = models.BigIntegerField()
    amount_sent  = models.BigIntegerField(default=0)
    authority    = models.CharField(max_length=255, blank=True, db_index=True)  # trans_id
    status       = models.CharField(max_length=16, default="waiting", db_index=True)
    reference_id = models.CharField(max_length=255, blank=True)
    card_number  = models.CharField(max_length=32, blank=True)
    error_message = models.TextField(blank=True)
    callback_url = models.URLField(max_length=500)
    created_at   = models.DateTimeField(auto_now_add=True)
```
</div>

### قدم ۴: url های خودت

<div dir="ltr">

```python
# yourapp/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("pay/nextpay/",          views.checkout, name="np-checkout"),
    path("pay/callback/nextpay/", views.callback, name="np-callback"),
]
```
</div>

### قدم ۵: view شروع پرداخت

<div dir="ltr">

```python
# yourapp/views.py
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse

from django_iranian_payment import get_gateway
from django_iranian_payment.core.models import PaymentRequest
from django_iranian_payment.core.exceptions import GatewayError, GatewayConnectionError
from .models import MyPayment


def checkout(request):
    order_id = "NP-ORDER-001"
    amount = 180_000  # ریال
    callback_url = request.build_absolute_uri(reverse("np-callback"))

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

    record.authority = result.authority        # trans_id
    record.amount_sent = result.amount_to_send  # مرجع یکتا برای verify
    record.status = "redirect"
    record.save()
    return HttpResponseRedirect(result.redirect_url)
```
</div>

### قدم ۶: view بازگشت (GET) و verify

<div dir="ltr">

```python
def callback(request):
    # نکست‌پی در callback GET می‌فرستد: ?trans_id=...&order_id=...&amount=...
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

    # پیش‌علامت: پیش از تماس با بانک «returned» بگذار تا خطای شبکه رکورد را گم نکند.
    record.status = "returned"
    record.save(update_fields=["status", "updated_at"])

    gw = get_gateway("nextpay")
    try:
        result = gw.verify(
            authority=trans_id,
            amount=record.amount_sent,   # ⚠️ نه record.amount
            order_id=record.order_id,
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
        return HttpResponse(f"پرداخت موفق! شماره پیگیری: {record.reference_id}")

    record.status = "failed"
    record.error_message = result.error_message or ""
    record.save()
    return HttpResponse(f"پرداخت ناموفق: {record.error_message}")


def reverify_pending():
    """رکوردهای معلق نکست‌پی (درگاه در callback بی‌پاسخ داده بود) را دوباره verify می‌کند. cron."""
    for record in MyPayment.objects.filter(gateway_slug="nextpay", status="returned"):
        try:
            result = get_gateway("nextpay").verify(
                authority=record.authority,
                amount=record.amount_sent,
                order_id=record.order_id,
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

### استرداد وجه (refund)

<div dir="ltr">

```python
gw = get_gateway("nextpay")
result = gw.refund(trans_id="TRANS9", amount=180_000)
```
</div>

### نکات اختصاصی نکست‌پی در حالت ۲

- **هدایت:** GET ساده.
- **پیدا کردن رکورد:** با `authority`(==`trans_id`).
- **`extra`:** لازم نیست.
- **مبلغ:** پکیج `currency=IRR` می‌فرستد؛ در پنل به تومان دیده می‌شود (طبیعی).

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

- [`scripts/django_nextpay.py`](../../scripts/django_nextpay.py) — کد هر دو حالت.
- [`scripts/test_nextpay.py`](../../scripts/test_nextpay.py) — تست با api_key واقعی.
</div>
