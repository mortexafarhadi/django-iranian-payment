# django-iranian-payment

درگاه‌های پرداخت ایرانی برای Django، با معماری دو لایه:

- **لایه‌ی ساده (توصیه‌شده):** یک اپ Django اختیاری که خودش رکورد پرداخت، ذخیره‌ی
  `authority`، تأیید، و مدیریت وضعیت تراکنش را انجام می‌دهد. کاربر تقریباً هیچ
  منطقی نمی‌نویسد.
- **لایه‌ی هسته (پیشرفته):** درگاه‌های بدون state که در هر محیطی (حتی غیر Django یا
  async) قابل استفاده‌اند. کاربر خودش `authority` را ذخیره و تأیید را مدیریت می‌کند.

همه‌ی مبالغ به **ریال** هستند.

## درگاه‌های آماده و تست‌شده (registry عمومی)

تنها این دو درگاه با تست واقعی sandbox (در `scripts/`) راستی‌آزمایی شده و با
`get_gateway("slug")` در دسترس‌اند:

| درگاه | نوع | وضعیت |
|-------|-----|--------|
| **زرین‌پال** | REST/JSON | sandbox تست‌شده (تراکنش live هنوز تست نشده) |
| **زیبال** | REST/JSON | sandbox تست‌شده (تراکنش live هنوز تست نشده) |

> ⚠️ هشدار صداقت: «sandbox تست‌شده» یعنی روند با ترمینال آزمایشی کار کرد، نه اینکه
> با ترمینال/قرارداد واقعی پول جابه‌جا شده باشد. تراکنش واقعی هیچ درگاهی هنوز تست نشده.

## درگاه‌های تجربی (در `core.experimental`)

این درگاه‌ها پیاده‌سازی کامل از مستند رسمی دارند و منطقشان با تست خودکار
(`InMemoryTransport`) پوشش داده شده، اما **هنوز هیچ تست sandbox یا ترمینال واقعی
روی آن‌ها انجام نشده** — برخلاف زرین‌پال/زیبال که حداقل sandbox دارند، این درگاه‌ها
به‌دلیل محدودیت‌های دسترسی (نیاز به قرارداد پذیرندگی، ثبت IP، کلید واقعی) حتی تست
script سندباکسشان هم انجام نشده است.

طبق قانون طلایی پروژه، تا تست واقعی موفق در registry عمومی قرار نمی‌گیرند و با
`get_gateway` در دسترس نیستند؛ فقط با import صریح:

```python
from django_iranian_payment.core.experimental.mellat import MellatGateway
from django_iranian_payment.core.experimental.saman import SamanGateway
from django_iranian_payment.core.experimental.irankish import IrankishGateway
from django_iranian_payment.core.experimental.nextpay import NextPayGateway
from django_iranian_payment.core.experimental.sadad import SadadGateway
from django_iranian_payment.core.experimental.digipay import DigipayGateway
```

| درگاه | نوع | رمزنگاری | وابستگی اختیاری |
|-------|-----|----------|------------------|
| **ملت** | SOAP | — | `[soap]` (zeep) |
| **سامان (SEP)** | REST/JSON | — | — |
| **ایران‌کیش** | REST/JSON | AES + RSA | `[irankish]` |
| **نکست‌پی** | REST/JSON | — | — |
| **سداد** | REST/JSON (WebApi) | 3DES | `[sadad]` |
| **دیجی‌پی** | REST/JSON (OAuth2) | — | — |

> ⚠️ **ملت** نیاز به `zeep` دارد: `pip install "django-iranian-payment[soap]"`.
> ملت دومرحله‌ای است؛ حالت پیش‌فرض `verify_settle` (تأیید+واریز اتمیک) توصیه می‌شود.
> برای واریز با تأخیر، `settle_mode="verify_only"` را در config بگذار و خودت
> `settle()` را صدا بزن (وگرنه بانک در ۳ ساعت Autoreversal می‌زند).

> **ایران‌کیش** و **سداد** به وابستگی رمزنگاری نیاز دارند:
> `pip install "django-iranian-payment[irankish]"` (شامل `pycryptodome` و `rsa`) یا
> `pip install "django-iranian-payment[sadad]"` (شامل `pycryptodome`).

> ⚠️ **سداد** همان درگاهی است که از سایت **بانک ملی** به آن هدایت می‌شوید؛
> بانک ملی درگاه مستقل خود را به سداد سپرده است.

> ⚠️ **دیجی‌پی** برخلاف بقیه احراز هویت دومرحله‌ای OAuth2 دارد: config آن پنج فیلد
> اجباری می‌خواهد (`username`, `password`, `client_id`, `client_secret`,
> `provider_id`). در verify به `trackingCode` (که در نتیجه‌ی پرداخت/callback
> برمی‌گردد) از طریق `extra` نیاز دارد. اگر پرداخت موفق را verify نکنی، پس از
> مدتی خودکار لغو و وجه مرجوع می‌شود.

