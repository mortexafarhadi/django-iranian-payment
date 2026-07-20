<div dir="rtl">

# راهنمای اتصال درگاه ایران‌کیش (IranKish)

ایران‌کیش درگاه پرداخت اینترنتی گروه توسن/شاپرک است. برای ساخت
`authenticationEnvelope` از رمزنگاری **AES + RSA + SHA256** استفاده می‌کند.

- **وضعیت:** ⚠️ **تجربی** — کد کامل از مستند رسمی، با ترمینال/sandbox واقعی تست
  نشده. در registry عمومی نیست؛ باید صریحاً register شود.
- **هدایت کاربر:** redirect (GET) به `redirect_base + token`. (مستند بانک فرم POST با
  فیلد `tokenIdentity` توصیه می‌کند؛ اگر بانک به GET ایراد گرفت مثل ملت فرم POST بساز.)
- **callback:** POST با فیلدهای `resultCode`، `token`، `referenceId`.
- **وابستگی اختیاری:** `[irankish]` (pycryptodome + rsa).
- **sandbox:** ⚠️ URL سندباکس جدا ندارد؛ فلگ `sandbox` بی‌اثر است.
- **پیش‌نیاز:** ترمینال واقعی + کلید عمومی RSA بانک (فایل `.pem`) + ثبت IP.
- **امنیت:** برخلاف کد مرجع، پکیج SSL را هیچ‌گاه خاموش نمی‌کند.
- **مبلغ:** ریال.

> ⚠️ verify به **هم `token` و هم `referenceId`** نیاز دارد که هر دو در callbackِ POST
> برمی‌گردند.

