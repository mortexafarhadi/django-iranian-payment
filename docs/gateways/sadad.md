# راهنمای اتصال درگاه سداد (Sadad — بانک ملی)

سداد درگاه پرداخت اینترنتی بانک ملی ایران است. از REST/JSON (WebApi) و امضای
**3DES (ECB, PKCS7)** برای `SignData` استفاده می‌کند.

- **وضعیت:** ⚠️ **تجربی** — کد از مستند رسمی، با sandbox/کلید واقعی تست نشده. در
  registry عمومی نیست؛ باید صریحاً register شود.
- **هدایت کاربر:** redirect ساده (GET) به `.../Purchase?Token=<token>`.
- **callback:** POST با فیلدهای `Token`، `ResCode`، `OrderId`.
- **وابستگی اختیاری:** `[sadad]` (pycryptodome).
- **sandbox:** ⚠️ URL سندباکس جدا ندارد؛ فلگ `sandbox` بی‌اثر است.
- **پیش‌نیاز:** `MerchantId`، `TerminalId`، `TerminalKey` (Base64، پس از دیکد ۱۶ یا
  ۲۴ بایت) + ثبت IP.
- **مبلغ:** ریال. `order_id` باید عددی باشد.

> ⚠️ **پنجره‌ی ۱۵ دقیقه‌ای:** verify باید ظرف ۱۵ دقیقه پس از شروع زده شود وگرنه مبلغ
> برمی‌گردد. `ResCode=100` در verify یعنی DUPLICATE (قبلاً تأیید شده). authority همان
> `Token` است (فیلد callback با حرف بزرگ `Token`).

