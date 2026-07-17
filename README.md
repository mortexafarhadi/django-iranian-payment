# django-iranian-payment

درگاه‌های پرداخت ایرانی برای Django، با معماری دو لایه:

- **لایه‌ی ساده (توصیه‌شده):** یک اپ Django اختیاری که خودش رکورد پرداخت، ذخیره‌ی
  `authority`، تأیید، و مدیریت وضعیت تراکنش را انجام می‌دهد. کاربر تقریباً هیچ
  منطقی نمی‌نویسد.
- **لایه‌ی هسته (پیشرفته):** درگاه‌های بدون state که در هر محیطی (حتی غیر Django یا
  async) قابل استفاده‌اند. کاربر خودش `authority` را ذخیره و تأیید را مدیریت می‌کند.

واحد بانک همیشه **ریال** است، اما می‌توانی واحد ورودی خودت را به **تومان** تغییر
دهی (`IRANIAN_PAYMENT["currency"] = "toman"`)؛ پکیج خودکار به ریال تبدیل می‌کند.
بخش [واحد پول](#واحد-پول-ریال-یا-تومان) را ببین.

## درگاه‌های آماده و تست‌شده (registry عمومی)

این درگاه‌ها راستی‌آزمایی شده و با `get_gateway("slug")` در دسترس‌اند:

| درگاه | نوع | وضعیت | وابستگی اختیاری |
|-------|-----|--------|------------------|
| **زرین‌پال** | REST/JSON | sandbox تست‌شده (تراکنش live هنوز تست نشده) | — |
| **زیبال** | REST/JSON | sandbox تست‌شده (تراکنش live هنوز تست نشده) | — |
| **ملت** | SOAP | ✅ **تراکنش live واقعی تست‌شده** | `[soap]` (zeep) |

> ⚠️ هشدار صداقت: «sandbox تست‌شده» یعنی روند با ترمینال آزمایشی کار کرد، نه اینکه
> با ترمینال/قرارداد واقعی پول جابه‌جا شده باشد. زرین‌پال/زیبال هنوز تراکنش live
> نشده‌اند. **ملت** اما با ترمینال/قرارداد واقعی روی محیط عملیاتی (bpm.shaparak.ir)
> تست شد: تراکنش موفق (ResCode=0، SaleReferenceId، CardHolderPan، FinalAmount) و
> سناریوی کنسل کاربر (ResCode=17) هر دو تأیید شدند.

> ⚠️ **ملت** نیاز به `zeep` دارد: `pip install "django-iranian-payment[soap]"`.
> ملت دومرحله‌ای است؛ حالت پیش‌فرض `verify_settle` (تأیید+واریز اتمیک) توصیه می‌شود.
> برای واریز با تأخیر، `settle_mode="verify_only"` را در config بگذار و خودت
> `settle()` را صدا بزن (وگرنه بانک در ۳ ساعت Autoreversal می‌زند). هدایت کاربر به
> ملت با **فرم POST** است (نه redirect ساده)؛ لایه‌ی Django این فرم auto-submit را
> در view `go_to_gateway` خودکار می‌سازد.

## درگاه‌های تجربی (در `core.experimental`)

این درگاه‌ها پیاده‌سازی کامل از مستند رسمی دارند و منطقشان با تست خودکار
(`InMemoryTransport`) پوشش داده شده، اما **هنوز هیچ تست sandbox یا ترمینال واقعی
روی آن‌ها انجام نشده** — برخلاف زرین‌پال/زیبال که حداقل sandbox دارند، این درگاه‌ها
به‌دلیل محدودیت‌های دسترسی (نیاز به قرارداد پذیرندگی، ثبت IP، کلید واقعی) حتی تست
script سندباکسشان هم انجام نشده است.

طبق قانون طلایی پروژه، تا تست واقعی موفق در registry عمومی قرار نمی‌گیرند و با
`get_gateway` در دسترس نیستند؛ فقط با import صریح:

```python
from django_iranian_payment.core.experimental.saman import SamanGateway
from django_iranian_payment.core.experimental.irankish import IrankishGateway
from django_iranian_payment.core.experimental.nextpay import NextPayGateway
from django_iranian_payment.core.experimental.sadad import SadadGateway
from django_iranian_payment.core.experimental.digipay import DigipayGateway
```

| درگاه | نوع | رمزنگاری | وابستگی اختیاری |
|-------|-----|----------|------------------|
| **سامان (SEP)** | REST/JSON | — | — |
| **ایران‌کیش** | REST/JSON | AES + RSA | `[irankish]` |
| **نکست‌پی** | REST/JSON | — | — |
| **سداد** | REST/JSON (WebApi) | 3DES | `[sadad]` |
| **دیجی‌پی** | REST/JSON (OAuth2) | — | — |

> ℹ️ **ملت** پیش‌تر تجربی بود؛ پس از تست تراکنش واقعی به registry عمومی منتقل شد
> (بالاتر را ببین). دیگر از `core.experimental` import نمی‌شود.

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
    "sandbox": False,    # پیش‌فرض سراسری
    "currency": "rial",  # واحد ورودی مبلغ: "rial" (پیش‌فرض) یا "toman"
    "gateways": {
        "zarinpal": {"merchant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                     "sandbox": True},   # sandbox مجزای همین درگاه
        "zibal": {"merchant": "zibal"},  # زیبال sandbox را با merchant کنترل می‌کند
        "mellat": {
            "terminal_id": "1234567",
            "username": "your-username",
            "password": "your-password",
            "settle_mode": "verify_settle",  # یا "verify_only"
            # بدون "sandbox" → از پیش‌فرض سراسری (False = live) پیروی می‌کند
        },
    },
}
```

### واحد پول (ریال یا تومان)

بانک‌های ایرانی همیشه با **ریال** کار می‌کنند؛ این واحد بانکِ پکیج است و
`amount_to_send` که به درگاه و verify می‌رود همیشه ریال است. اما می‌توانی واحدی که
**خودت ورودی می‌دهی** را با `IRANIAN_PAYMENT["currency"]` به‌صورت سراسری انتخاب کنی:

```python
IRANIAN_PAYMENT = {
    "currency": "toman",   # حالا amount ها را به تومان می‌دهی
    "gateways": {...},
}

# با تنظیم بالا (هر دو مسیر یکسان عمل می‌کنند):
services.start_payment("zarinpal", amount=15_000, ...)   # ۱۵۰۰۰ تومان → بانک ۱۵۰۰۰۰ ریال
# مسیر toolkit هم واحد سراسری را رعایت می‌کند (get_gateway آن را تزریق می‌کند):
get_gateway("zarinpal").initiate(PaymentRequest(amount=15_000, ...))  # هم ۱۵۰۰۰۰ ریال
```

- پیش‌فرض `"rial"` است (سازگار با قبل؛ هیچ تبدیلی انجام نمی‌شود).
- واحد سراسری در **هر دو مسیر** اعمال می‌شود: هم `start_payment`، هم
  `get_gateway(...).initiate(PaymentRequest(...))`. در مسیر toolkit، `get_gateway`
  واحد سراسری را در درخواستی که `currency` مشخص نکرده تزریق می‌کند. اگر `currency` را
  روی خود `PaymentRequest` بدهی، بر تنظیم سراسری اولویت دارد.
- تبدیل **۱ تومان = ۱۰ ریال** فقط یک‌بار و در همان ابتدای کار انجام می‌شود.
- مبالغ ذخیره‌شده در مدل `Payment` و مقادیر بازگشتی verify **همیشه ریال‌اند** (واحد
  بانک)؛ `currency` فقط واحد *ورودی* را تعیین می‌کند. برای نمایش به کاربر در تومان،
  خودت بر ۱۰ تقسیم کن.
- کارمزد: `rate_bps` واحد‌مستقل است؛ ولی `fixed` و `max_fee` در همان واحد ورودی
  تفسیر و خودکار به ریال تبدیل می‌شوند.
- در لایه‌ی هسته‌ی خالص (بدون Django و بدون `get_gateway`) واحد را روی خود درخواست
  بده: `PaymentRequest(amount=15_000, currency="toman", ...)`. برای خواندن مقدار
  سراسری از settings هم `from django_iranian_payment import get_default_currency` هست.

### sandbox مجزای هر درگاه

`sandbox` هر درگاه جداگانه تعیین می‌شود. کلید `"sandbox"` داخل config همان درگاه بر
مقدار سراسری اولویت دارد، پس می‌توانی یک درگاه را sandbox و درگاه دیگری را live
داشته باشی هم‌زمان. اولویت کامل:

```
get_gateway(..., sandbox=...)  >  config درگاه  >  "sandbox" سراسری  >  False
```

> فقط درگاه‌هایی که URL سندباکس جدا دارند (زرین‌پال، ملت، دیجی‌پی) به این فلگ واکنش
> می‌دهند. زیبال با مقدار `merchant="zibal"` و سامان/ایران‌کیش/نکست‌پی/سداد اصلاً URL
> سندباکس جدا ندارند (فلگ `sandbox` برایشان بی‌اثر است).

### راهنمای کامل هر درگاه

برای هر درگاه یک راهنمای گام‌به‌گام و خودکفا (هر دو حالت مدیریت دیتابیس) در
[`docs/gateways/`](docs/gateways/README.md) هست:
[زرین‌پال](docs/gateways/zarinpal.md) ·
[زیبال](docs/gateways/zibal.md) ·
[ملت](docs/gateways/mellat.md) ·
[سامان](docs/gateways/saman.md) ·
[ایران‌کیش](docs/gateways/irankish.md) ·
[نکست‌پی](docs/gateways/nextpay.md) ·
[سداد](docs/gateways/sadad.md) ·
[دیجی‌پی](docs/gateways/digipay.md).

> توجه: درگاه‌های تجربی (سامان، ایران‌کیش، ...) در registry عمومی نیستند. برای
> استفاده‌شان با `get_gateway` و لایه‌ی Django باید یک‌بار صریحاً register شوند
> (روش بالا را ببین). درگاه‌های registry عمومی (زرین‌پال، زیبال، ملت) به این ثبت
> نیاز ندارند و مستقیم با `get_gateway("slug")` در دسترس‌اند.

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
اگر از لایه‌ی Django استفاده کنی، view‌های پکیج این مقادیر را خودکار از callback
استخراج و پاس می‌دهند.

```python
# ملت (registry عمومی): به sale_reference_id و sale_order_id نیاز دارد.
# اگر کاربر کنسل کرده باشد، res_code از callback (=17) را هم بده تا بدون
# تماس SOAP وضعیت CANCELLED برگردد.
gw.verify(authority=ref_id, amount=amount, order_id=oid,
          extra={"sale_reference_id": "...", "sale_order_id": "...",
                 "card_number": "...", "res_code": "0"})

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
from django_iranian_payment.core.experimental.saman import SamanGateway
```

نمونه‌ی واقعی این ارتقا: **ملت** که پس از تست تراکنش live از `core.experimental` به
`core.gateways` منتقل شد و حالا با `get_gateway("mellat")` در دسترس است.

---

## تاریخچه‌ی تغییرات درگاه‌ها

- **نسخه‌ی `0.7.0`** — **انتخاب واحد پول (ریال/تومان).** کلید سراسری
  `IRANIAN_PAYMENT["currency"]` (`"rial"` پیش‌فرض یا `"toman"`) اضافه شد. کاربر
  می‌تواند مبلغ‌ها را به تومان بدهد و پکیج خودکار به ریال (واحد بانک) تبدیل می‌کند
  (۱ تومان = ۱۰ ریال). تبدیل در `PaymentRequest.resolve_amount()` انجام می‌شود، پس
  هیچ درگاهی نیاز به تغییر نداشت. در لایه‌ی هسته `PaymentRequest(currency=...)` و
  در settings کلید `currency`. سازگار با قبل (پیش‌فرض ریال = بدون تبدیل). مبالغ
  ذخیره/بازگشتی همیشه ریال‌اند. تست: `tests/test_currency.py`.

- **نسخه‌ی `0.6.0`** — دو تغییر:
  - **sandbox مجزای هر درگاه:** کلید `"sandbox"` داخل config هر درگاه بر مقدار
    سراسری اولویت دارد؛ `get_gateway(..., sandbox=...)` هم اضافه شد. حالا می‌توان یک
    درگاه را live و دیگری را sandbox داشت هم‌زمان (سازگار با قبل: فقط `sandbox`
    سراسری مثل قبل کار می‌کند).
  - **رفع باگ callback لایه‌ی Django برای درگاه‌های شاپرکی:** پیش‌تر view callback
    پکیج رکورد را فقط با چند نام پارامتر محدود پیدا می‌کرد و برای نکست‌پی
    (`trans_id`)، سداد (`Token`)، سامان (`ResNum` — توکن در callback نیست) و دیجی‌پی
    (`providerId` — ticket در callback نیست) رکورد را نمی‌یافت و ۴۰۴ می‌داد. اکنون یک
    جدول مشخصات (`_CALLBACK_SPEC`) در `contrib/django/views.py` برای هر درگاه نام
    پارامتر درست و کلید پیدا کردن رکورد (authority یا order_id) را تعریف می‌کند.
    ملت همچنان با `RefId` (authority یکتا) پیدا می‌شود تا رفتار live تست‌شده‌اش
    دست‌نخورده بماند.
  - راهنمای کامل هر درگاه برای هر دو حالت مدیریت دیتابیس در `docs/gateways/` افزوده شد.

- **۱۴۰۵/۰۴/۰۳** (نسخه‌ی `0.5.0`) — درگاه **ملت** پس از تست تراکنش واقعی روی محیط
  عملیاتی (bpm.shaparak.ir) از `core.experimental` به registry عمومی منتقل شد و
  حالا با `get_gateway("mellat")` در دسترس است. در جریان تست live دو باگ کشف و رفع
  شد (هر دو تست رگرسیون دارند):
  - کنسل کاربر (`ResCode=17` بدون `SaleReferenceId`) باعث crash می‌شد؛ حالا verify
    ابتدا `res_code` از callback را بررسی و بدون تماس SOAP، `CANCELLED`/`FAILED`
    برمی‌گرداند.
  - `CardHolderPan` از callback ذخیره نمی‌شد. اکنون شماره‌ی کارت ماسک‌شده در
    `card_number` و مقادیر `sale_order_id`/`sale_reference_id`/`final_amount` در
    `raw` (مدل Payment) ذخیره می‌شوند تا برای `settle`/`reverse` بعدی در دسترس باشند.

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