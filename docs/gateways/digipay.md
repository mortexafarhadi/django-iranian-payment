<div dir="rtl">

# راهنمای اتصال درگاه دیجی‌پی (DigiPay)

دیجی‌پی درگاه پرداخت دیجی‌کالا است. برای احراز هویت از **OAuth2** و برای پرداخت از
REST/JSON استفاده می‌کند.

- **وضعیت:** ⚠️ **تجربی** — کد کامل از مستند رسمی، با کلید واقعی تست نشده. در
  registry عمومی نیست؛ باید صریحاً register شود.
- **هدایت کاربر:** redirect ساده (GET) به `redirectUrl` که از پاسخ API خوانده می‌شود.
- **callback:** فیلدهای `trackingCode`، `providerId`، `result`.
- **sandbox:** بله — محیط UAT/staging (`uat.mydigipay.info`). فلگ `sandbox` مؤثر است.
- **پیش‌نیاز:** پنج فیلد اجباری: `username`، `password`، `client_id`، `client_secret`،
  `provider_id`.
- **مبلغ:** ریال.

> ⚠️ **نکات مهم دیجی‌پی:**
> - هر `initiate`/`verify` ابتدا یک OAuth2 token تازه می‌گیرد (بدون state).
> - کلید موفقیت `result.status == 0` است (نه HTTP status code).
> - callback **`ticket` (authority) را برنمی‌گرداند**؛ رکورد را با `providerId`
>   (==`order_id` که خودت فرستادی) پیدا کن.
> - verify به `trackingCode` نیاز دارد و `providerId` را دوباره می‌فرستد (پکیج آن را
>   از `order_id` می‌گیرد) — باید با تراکنش ثبت‌شده تطبیق داشته باشد.

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
        "digipay": {
            "username": "your-username",
            "password": "your-password",
            "client_id": "your-client-id",
            "client_secret": "your-client-secret",
            "provider_id": "your-provider-id",
            "sandbox": True,   # ← sandbox مجزای دیجی‌پی (uat.mydigipay.info)
            # "ticket_type": 11,   # اختیاری؛ پیش‌فرض ۱۱ (UPG)
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
        from django_iranian_payment.core.experimental.digipay import DigipayGateway
        _REGISTRY.setdefault("digipay", DigipayGateway)
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
GET      /payment/go/<payment_id>/      → هدایت به درگاه
GET|POST /payment/callback/digipay/     → برگشت از بانک
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
from django_iranian_payment.core.exceptions import GatewayError


def checkout(request):
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

    return HttpResponseRedirect(redirect_url)


def payment_result(request):
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
    return HttpResponse("نتیجه نامشخص.", status=400)
```
</div>

### جریان کامل حالت ۱

1. `checkout` → `start_payment` (OAuth2 token + tickets/business) → رکورد با
   `authority`(=ticket) و `order_id`(=providerId) ذخیره می‌شود → کاربر به دیجی‌پی می‌رود.
2. کاربر پرداخت می‌کند → دیجی‌پی به `/payment/callback/digipay/` برمی‌گردد
   (trackingCode, providerId, result).
3. view callback پکیج رکورد را با `providerId`(==order_id) پیدا می‌کند،
   `trackingCode`/`result` را به‌عنوان `extra` به verify می‌دهد (purchases/verify).

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
        "digipay": {
            "username": "your-username",
            "password": "your-password",
            "client_id": "your-client-id",
            "client_secret": "your-client-secret",
            "provider_id": "your-provider-id",
            "sandbox": True,   # sandbox مجزای دیجی‌پی
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
        from django_iranian_payment.core.experimental.digipay import DigipayGateway
        _REGISTRY.setdefault("digipay", DigipayGateway)
```
</div>

### قدم ۳: مدل خودت

<div dir="ltr">

```python
# yourapp/models.py
from django.db import models


class MyPayment(models.Model):
    gateway_slug = models.CharField(max_length=32, db_index=True)
    order_id     = models.CharField(max_length=128, db_index=True)   # == providerId
    amount       = models.BigIntegerField()
    amount_sent  = models.BigIntegerField(default=0)
    authority    = models.CharField(max_length=255, blank=True, db_index=True)  # ticket
    status       = models.CharField(max_length=16, default="waiting", db_index=True)
    reference_id = models.CharField(max_length=255, blank=True)   # rrn
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
    path("pay/digipay/",          views.checkout, name="dp-checkout"),
    path("pay/callback/digipay/", views.callback, name="dp-callback"),
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
from django_iranian_payment.core.exceptions import GatewayError
from .models import MyPayment


def checkout(request):
    order_id = "DIGIPAY-ORDER-001"   # همین در callback به‌عنوان providerId برمی‌گردد
    amount = 350_000                 # ریال
    callback_url = request.build_absolute_uri(reverse("dp-callback"))

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

    record.authority = result.authority        # ticket (در callback برنمی‌گردد)
    record.amount_sent = result.amount_to_send  # مرجع یکتا برای verify
    record.status = "redirect"
    record.save()
    return HttpResponseRedirect(result.redirect_url)
```
</div>

### قدم ۶: view بازگشت و verify با trackingCode

<div dir="ltr">

```python
def callback(request):
    params = request.POST if request.method == "POST" else request.GET
    provider_id = params.get("providerId")   # == order_id ما
    if not provider_id:
        return HttpResponse("providerId در callback نبود.", status=400)

    # ⚠️ دیجی‌پی ticket را برنمی‌گرداند → با order_id(==providerId) پیدا کن.
    record = MyPayment.objects.filter(
        gateway_slug="digipay", order_id=provider_id
    ).first()
    if record is None:
        return HttpResponse("رکورد یافت نشد.", status=404)
    if record.status == "complete":
        return HttpResponse("قبلاً تأیید شده.")

    gw = get_gateway("digipay")
    result = gw.verify(
        authority=record.authority,
        amount=record.amount_sent,   # ⚠️ نه record.amount
        order_id=record.order_id,    # == providerId برای verify
        extra={
            "tracking_code": params.get("trackingCode"),   # ضروری
            "result": params.get("result"),
        },
    )

    if result.is_success:
        record.status = "complete"
        record.reference_id = result.reference_id or ""   # rrn
        record.save()
        return HttpResponse(f"پرداخت موفق! کد پیگیری: {record.reference_id}")

    record.status = "failed"
    record.error_message = result.error_message or ""
    record.save()
    return HttpResponse(f"پرداخت ناموفق: {record.error_message}")
```
</div>

### نکات اختصاصی دیجی‌پی در حالت ۲

- **هدایت:** GET ساده به `result.redirect_url` (از پاسخ API).
- **پیدا کردن رکورد:** با `order_id`(==`providerId`) — چون `ticket` در callback نیست.
- **`extra`:** ضروری — `tracking_code`(==`trackingCode`) نباشد verify خطا می‌دهد.
- **OAuth2:** هر فراخوانی توکن تازه می‌گیرد؛ نیازی به مدیریت توکن نداری.

---

## کد آماده‌ی اجرا

- [`scripts/django_digipay.py`](../../scripts/django_digipay.py) — کد هر دو حالت.
- [`scripts/test_digipay.py`](../../scripts/test_digipay.py) — تست با اعتبارنامه‌ی کامل.
</div>