این راهنما دو حالت دارد و هر حالت کامل و مستقل است:
- [حالت ۱: پکیج دیتابیس را مدیریت می‌کند](#حالت-۱)
- [حالت ۲: خودت دیتابیس را مدیریت می‌کنی](#حالت-۲)

---

## نصب

```bash
pip install "django-iranian-payment[sadad]"
# pycryptodome برای 3DES لازم است.
```

---

<a id="حالت-۱"></a>
## حالت ۱: پکیج دیتابیس را مدیریت می‌کند

### قدم ۱: settings.py

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
        "sadad": {
            "merchant_id": "1234",          # شناسه پذیرنده
            "terminal_id": "5678",          # شناسه ترمینال
            "terminal_key": "BASE64_KEY==", # کلید پذیرنده Base64
            # ⚠️ کلید "sandbox" برای سداد بی‌اثر است.
        },
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
        from django_iranian_payment.core.experimental.sadad import SadadGateway
        _REGISTRY.setdefault("sadad", SadadGateway)
```

### قدم ۳: migration و url ها

```bash
python manage.py migrate
```

```python
# project/urls.py
from django.urls import path, include

urlpatterns = [
    path("payment/", include("django_iranian_payment.contrib.django.urls")),
]
```

مسیرها:

```
GET  /payment/go/<payment_id>/     → هدایت به درگاه
POST /payment/callback/sadad/      → برگشت از بانک (POST)
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
    order_id = "5001"   # عددی
    amount = 400_000    # ریال
    callback_url = request.build_absolute_uri(
        reverse("iranian_payment:callback", kwargs={"slug": "sadad"})
    )

    try:
        payment, redirect_url = start_payment(
            slug="sadad",
            amount=amount,
            callback_url=callback_url,
            order_id=order_id,
            description="خرید آنلاین",
        )
    except GatewayError as e:
        return HttpResponse(f"خطا در اتصال به سداد: {e}", status=502)

    return HttpResponseRedirect(redirect_url)


def payment_result(request):
    status = request.GET.get("payment_status")
    order_id = request.GET.get("order_id", "")
    if status == "success":
        payment = Payment.objects.filter(
            order_id=order_id, status=PaymentStatus.COMPLETE
        ).first()
        if payment:
            return HttpResponse(f"پرداخت سداد موفق! کد پیگیری: {payment.reference_id}")
    elif status == "failed":
        return HttpResponse("پرداخت ناموفق.")
    return HttpResponse("نتیجه نامشخص.", status=400)
```

### جریان کامل حالت ۱

1. `checkout` → `start_payment` (SignData با 3DES) → رکورد با `authority`(=Token)
   ذخیره می‌شود → کاربر به سداد می‌رود.
2. کاربر پرداخت می‌کند → سداد با **POST** به `/payment/callback/sadad/` برمی‌گردد
   (Token, ResCode, OrderId).
3. view callback پکیج رکورد را با `Token` پیدا می‌کند، `ResCode` را چک می‌کند و در
   صورت موفق verify می‌زند (ظرف ۱۵ دقیقه).

---

<a id="حالت-۲"></a>
## حالت ۲: خودت دیتابیس را مدیریت می‌کنی

### قدم ۱: settings.py (بدون افزودن اپ پکیج)

```python
IRANIAN_PAYMENT = {
    "currency": "rial",  # واحد ورودی مبلغ: "rial" (پیش‌فرض) یا "toman"
    "sandbox": False,
    "gateways": {
        "sadad": {
            "merchant_id": "1234",
            "terminal_id": "5678",
            "terminal_key": "BASE64_KEY==",
        },
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
        from django_iranian_payment.core.experimental.sadad import SadadGateway
        _REGISTRY.setdefault("sadad", SadadGateway)
```

### قدم ۳: مدل خودت

```python
# yourapp/models.py
from django.db import models


class MyPayment(models.Model):
    gateway_slug = models.CharField(max_length=32, db_index=True)
    order_id     = models.CharField(max_length=128, db_index=True)
    amount       = models.BigIntegerField()
    amount_sent  = models.BigIntegerField(default=0)
    authority    = models.CharField(max_length=255, blank=True, db_index=True)  # Token
    status       = models.CharField(max_length=16, default="waiting", db_index=True)
    reference_id = models.CharField(max_length=255, blank=True)   # RetrivalRefNo
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
    path("pay/sadad/",          views.checkout, name="sd-checkout"),
    path("pay/callback/sadad/", views.callback, name="sd-callback"),
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
    order_id = "5001"   # عددی
    amount = 400_000    # ریال
    callback_url = request.build_absolute_uri(reverse("sd-callback"))

    record = MyPayment.objects.create(
        gateway_slug="sadad",
        order_id=order_id,
        amount=amount,
        callback_url=callback_url,
        status="waiting",
    )

    gw = get_gateway("sadad")
    try:
        result = gw.initiate(
            PaymentRequest(amount=amount, callback_url=callback_url, order_id=order_id)
        )
    except GatewayError as e:
        record.status = "failed"
        record.error_message = str(e)
        record.save()
        return HttpResponse(f"خطا در اتصال به سداد: {e}", status=502)

    record.authority = result.authority        # Token
    record.amount_sent = result.amount_to_send  # مرجع یکتا برای verify
    record.status = "redirect"
    record.save()
    return HttpResponseRedirect(result.redirect_url)
```

### قدم ۶: view بازگشت (POST) و verify با Token

```python
def callback(request):
    p = request.POST   # سداد با POST برمی‌گردد
    token = p.get("Token")   # ⚠️ حرف بزرگ
    if not token:
        return HttpResponse("Token در callback نبود.", status=400)

    record = MyPayment.objects.filter(gateway_slug="sadad", authority=token).first()
    if record is None:
        return HttpResponse("رکورد یافت نشد.", status=404)
    if record.status == "complete":
        return HttpResponse("قبلاً تأیید شده.")

    gw = get_gateway("sadad")
    extra = {"res_code": p.get("ResCode")} if p.get("ResCode") else None
    result = gw.verify(
        authority=token,
        amount=record.amount_sent,   # ⚠️ نه record.amount
        order_id=record.order_id,
        extra=extra,   # اختیاری: اگر ResCode ناموفق باشد بدون تماس با بانک رد می‌شود
    )

    if result.is_success:
        record.status = "complete"
        record.reference_id = result.reference_id or ""   # RetrivalRefNo
        record.card_number = result.card_number or ""
        record.save()
        return HttpResponse(f"پرداخت سداد موفق! کد پیگیری: {record.reference_id}")

    record.status = "failed"
    record.error_message = result.error_message or ""
    record.save()
    return HttpResponse(f"پرداخت ناموفق: {record.error_message}")
```

### نکات اختصاصی سداد در حالت ۲

- **هدایت:** GET ساده به `Purchase?Token=<token>`.
- **پیدا کردن رکورد:** با `authority`(==`Token`، حرف بزرگ در callback).
- **`extra`:** اختیاری — اگر `ResCode` بدهی و ناموفق باشد، بدون تماس با بانک رد می‌شود.
- **پنجره‌ی زمانی:** verify را ظرف ۱۵ دقیقه بزن وگرنه مبلغ برمی‌گردد.

---

## کد آماده‌ی اجرا

- [`scripts/django_sadad.py`](../../scripts/django_sadad.py) — کد هر دو حالت.
- [`scripts/test_sadad.py`](../../scripts/test_sadad.py) — تست با merchant/terminal/key واقعی.