این راهنما دو حالت دارد و هر حالت کامل و مستقل است:
- [حالت ۱: پکیج دیتابیس را مدیریت می‌کند](#حالت-۱)
- [حالت ۲: خودت دیتابیس را مدیریت می‌کنی](#حالت-۲)

---

## نصب

<div dir="ltr">

```bash
pip install "django-iranian-payment[irankish]"
# pycryptodome + rsa برای رمزنگاری لازم است.
```
</div>

کلید عمومی RSA ایران‌کیش را از پورتال/تیم فنی بانک بگیر و در مسیری ذخیره کن.

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
        "irankish": {
            "terminal_id": "xxxxxxxx",       # از ایران‌کیش
            "acceptor_id": "xxxxxxxx",       # از ایران‌کیش
            "pass_phrase": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",  # hex
            "public_key": "/path/to/irankish_public.pem",       # مسیر کلید RSA بانک
            # ⚠️ کلید "sandbox" برای ایران‌کیش بی‌اثر است.
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
        from django_iranian_payment.core.experimental.irankish import IrankishGateway
        _REGISTRY.setdefault("irankish", IrankishGateway)
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
GET  /payment/go/<payment_id>/        → هدایت به درگاه
POST /payment/callback/irankish/      → برگشت از بانک (POST)
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
    order_id = "IK-ORDER-001"
    amount = 250_000  # ریال
    callback_url = request.build_absolute_uri(
        reverse("iranian_payment:callback", kwargs={"slug": "irankish"})
    )

    try:
        payment, redirect_url = start_payment(
            slug="irankish",
            amount=amount,
            callback_url=callback_url,
            order_id=order_id,
            description="خرید از سایت",
        )
    except GatewayError as e:
        return HttpResponse(f"خطا در اتصال به ایران‌کیش: {e}", status=502)

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

1. `checkout` → `start_payment` (رمزنگاری AES+RSA و tokenization) → رکورد با
   `authority`(=token) ذخیره می‌شود → کاربر به ایران‌کیش می‌رود.
2. کاربر پرداخت می‌کند → ایران‌کیش با **POST** به `/payment/callback/irankish/`
   برمی‌گردد (resultCode, token, referenceId).
3. view callback پکیج رکورد را با `token` پیدا می‌کند، `referenceId`/`token`/`resultCode`
   را به‌عنوان `extra` به verify می‌دهد (confirmation/purchase).

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
        "irankish": {
            "terminal_id": "xxxxxxxx",
            "acceptor_id": "xxxxxxxx",
            "pass_phrase": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "public_key": "/path/to/irankish_public.pem",
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
        from django_iranian_payment.core.experimental.irankish import IrankishGateway
        _REGISTRY.setdefault("irankish", IrankishGateway)
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
    authority    = models.CharField(max_length=255, blank=True, db_index=True)  # token
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
    path("pay/irankish/",          views.checkout, name="ik-checkout"),
    path("pay/callback/irankish/", views.callback, name="ik-callback"),
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
    order_id = "IK-ORDER-001"
    amount = 250_000  # ریال
    callback_url = request.build_absolute_uri(reverse("ik-callback"))

    record = MyPayment.objects.create(
        gateway_slug="irankish",
        order_id=order_id,
        amount=amount,
        callback_url=callback_url,
        status="waiting",
    )

    gw = get_gateway("irankish")
    try:
        result = gw.initiate(
            PaymentRequest(amount=amount, callback_url=callback_url, order_id=order_id)
        )
    except GatewayError as e:
        record.status = "failed"
        record.error_message = str(e)
        record.save()
        return HttpResponse(f"خطا در اتصال به ایران‌کیش: {e}", status=502)

    record.authority = result.authority        # token
    record.amount_sent = result.amount_to_send  # مرجع یکتا برای verify
    record.status = "redirect"
    record.save()
    return HttpResponseRedirect(result.redirect_url)
```
</div>

### قدم ۶: view بازگشت (POST) و verify با token + referenceId

<div dir="ltr">

```python
def callback(request):
    p = request.POST   # ایران‌کیش با POST برمی‌گردد
    token = p.get("token")
    if not token:
        return HttpResponse("token در callback نبود.", status=400)

    record = MyPayment.objects.filter(gateway_slug="irankish", authority=token).first()
    if record is None:
        return HttpResponse("رکورد یافت نشد.", status=404)
    if record.status == "complete":
        return HttpResponse("قبلاً تأیید شده.")

    extra = {k: v for k, v in {
        "reference_id": p.get("referenceId"),   # ضروری
        "token": token,
        "result_code": p.get("resultCode"),
    }.items() if v}

    # پیش‌علامت: «returned» + ذخیره‌ی extra در raw، پیش از تماس با بانک، تا خطای شبکه
    # رکورد را گم نکند و reverify_pending با همین extra (reference_id) بگیردش.
    record.status = "returned"
    record.raw = {**(record.raw or {}), "callback_extra": extra}
    record.save(update_fields=["status", "raw", "updated_at"])

    gw = get_gateway("irankish")
    try:
        result = gw.verify(
            authority=token,
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
        record.save()
        return HttpResponse(f"پرداخت موفق! کد پیگیری: {record.reference_id}")

    record.status = "failed"
    record.error_message = result.error_message or ""
    record.save()
    return HttpResponse(f"پرداخت ناموفق: {record.error_message}")


def reverify_pending():
    """رکوردهای معلق ایران‌کیش (درگاه در callback بی‌پاسخ داده بود) را دوباره verify می‌کند. cron."""
    for record in MyPayment.objects.filter(gateway_slug="irankish", status="returned"):
        extra = (record.raw or {}).get("callback_extra")
        try:
            result = get_gateway("irankish").verify(
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

### نکات اختصاصی ایران‌کیش در حالت ۲

- **هدایت:** GET ساده (یا فرم POST با فیلد `tokenIdentity` اگر بانک خواست).
- **پیدا کردن رکورد:** با `authority`(==`token`) که در callback برمی‌گردد.
- **`extra`:** ضروری — `reference_id`(==`referenceId`) نباشد verify خطا می‌دهد.
  `token` و `result_code` هم بفرست.

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

- [`scripts/django_irankish.py`](../../scripts/django_irankish.py) — کد هر دو حالت.
- [`scripts/test_irankish.py`](../../scripts/test_irankish.py) — تست با ترمینال/کلید واقعی.
</div>