### درگاه‌های از کار افتاده (دیگر سرویس نمی‌دهند)

> ❌ **پی‌آی‌آر (Pay.ir)** و **آیدی‌پی (IDPay)** کلاً از دسترس خارج شده‌اند و دیگر
> سرویس‌دهی نمی‌کنند. کدشان در `core.experimental` به‌عنوان آرشیو باقی مانده ولی
> برای استفاده توصیه نمی‌شود و `get_gateway("pay_ir")` / `get_gateway("idpay")`
> کار نمی‌کند. تنها در صورتی که این سرویس‌ها روزی بازگردند، با import صریح در
> دسترس‌اند:
> `from django_iranian_payment.core.experimental import PayIrGateway, IDPayGateway`

## نصب

```bash
pip install django-iranian-payment
# درگاه‌های SOAP (ملت و سایر درگاه‌های SOAP):
pip install "django-iranian-payment[soap]"
# درگاه ایران‌کیش (AES+RSA):
pip install "django-iranian-payment[irankish]"
# درگاه سداد (3DES):
pip install "django-iranian-payment[sadad]"
```

## تنظیمات

در `settings.py`:

```python
IRANIAN_PAYMENT = {
    "sandbox": True,  # روی پروداکشن False
    "gateways": {
        "zarinpal": {"merchant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"},
        "zibal": {"merchant": "zibal"},
    },
}
```

> توجه: درگاه‌های تجربی (ملت، سامان، ...) چون در registry نیستند با این config و
> `get_gateway` ساخته نمی‌شوند. برای استفاده از آن‌ها باید کلاسشان را مستقیم import
> و دستی config کنی (پس از تست واقعی).

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

### درگاه‌هایی که در verify به داده‌ی بیشتری نیاز دارند (پارامتر `extra`)

برخی درگاه‌های شاپرکی در verify به داده‌ای فراتر از یک `authority` نیاز دارند که
در callbackِ POST از بانک برمی‌گردد. این داده‌ها از طریق `extra` پاس داده می‌شوند.
این درگاه‌ها فعلاً تجربی‌اند و باید کلاسشان را مستقیم import کنی:

```python
# ملت (تجربی): به sale_reference_id و sale_order_id نیاز دارد
gw.verify(authority=ref_id, amount=amount, order_id=oid,
          extra={"sale_reference_id": "...", "sale_order_id": "..."})

# سامان (تجربی): به RefNum نیاز دارد
gw.verify(authority=token, amount=amount, order_id=oid,
          extra={"ref_num": "...", "state": "OK"})

# ایران‌کیش (تجربی): به token و reference_id نیاز دارد
gw.verify(authority=token, amount=amount, order_id=oid,
          extra={"token": "...", "reference_id": "...", "result_code": "100"})

# دیجی‌پی (تجربی): به trackingCode نیاز دارد (providerId همان order_id است)
gw.verify(authority=ticket, amount=amount, order_id=oid,
          extra={"tracking_code": "...", "result": "SUCCESS"})
```

درگاه‌های ساده (زرین‌پال، زیبال) پارامتر `extra` را نادیده می‌گیرند.

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

## افزودن درگاه جدید / عمومی‌کردن یک درگاه تجربی

درگاه‌های `core.experimental` پس از تست با اطلاعات و ترمینال واقعی، با انتقال فایل
به `core/gateways/` و افزودن یک خط به `core/gateways/__init__.py` عمومی می‌شوند. تا
آن لحظه با `get_gateway` در دسترس نیستند و فقط با import صریح قابل دسترسی‌اند:

```python
from django_iranian_payment.core.experimental.mellat import MellatGateway
```

---

## تاریخچه‌ی تغییرات درگاه‌ها

- **۱۴۰۵/۰۳/۲۷** — درگاه‌های مستقل **بانک تجارت** و **بانک ملی** حذف شدند. این
  بانک‌ها درگاه مستقل خود را کنار گذاشته‌اند و پرداخت را به PSPهای دیگر سپرده‌اند:
  - **بانک تجارت → ایران‌کیش**: از درگاه بانک تجارت به ایران‌کیش هدایت
    می‌شوید. به‌جای درگاه تجارت از `IrankishGateway` استفاده کنید.
  - **بانک ملی → سداد**: از سایت بانک ملی به درگاه سداد هدایت می‌شوید. به‌جای
    درگاه ملی از `SadadGateway` استفاده کنید.

  اسکلت‌های `tejarat.py` و `melli.py` (که هرگز پیاده‌سازی واقعی نداشتند و فقط
  `TODO` بودند) از پروژه حذف شدند تا فایل اضافی نماند. اگر روزی این بانک‌ها
  درگاه مستقل خود را دوباره راه‌اندازی کنند، در نسخه‌های بعدی دوباره افزوده
  خواهند شد.

## لایسنس

MIT