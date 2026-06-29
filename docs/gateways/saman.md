# راهنمای اتصال درگاه سامان (SEP — Saman Electronic Payment)

سامان درگاه پرداخت اینترنتی بانک سامان با REST/JSON و flow مبتنی بر Token است.

- **وضعیت:** ⚠️ **تجربی** — کد کامل از مستند رسمی، ولی با ترمینال/sandbox واقعی
  تست نشده. در registry عمومی نیست؛ برای استفاده باید صریحاً register شود.
- **هدایت کاربر:** redirect ساده (GET) به `.../SendToken?token=<token>`. (مستند بانک
  فرم POST توصیه می‌کند؛ اگر بانک به GET ایراد گرفت مثل ملت فرم POST بساز.)
- **callback:** POST با فیلدهای `State`، `Status`، `RefNum`، `ResNum`، `RRN`.
- **sandbox:** ⚠️ URL سندباکس جدا ندارد؛ فلگ `sandbox` بی‌اثر است. تست با ترمینال
  واقعی روی همان آدرس عملیاتی.
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

```bash
pip install django-iranian-payment
```

---

<a id="حالت-۱"></a>
## حالت ۱: پکیج دیتابیس را مدیریت می‌کند

### قدم ۱: settings.py

```python
INSTALLED_APPS = [
    # ...
    "django_iranian_payment.contrib.django",
    "yourapp",   # برای ثبت درگاه تجربی در AppConfig.ready (قدم ۲)
]

IRANIAN_PAYMENT = {
    "currency": "rial",  # واحد ورودی مبلغ: "rial" (پیش‌فرض) یا "toman"
    "sandbox": False,
    "gateways": {
        "saman": {
            "terminal_id": "123456789",   # شماره ترمینال از پرداخت الکترونیک سامان
            # اختیاری برای neo-pg: "redirect_url": "https://sep.shaparak.ir/OnlinePG/SendToken"
            # ⚠️ کلید "sandbox" برای سامان بی‌اثر است (URL سندباکس جدا ندارد).
        },
    },
}
```

### قدم ۲: ثبت درگاه تجربی در registry

چون سامان در registry عمومی نیست، آن را در `AppConfig.ready` ثبت کن:

```python
# yourapp/apps.py
from django.apps import AppConfig


class YourAppConfig(AppConfig):
    name = "yourapp"

    def ready(self):
        from django_iranian_payment.core.gateways import _REGISTRY
        from django_iranian_payment.core.experimental.saman import SamanGateway
        _REGISTRY.setdefault("saman", SamanGateway)
```

### قدم ۳: migration و url ها

```bash
python manage.py migrate
```

```python
# project/urls.py
from django.urls import path, include

urlpatterns = [
    # ...
    path("payment/", include("django_iranian_payment.contrib.django.urls")),
]
```

مسیرها:

```
GET  /payment/go/<payment_id>/      → هدایت به درگاه (GET)
POST /payment/callback/saman/       → برگشت از بانک (POST)
```

### قدم ۴: view های خودت

```python
# yourapp/views.py
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse

from django_iranian_payment.contrib.django.services import start_payment
from django_iranian_payment.contrib.django.models import Payment, PaymentStatus
from django_iranian_payment.core.exceptions import GatewayError


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

    return HttpResponseRedirect(redirect_url)


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
    return HttpResponse("نتیجه نامشخص.", status=400)
```

### جریان کامل حالت ۱

1. `checkout` → `start_payment` رکورد با `authority`(=token) و `amount_sent` ذخیره
   می‌کند → کاربر به سامان می‌رود.
2. کاربر پرداخت می‌کند → سامان با **POST** به `/payment/callback/saman/` برمی‌گردد
   (State, Status, RefNum, ResNum, ...).
3. view callback پکیج رکورد را با `ResNum`(==order_id) پیدا می‌کند، `RefNum`/`State`
   را به‌عنوان `extra` به verify می‌دهد، و نتیجه را ذخیره می‌کند.

---

<a id="حالت-۲"></a>
## حالت ۲: خودت دیتابیس را مدیریت می‌کنی

### قدم ۱: settings.py (بدون افزودن اپ پکیج)

```python
IRANIAN_PAYMENT = {
    "currency": "rial",  # واحد ورودی مبلغ: "rial" (پیش‌فرض) یا "toman"
    "sandbox": False,
    "gateways": {
        "saman": {"terminal_id": "123456789"},
    },
}
```

### قدم ۲: ثبت درگاه تجربی

```python
# yourapp/apps.py
from django.apps import AppConfig


class YourAppConfig(AppConfig):
    name = "yourapp"

    def ready(self):
        from django_iranian_payment.core.gateways import _REGISTRY
        from django_iranian_payment.core.experimental.saman import SamanGateway
        _REGISTRY.setdefault("saman", SamanGateway)
```

### قدم ۳: مدل خودت

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

### قدم ۴: url های خودت

```python
# yourapp/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("pay/saman/",          views.checkout, name="sm-checkout"),
    path("pay/callback/saman/", views.callback, name="sm-callback"),
]
```

### قدم ۵: view شروع پرداخت

```python
# yourapp/views.py
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse

from django_iranian_payment import get_gateway
from django_iranian_payment.core.models import PaymentRequest
from django_iranian_payment.core.exceptions import GatewayError
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
    return HttpResponseRedirect(result.redirect_url)
```

### قدم ۶: view بازگشت (POST) و verify با RefNum

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

    gw = get_gateway("saman")
    result = gw.verify(
        authority=record.authority,
        amount=record.amount_sent,   # ⚠️ نه record.amount
        order_id=record.order_id,
        extra={"ref_num": p.get("RefNum"), "state": p.get("State")},
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
```

### برگشت وجه (reverse)

```python
gw = get_gateway("saman")
result = gw.reverse(ref_num="RN50")   # RefNum همان تراکنش
```

### نکات اختصاصی سامان در حالت ۲

- **هدایت:** GET ساده.
- **پیدا کردن رکورد:** با `order_id`(==`ResNum`) — چون توکن در callback نیست.
- **`extra`:** ضروری — `ref_num`(==`RefNum`) و `state`. verify با `RefNum` انجام
  می‌شود نه توکن.
- **idempotency:** حتماً قبل از verify چک کن `status == "complete"` نباشد (سامان یک
  `RefNum` را بارها verify می‌کند).

---

## کد آماده‌ی اجرا

- [`scripts/django_saman.py`](../../scripts/django_saman.py) — کد هر دو حالت.
- [`scripts/test_saman.py`](../../scripts/test_saman.py) — تست با ترمینال واقعی + IP ثبت‌شده.
