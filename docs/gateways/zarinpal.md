# راهنمای اتصال درگاه زرین‌پال (Zarinpal)

زرین‌پال درگاه پرداخت اینترنتی ایرانی با REST/JSON است. در **registry عمومی** پکیج
قرار دارد (با `get_gateway("zarinpal")` در دسترس است). sandbox آن بدون ثبت‌نام و از
هر IP قابل تست است.

- **وضعیت:** registry عمومی — فقط sandbox تست‌شده (تراکنش live هنوز تست نشده).
- **هدایت کاربر:** redirect ساده (GET).
- **callback:** GET با پارامترهای `Authority` و `Status`.
- **وابستگی اختیاری:** ندارد.
- **مبلغ:** ریال.

این راهنما دو حالت دارد و هر حالت کامل و مستقل است:
- [حالت ۱: پکیج دیتابیس را مدیریت می‌کند](#حالت-۱)
- [حالت ۲: خودت دیتابیس را مدیریت می‌کنی](#حالت-۲)

---

## نصب

```bash
pip install django-iranian-payment
# یا: uv add django-iranian-payment
```

---

<a id="حالت-۱"></a>
## حالت ۱: پکیج دیتابیس را مدیریت می‌کند

در این حالت پکیج رکورد `Payment` را می‌سازد، `authority` و `amount_sent` را ذخیره
می‌کند، verify می‌زند و state را مدیریت می‌کند. تو تقریباً هیچ منطقی نمی‌نویسی.

### قدم ۱: settings.py

```python
INSTALLED_APPS = [
    # ...
    "django_iranian_payment.contrib.django",   # لایه‌ی Django پکیج
]

IRANIAN_PAYMENT = {
    "currency": "rial",  # واحد ورودی مبلغ: "rial" (پیش‌فرض) یا "toman"
    "sandbox": False,   # پیش‌فرض سراسری
    "gateways": {
        "zarinpal": {
            "merchant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            # merchant_id را از پنل زرین‌پال بگیر. برای sandbox هر UUID ۳۶ کاراکتری.
            "sandbox": True,   # ← sandbox مجزای همین درگاه (sandbox.zarinpal.com)
        },
    },
}
```

### قدم ۲: اجرای migration

```bash
python manage.py migrate
# جدول iranian_payment_payment ساخته می‌شود.
```

### قدم ۳: mount کردن url های پکیج

```python
# project/urls.py
from django.urls import path, include

urlpatterns = [
    # ...
    path("payment/", include("django_iranian_payment.contrib.django.urls")),
]
```

مسیرهای ساخته‌شده:

```
GET      /payment/go/<payment_id>/         → هدایت کاربر به درگاه
GET|POST /payment/callback/zarinpal/       → برگشت از بانک (پکیج verify می‌زند)
```

### قدم ۴: view های خودت (checkout و نمایش نتیجه)

```python
# yourapp/views.py
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse

from django_iranian_payment.contrib.django.services import start_payment
from django_iranian_payment.contrib.django.models import Payment, PaymentStatus
from django_iranian_payment.core.exceptions import GatewayError


def checkout(request):
    order_id = "ORDER-2001"
    amount = 150_000  # ریال

    # callback_url باید به مسیر callback پکیج اشاره کند (نه view خودت).
    callback_url = request.build_absolute_uri(
        reverse("iranian_payment:callback", kwargs={"slug": "zarinpal"})
    )

    try:
        payment, redirect_url = start_payment(
            slug="zarinpal",
            amount=amount,
            callback_url=callback_url,
            order_id=order_id,
            description="خرید از فروشگاه",
            mobile="09120000000",   # اختیاری
            email="user@example.com",  # اختیاری
        )
    except GatewayError as e:
        return HttpResponse(f"خطا در اتصال به زرین‌پال: {e}", status=502)

    # کاربر را به درگاه هدایت کن (redirect ساده)
    return HttpResponseRedirect(redirect_url)


def payment_result(request):
    # پکیج بعد از verify به callback_url سفارش با این پارامترها redirect می‌کند:
    #   ?payment_status=success&order_id=ORDER-2001
    status = request.GET.get("payment_status")
    order_id = request.GET.get("order_id", "")

    if status == "success":
        payment = Payment.objects.filter(
            order_id=order_id, status=PaymentStatus.COMPLETE
        ).first()
        if payment:
            return HttpResponse(f"پرداخت موفق! کد پیگیری: {payment.reference_id}")
    elif status == "failed":
        return HttpResponse(f"پرداخت ناموفق برای سفارش {order_id}.")
    return HttpResponse("نتیجه نامشخص.", status=400)
```

### قدم ۵: url های app خودت

```python
# yourapp/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("payment/result/", views.payment_result, name="payment-result"),
]
```

### جریان کامل حالت ۱

1. کاربر `/checkout/` را می‌زند → `start_payment` رکورد `Payment` می‌سازد و
   `authority`/`amount_sent` را ذخیره می‌کند → کاربر به زرین‌پال می‌رود.
2. کاربر پرداخت می‌کند → زرین‌پال او را به `/payment/callback/zarinpal/?Authority=...&Status=OK`
   برمی‌گرداند.
3. view callback پکیج رکورد را با `Authority` پیدا می‌کند، با `amount_sent` صحیح
   verify می‌زند، state را `COMPLETE`/`RETURN_FROM_BANK` می‌کند، و به `callback_url`
   سفارش با `payment_status` هدایت می‌کند.

> نکته‌ی زرین‌پال: در verify مبلغ باید دقیقاً همان مبلغ initiate باشد. پکیج این را
> خودکار با `amount_sent` رعایت می‌کند، حتی اگر کارمزد از مشتری گرفته باشی.

---

<a id="حالت-۲"></a>
## حالت ۲: خودت دیتابیس را مدیریت می‌کنی

در این حالت اپ `contrib.django` لازم **نیست** و migration پکیج هم نمی‌خواهی. فقط از
هسته‌ی بدون state استفاده می‌کنی و رکورد را در مدل خودت ذخیره می‌کنی.

### قدم ۱: settings.py (بدون افزودن اپ پکیج)

```python
# نیازی به افزودن "django_iranian_payment.contrib.django" به INSTALLED_APPS نیست.
IRANIAN_PAYMENT = {
    "currency": "rial",  # واحد ورودی مبلغ: "rial" (پیش‌فرض) یا "toman"
    "sandbox": False,
    "gateways": {
        "zarinpal": {
            "merchant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            "sandbox": True,   # sandbox مجزای زرین‌پال
        },
    },
}
```

### قدم ۲: مدل خودت

```python
# yourapp/models.py
from django.db import models


class MyPayment(models.Model):
    gateway_slug = models.CharField(max_length=32, db_index=True)
    order_id     = models.CharField(max_length=128, db_index=True)
    amount       = models.BigIntegerField()                # مبلغ پایه (ریال)
    amount_sent  = models.BigIntegerField(default=0)       # مبلغ ارسالی به بانک
    authority    = models.CharField(max_length=255, blank=True, db_index=True)
    status       = models.CharField(max_length=16, default="waiting", db_index=True)
    reference_id = models.CharField(max_length=255, blank=True)
    card_number  = models.CharField(max_length=32, blank=True)
    error_message = models.TextField(blank=True)
    callback_url = models.URLField(max_length=500)
    created_at   = models.DateTimeField(auto_now_add=True)
```

سپس `python manage.py makemigrations yourapp && python manage.py migrate`.

### قدم ۳: url های خودت

```python
# yourapp/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("pay/zarinpal/",          views.checkout, name="zp-checkout"),
    path("pay/callback/zarinpal/", views.callback, name="zp-callback"),
]
```

### قدم ۴: view شروع پرداخت (checkout)

```python
# yourapp/views.py
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse

from django_iranian_payment import get_gateway
from django_iranian_payment.core.models import PaymentRequest
from django_iranian_payment.core.exceptions import GatewayError
from .models import MyPayment


def checkout(request):
    order_id = "ORDER-2001"
    amount = 150_000  # ریال
    callback_url = request.build_absolute_uri(reverse("zp-callback"))

    record = MyPayment.objects.create(
        gateway_slug="zarinpal",
        order_id=order_id,
        amount=amount,
        callback_url=callback_url,
        status="waiting",
    )

    gw = get_gateway("zarinpal")   # sandbox از config همین درگاه خوانده می‌شود
    try:
        result = gw.initiate(
            PaymentRequest(amount=amount, callback_url=callback_url, order_id=order_id)
        )
    except GatewayError as e:
        record.status = "failed"
        record.error_message = str(e)
        record.save()
        return HttpResponse(f"خطا در اتصال به زرین‌پال: {e}", status=502)

    # ⚠️ این دو را حتماً ذخیره کن:
    record.authority = result.authority        # برای پیدا کردن رکورد در callback
    record.amount_sent = result.amount_to_send  # مرجع یکتا برای verify
    record.status = "redirect"
    record.save()

    return HttpResponseRedirect(result.redirect_url)
```

### قدم ۵: view بازگشت (callback) و verify

```python
def callback(request):
    # زرین‌پال در callback GET می‌فرستد: ?Authority=...&Status=OK|NOK
    authority = request.GET.get("Authority")
    if not authority:
        return HttpResponse("Authority در callback نبود.", status=400)

    # رکورد را با authority پیدا کن (زرین‌پال order_id را echo نمی‌کند).
    record = MyPayment.objects.filter(
        gateway_slug="zarinpal", authority=authority
    ).first()
    if record is None:
        return HttpResponse("رکورد یافت نشد.", status=404)
    if record.status == "complete":   # idempotent
        return HttpResponse("قبلاً تأیید شده.")

    gw = get_gateway("zarinpal")
    result = gw.verify(
        authority=authority,
        amount=record.amount_sent,   # ⚠️ نه record.amount
        order_id=record.order_id,
        # زرین‌پال extra لازم ندارد.
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
```

### نکات اختصاصی زرین‌پال در حالت ۲

- **هدایت:** GET ساده؛ فقط `HttpResponseRedirect(result.redirect_url)`.
- **پیدا کردن رکورد:** با `authority` (زرین‌پال `order_id` را در callback برنمی‌گرداند).
- **`extra`:** لازم نیست. پارامتر `Status` در callback اطلاعاتی است؛ تصمیم نهایی را
  از `result.is_success` بگیر، نه از `Status` (که قابل دستکاری است).
- **idempotency:** قبل از verify، اگر `status == "complete"` بود دوباره verify نزن.

---

## کد آماده‌ی اجرا

- [`scripts/django_zarinpal.py`](../../scripts/django_zarinpal.py) — کد هر دو حالت.
- [`scripts/test_zarinpal.py`](../../scripts/test_zarinpal.py) — تست sandbox با
  merchant_id واقعی (دو مرحله‌ای: ساخت پرداخت، سپس verify با authority بازگشتی).
