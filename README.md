# django-iranian-payment

درگاه‌های پرداخت ایرانی برای Django، با معماری دو لایه:

- **لایه‌ی ساده (توصیه‌شده):** یک اپ Django اختیاری که خودش رکورد پرداخت، ذخیره‌ی
  `authority`، تأیید، و مدیریت وضعیت تراکنش را انجام می‌دهد. کاربر تقریباً هیچ
  منطقی نمی‌نویسد.
- **لایه‌ی هسته (پیشرفته):** درگاه‌های بدون state که در هر محیطی (حتی غیر Django یا
  async) قابل استفاده‌اند. کاربر خودش `authority` را ذخیره و تأیید را مدیریت می‌کند.

همه‌ی مبالغ به **ریال** هستند.

## درگاه‌های آماده و تست‌شده

زرین‌پال، زیبال (REST، تست واقعی موفق) و ملت (SOAP، پیاده‌سازی کامل از مستند رسمی).

> ⚠️ **ملت** نیاز به `zeep` دارد: `pip install "django-iranian-payment[soap]"`.
> ملت دومرحله‌ای است؛ حالت پیش‌فرض `verify_settle` (تأیید+واریز اتمیک) توصیه می‌شود.
> برای واریز با تأخیر، `settle_mode="verify_only"` را در config بگذار و خودت
> `settle()` را صدا بزن (وگرنه بانک در ۳ ساعت Autoreversal می‌زند).

> ⏸️ **پی‌آی‌آر (Pay.ir) معلق شد.** این درگاه قبلاً کار می‌کرد، اما به‌دلیل خطای
> دسترسی و بی‌ثباتی شبکهٔ پرداخت پی موقتاً از درگاه‌های عمومی خارج و به
> `core.experimental` منتقل شده است. `get_gateway("pay_ir")` دیگر کار نمی‌کند.
> کد سالم است و در صورت نیاز با import صریح در دسترس است:
> `from django_iranian_payment.core.experimental import PayIrGateway`
>
> ⏸️ **آیدی‌پی (IDPay) هم معلق شد.** سرویس از کار افتاده گزارش شد (آخرین فعالیت
> پشتیبانی حوالی ۲۰۲۵-۱۱-۲۰). `get_gateway("idpay")` دیگر کار نمی‌کند. کد سالم و
> با import صریح در دسترس است:
> `from django_iranian_payment.core.experimental import IDPayGateway`

درگاه‌های بانکی دیگر (ملت، ملی، سامان، پاسارگاد و ...) در ماژول `core.experimental`
قرار دارند: تست‌نشده، فقط برای توسعه، و در پروداکشن نباید استفاده شوند.

## نصب

```bash
pip install django-iranian-payment
# برای درگاه‌های SOAP (ملت، سپه، پارسیان):
pip install "django-iranian-payment[soap]"
```

## تنظیمات

در `settings.py`:

```python
IRANIAN_PAYMENT = {
    "sandbox": True,  # روی پروداکشن False
    "gateways": {
        "zarinpal": {"merchant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"},
        "zibal": {"merchant": "zibal"},
        "mellat": {
            "terminal_id": "1234",
            "username": "...",
            "password": "...",
            "settle_mode": "verify_settle",  # یا "verify_only"
        },
    },
}
```

برای استفاده از لایه‌ی ساده (مدل و ردیابی خودکار)، اپ را هم اضافه کن:

```python
INSTALLED_APPS = [
    # ...
    "django_iranian_payment.contrib.django",
]
```

سپس migrate:

```bash
python manage.py migrate
```

و مسیرهای داخلی را در `urls.py` پروژه اضافه کن:

```python
from django.urls import path, include

urlpatterns = [
    # ...
    path("payment/", include("django_iranian_payment.contrib.django.urls")),
]
```

---

## روش ۱: لایه‌ی ساده (توصیه‌شده)

پکیج خودش رکورد می‌سازد، `authority` را ذخیره می‌کند، و تأیید را انجام می‌دهد.

### شروع پرداخت

```python
from django.shortcuts import redirect
from django_iranian_payment.contrib.django import services

def start_payment(request, order):
    payment, redirect_url = services.start_payment(
        "zarinpal",
        amount=order.amount,                      # ریال
        callback_url="https://yoursite.com/payment/callback/zarinpal/",
        order_id=str(order.id),
        description="پرداخت سفارش",
        mobile="09120000000",                     # اختیاری
    )
    # نیازی به ذخیره‌ی authority نیست؛ پکیج خودش نگه می‌دارد.
    return redirect(redirect_url)
```

### بازگشت از بانک (callback)

اگر مسیرهای داخلی را در `urls.py` اضافه کرده باشی، **هیچ view ای لازم نیست**.
بانک به `/payment/callback/zarinpal/` برمی‌گردد، پکیج خودش تأیید می‌کند و کاربر را
به `callback_url` رکورد با پارامتر `payment_status` هدایت می‌کند:

```
https://yoursite.com/...?payment_status=success&order_id=123
```

