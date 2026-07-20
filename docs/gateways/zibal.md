<div dir="rtl">

# راهنمای اتصال درگاه زیبال (Zibal)

زیبال درگاه پرداخت اینترنتی ایرانی با REST/JSON است. در **registry عمومی** پکیج
قرار دارد. sandbox آن با `merchant="zibal"` بدون ثبت‌نام و از هر IP قابل تست است.

- **وضعیت:** registry عمومی — فقط sandbox تست‌شده (تراکنش live هنوز تست نشده).
- **هدایت کاربر:** redirect ساده (GET).
- **callback:** GET با پارامترهای `trackId`، `success`، `status`.
- **sandbox:** ⚠️ برخلاف زرین‌پال، با فلگ `sandbox` کنترل **نمی‌شود**؛ با مقدار
  `merchant` کنترل می‌شود (`merchant="zibal"` یعنی تست).
- **مبلغ:** ریال. توجه: در زیبال `authority` همان `trackId` است.

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
        "zibal": {
            "merchant": "zibal",
            # ⚠️ sandbox زیبال با همین مقدار merchant کنترل می‌شود:
            #   "zibal"  → حالت تست (بدون ثبت‌نام)
            #   merchant واقعی از پنل zibal.ir → حالت عملیاتی
            # کلید "sandbox" برای زیبال بی‌اثر است.
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
GET  /payment/go/<payment_id>/      → هدایت کاربر به درگاه
GET  /payment/callback/zibal/       → برگشت از بانک (?trackId=...&success=1)
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
    order_id = "ORDER-3001"
    amount = 200_000  # ریال
    callback_url = request.build_absolute_uri(
        reverse("iranian_payment:callback", kwargs={"slug": "zibal"})
    )

    try:
        payment, redirect_url = start_payment(
            slug="zibal",
            amount=amount,
            callback_url=callback_url,
            order_id=order_id,
            description="خرید از فروشگاه",
            mobile="09120000000",  # اختیاری
        )
    except GatewayError as e:
        return HttpResponse(f"خطا در اتصال به زیبال: {e}", status=502)

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

### قدم ۵: url های app خودت

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

### جریان کامل حالت ۱

1. `checkout` → `start_payment` رکورد می‌سازد، `authority`(=`trackId`) و `amount_sent`
   را ذخیره می‌کند → کاربر به زیبال می‌رود.
2. کاربر پرداخت می‌کند → زیبال به `/payment/callback/zibal/?trackId=...&success=1`
   برمی‌گردد.
3. view callback پکیج رکورد را با `trackId` پیدا می‌کند، verify می‌زند، و به
   `callback_url` سفارش هدایت می‌کند.

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
        "zibal": {"merchant": "zibal"},   # "zibal" = تست؛ merchant واقعی = عملیاتی
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
    order_id     = models.CharField(max_length=128, db_index=True)
    amount       = models.BigIntegerField()
    amount_sent  = models.BigIntegerField(default=0)
    authority    = models.CharField(max_length=255, blank=True, db_index=True)  # trackId
    status       = models.CharField(max_length=16, default="waiting", db_index=True)
    reference_id = models.CharField(max_length=255, blank=True)
    card_number  = models.CharField(max_length=32, blank=True)
    error_message = models.TextField(blank=True)
    callback_url = models.URLField(max_length=500)
    created_at   = models.DateTimeField(auto_now_add=True)
```
</div>

سپس `makemigrations` و `migrate`.

### قدم ۳: url های خودت

<div dir="ltr">

```python
# yourapp/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("pay/zibal/",          views.checkout, name="zb-checkout"),
    path("pay/callback/zibal/", views.callback, name="zb-callback"),
]
```
</div>

### قدم ۴: view شروع پرداخت

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
    order_id = "ORDER-3001"
    amount = 200_000  # ریال
    callback_url = request.build_absolute_uri(reverse("zb-callback"))

    record = MyPayment.objects.create(
        gateway_slug="zibal",
        order_id=order_id,
        amount=amount,
        callback_url=callback_url,
        status="waiting",
    )

    gw = get_gateway("zibal")
    try:
        result = gw.initiate(
            PaymentRequest(amount=amount, callback_url=callback_url, order_id=order_id)
        )
    except GatewayError as e:
        record.status = "failed"
        record.error_message = str(e)
        record.save()
        return HttpResponse(f"خطا در اتصال به زیبال: {e}", status=502)

    record.authority = result.authority        # == trackId
    record.amount_sent = result.amount_to_send  # مرجع یکتا برای verify
    record.status = "redirect"
    record.save()
    return HttpResponseRedirect(result.redirect_url)
```
</div>

### قدم ۵: view بازگشت و verify

<div dir="ltr">

```python
def callback(request):
    # زیبال در callback GET می‌فرستد: ?trackId=...&success=1&status=1
    track_id = request.GET.get("trackId")
    if not track_id:
        return HttpResponse("trackId در callback نبود.", status=400)

    record = MyPayment.objects.filter(gateway_slug="zibal", authority=track_id).first()
    if record is None:
        return HttpResponse("رکورد یافت نشد.", status=404)
    if record.status == "complete":
        return HttpResponse("قبلاً تأیید شده.")

    # پیش‌علامت: پیش از تماس با بانک «returned» بگذار تا خطای شبکه رکورد را گم نکند.
    record.status = "returned"
    record.save(update_fields=["status", "updated_at"])

    gw = get_gateway("zibal")
    try:
        result = gw.verify(
            authority=track_id,
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
        return HttpResponse(f"پرداخت موفق! کد پیگیری: {record.reference_id}")

    record.status = "failed"
    record.error_message = result.error_message or ""
    record.save()
    return HttpResponse(f"پرداخت ناموفق: {record.error_message}")


def reverify_pending():
    """رکوردهای معلق زیبال (درگاه در callback بی‌پاسخ داده بود) را دوباره verify می‌کند. cron."""
    for record in MyPayment.objects.filter(gateway_slug="zibal", status="returned"):
        try:
            result = get_gateway("zibal").verify(
                authority=record.authority,
                amount=record.amount_sent,
                order_id=record.order_id,
            )
        except GatewayConnectionError:
            continue   # هنوز در دسترس نیست؛ دفعه‌ی بعد
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

### نکات اختصاصی زیبال در حالت ۲

- **هدایت:** GET ساده.
- **پیدا کردن رکورد:** با `authority`(==`trackId`).
- **`extra`:** لازم نیست.
- **sandbox/live:** فقط با مقدار `merchant` کنترل می‌شود، نه فلگ `sandbox`.

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

- [`scripts/django_zibal.py`](../../scripts/django_zibal.py) — کد هر دو حالت.
- [`scripts/test_zibal.py`](../../scripts/test_zibal.py) — تست sandbox با `merchant="zibal"`.
</div>