اگر می‌خواهی منطق خودت را اجرا کنی، به‌جای استفاده از callback داخلی، خودت
`services.verify_payment(slug, authority)` را صدا بزن.

### تأیید مجدد تراکنش‌های ناتمام

گاهی کاربر از بانک برمی‌گردد ولی تأیید کامل نمی‌شود (قطع شبکه و ...). برای تأیید
مجدد این رکوردها، در یک job دوره‌ای (cron یا celery) اجرا کن:

```python
from django_iranian_payment.contrib.django import services

services.reverify_pending()       # تأیید مجدد همه‌ی رکوردهای بازگشته‌ی ناتمام
services.expire_stale(older_than_minutes=15)  # منقضی کردن رکوردهای خیلی قدیمی
```

### وضعیت‌های رکورد

`WAITING` → `REDIRECT_TO_BANK` → `RETURN_FROM_BANK` → `COMPLETE`
و حالت‌های پایانی: `CANCEL_BY_USER`، `EXPIRE_GATEWAY_TOKEN`، `EXPIRE_VERIFY`.

---

## روش ۲: لایه‌ی هسته (بدون مدل، پیشرفته)

اگر نمی‌خواهی مدل و migration داشته باشی (یا خارج از Django کار می‌کنی)، مستقیم از
هسته استفاده کن. در این حالت **خودت باید `authority` را ذخیره کنی**.

```python
from django_iranian_payment import get_gateway, PaymentRequest

def start_payment(request, order):
    gw = get_gateway("zarinpal")
    result = gw.initiate(PaymentRequest(
        amount=order.amount,                      # ریال
        callback_url="https://yoursite.com/verify/",
        order_id=str(order.id),
        description="پرداخت سفارش",
    ))
    order.authority = result.authority
    order.amount_sent = result.amount_to_send     # این را برای verify ذخیره کن
    order.save()
    return redirect(result.redirect_url)
```

```python
def verify_payment(request):
    authority = request.GET.get("Authority")
    order = Order.objects.get(authority=authority)
    gw = get_gateway("zarinpal")
    result = gw.verify(
        authority=authority,
        amount=order.amount_sent,   # همان مبلغی که در initiate رفت (با کارمزد)
        order_id=str(order.id),
    )
    if result.is_success:
        order.mark_paid(result.reference_id)
        return redirect("/success/")
    return redirect("/failure/")
```

> چرا `amount_sent` و نه `amount`؟ بعضی درگاه‌ها (زرین‌پال، پی‌پینگ) مبلغ را در
> callback برنمی‌گردانند و verify به همان مبلغ ارسالی نیاز دارد. اگر کارمزد روی
> مشتری اعمال شده باشد، مبلغ ارسالی با مبلغ پایه فرق دارد.

---

## کارمزد

کارمزد به‌صورت اختیاری روی هر پرداخت قابل تنظیم است. می‌توانی تعیین کنی کارمزد به
مبلغ اضافه شود (مشتری بپردازد) یا نشود (پذیرنده بپردازد، مبلغ بانک تغییر نکند).

```python
from django_iranian_payment import FeeConfig, FeePayer

fee = FeeConfig(
    rate_bps=200,                  # ۲٪ (۲۰۰ واحد پایه). ۱٪ = ۱۰۰
    fixed=0,                       # کارمزد ثابت به ریال (اختیاری)
    who_pays=FeePayer.CUSTOMER,    # CUSTOMER: به مبلغ اضافه می‌شود | MERCHANT: نمی‌شود
    max_fee=None,                  # سقف کارمزد به ریال (اختیاری)
)

# لایه‌ی ساده:
services.start_payment("zarinpal", amount=100_000, callback_url="...",
                       order_id="1", fee=fee)

# لایه‌ی هسته:
PaymentRequest(amount=100_000, callback_url="...", order_id="1", fee=fee)
```

نکات کارمزد:
- نرخ به **bps** (واحد پایه) است تا محاسبه‌ی پول با float انجام نشود (۲٪ = ۲۰۰).
- کارمزد همیشه **رو به بالا** گرد می‌شود تا پذیرنده کسری ضرر نکند.
- اگر `who_pays=CUSTOMER`، مبلغ ارسالی به بانک = مبلغ پایه + کارمزد. همین مبلغ در
  verify هم استفاده می‌شود (در لایه‌ی ساده خودکار است).
- اگر `who_pays=MERCHANT`، مبلغ بانک تغییر نمی‌کند و کارمزد فقط برای گزارش/حسابداری
  محاسبه می‌شود.

---

## افزودن درگاه جدید

درگاه‌های `core.experimental` پس از تست با اطلاعات و ترمینال واقعی، با افزودن یک
خط به `core/gateways/__init__.py` عمومی می‌شوند. تا آن لحظه با `get_gateway` در
دسترس نیستند و فقط با import صریح قابل دسترسی‌اند:

```python
from django_iranian_payment.core.experimental import MellatGateway
```

## لایسنس

MIT