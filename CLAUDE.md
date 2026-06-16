# CLAUDE.md — راهنمای پروژه برای دستیار هوش مصنوعی

این فایل را در ابتدای هر مکالمه‌ی جدید بفرست تا سریع با ساختار، تصمیم‌های معماری و
قراردادهای این پروژه آشنا شوی. لطفاً قبل از پیشنهاد هر تغییری، این قراردادها را رعایت کن.

---

## ۱. پروژه چیست

`django-iranian-payment` — یک پکیج پایتون که درگاه‌های پرداخت ایرانی را یکپارچه می‌کند.
روی PyPI منتشر می‌شود.

- نویسنده: Morteza Farhadi
- مخزن: https://github.com/mortexafarhadi/django-iranian-payment
- مدیریت محیط با **uv**.
- مدیریت ابزار با `uv add --dev` (pytest، pytest-django، black)؛ این ابزارها در
  `[dependency-groups]` می‌روند و در توزیع PyPI بسته‌بندی نمی‌شوند.
- فرمت کد با **black** (`uv run black .`). قبل از commit اجرا شود.
- `requires-python = ">=3.10"` (syntax مدرن مثل `int | None` مجاز است).

---

## ۲. فلسفه‌ی اصلی — مهم‌ترین بخش

این پکیج پول واقعی جابه‌جا می‌کند. قانون طلایی:

> **هیچ درگاهی عمومی نمی‌شود مگر با اطلاعات/ترمینال واقعی تست شده باشد.**

دو دسته درگاه داریم:

- **تست‌شده** (`core/gateways/`): REST/JSON با sandbox واقعی، تست خودکار. در registry
  عمومی ثبت شده و با `get_gateway("slug")` در دسترس‌اند.
- **تجربی** (`core/experimental/`): اسکلت با `TODO` و `NotImplementedError`. در registry
  عمومی نیستند. فقط با import صریح. تست‌نشده.

اگر خواسته شد درگاه تجربی «کامل» شود بدون مستندات واقعی آن بانک، باید هشدار بدهی و
فقط اسکلت با TODO بسازی — نه کد حدسی که تظاهر به درستی کند.

---

## ۳. معماری دو لایه (تصمیم بنیادی)

- **هسته (`core/`)**: بدون state، بدون وابستگی به Django. درگاه‌ها فقط `amount` ریالی
  می‌گیرند و می‌فرستند. در FastAPI/async/هر جای دیگر هم قابل استفاده است. این تمایز
  اصلی پروژه از az-iranian-bank-gateways است (که قفل به Django و ORM است).
- **لایه‌ی اختیاری (`contrib/django/`)**: مدل `Payment` + state machine + view و url
  داخلی callback + سرویس‌های تأیید مجدد. کاربری که جعبه‌سیاه می‌خواهد اپ را به
  `INSTALLED_APPS` اضافه می‌کند؛ کاربری که کنترل می‌خواهد فقط هسته را import می‌کند.

«کامل مثل az» عمداً انتخاب نشد: یک کلون ضعیف‌تر می‌شد. مدل toolkit + لایه‌ی اختیاری
هم سادگی جعبه‌سیاه را می‌دهد، هم تمایز سبکی و async را حفظ می‌کند.

---

## ۴. ساختار فایل‌ها

```
django_iranian_payment/
├── __init__.py                # رابط عمومی: get_gateway, PaymentRequest, FeeConfig, ...
├── core/                      # هسته‌ی بدون state
│   ├── __init__.py            # API عمومی هسته
│   ├── base.py                # BaseGateway + لایه‌ی transport قابل تزریق
│   ├── models.py              # PaymentRequest/Result/Status (dataclass، نه ORM)
│   ├── fee.py                 # apply_fee، FeeConfig، FeePayer (خالص و تست‌شده)
│   ├── exceptions.py          # GatewayError و زیرشاخه‌ها
│   ├── django_integration.py  # get_gateway(): config از settings.IRANIAN_PAYMENT
│   ├── gateways/              # درگاه‌های تست‌شده (registry عمومی)
│   │   └── __init__.py        # available_slugs, get_gateway_class, _REGISTRY
│   └── experimental/          # ۱۳ درگاه تجربی، خارج از registry
└── contrib/django/            # لایه‌ی اختیاری Django
    ├── models.py              # Payment + PaymentStatus + state machine
    ├── services.py            # start_payment, verify_payment, reverify_pending, expire_stale
    ├── views.py               # callback داخلی + go_to_gateway
    ├── urls.py                # مسیرهای داخلی
    ├── apps.py                # AppConfig (label="iranian_payment")
    └── migrations/

tests/                         # بیرون از پکیج، در توزیع نمی‌رود
├── test_fee.py                # تست تابع خالص کارمزد
├── test_gateways.py           # تست درگاه‌ها با InMemoryTransport
├── test_django_layer.py       # تست مدل/state machine/سرویس (نیازمند pytest-django)
└── test_views.py              # تست view ها با Django TestClient + monkeypatch
conftest.py                    # settings حداقلی برای تست‌های Django (ROOT_URLCONF=urls_test)
urls_test.py                   # urlconf تستی که مسیرهای پکیج را mount می‌کند
```

---

## ۵. قراردادهای معماری (رعایت اجباری)

1. **مبلغ همیشه به ریال است** در سراسر API. هر درگاهی که با تومان کار می‌کند (payping)،
   تبدیل را داخل خودش انجام می‌دهد.

2. **بدون state روی کلاس درگاه.** هر چیز موقت در متد می‌ماند یا برگردانده می‌شود.

3. **هر درگاه دقیقاً دو متد دارد:** `initiate(request) -> InitiateResult` و
   `verify(*, authority, amount, order_id) -> PaymentResult`.

4. **کارمزد در سطح PaymentRequest، نه داخل درگاه.** درگاه فقط `amount_to_send` را
   می‌بیند. این کار با `request.resolve_amount().amount_to_send` در ابتدای initiate
   انجام می‌شود. هر درگاه جدید هم باید همین را رعایت کند.

5. **`amount_to_send` مرجع یکتاست.** همان عددی که به initiate رفت، در verify هم
   استفاده می‌شود — نه مبلغ پایه. در لایه‌ی Django این در `payment.amount_sent` ذخیره
   و خودکار به verify پاس داده می‌شود. این تله‌ی verify-با-مبلغ-اشتباه را می‌بندد
   (زرین‌پال/پی‌پینگ verify را با مبلغ غلط رد می‌کنند).

6. **transport قابل تزریق است** (`core/base.py`). در تولید RequestsTransport، در تست
   InMemoryTransport. این یعنی منطق کامل initiate/verify بدون mock و بدون شبکه تست
   می‌شود. هر تست درگاه باید از InMemoryTransport استفاده کند.

7. **همه‌ی درخواست‌های HTTP timeout اجباری دارند.** خطای شبکه → GatewayConnectionError.
   برای درگاه‌های SOAP (ملت) هم همین timeout روی دانلود WSDL و فراخوانی متد اعمال
   می‌شود (zeep Transport با timeout/operation_timeout)، تا در نبود دسترسی به سرور
   به‌جای انتظار طولانی، سریع شکست بخورد.

8. **هیچ secret در کد hardcode نمی‌شود.** فقط از config.

9. **کارمزد:** نرخ به bps (۲٪ = ۲۰۰)، گرد رو به بالا (ceil)، بدون float. تابع
   `apply_fee` خالص است و در `core/fee.py` تست کامل دارد.

11. **verify می‌تواند پارامتر `extra` (دیکشنری، پیش‌فرض None) بگیرد.** درگاه‌های ساده
    (زرین‌پال/زیبال) آن را نادیده می‌گیرند. درگاه‌های شاپرکی مثل ملت که در verify به
    داده‌ی بیشتری از یک authority نیاز دارند (sale_reference_id و sale_order_id که در
    callbackِ POST برمی‌گردند)، آن‌ها را از `extra` می‌خوانند. لایه‌ی Django این مقادیر
    را در view از POST استخراج و به verify_payment پاس می‌دهد.

12. **درگاه‌های دومرحله‌ای (verify سپس settle) مثل ملت:** پیش‌فرض حالت تک‌مرحله‌ای
    `verify_settle` (bpVerifySettleRequest) است که تأیید و واریز را اتمیک انجام می‌دهد
    و پنجره‌ی شکست بین verify و settle را می‌بندد. حالت `verify_only` با config قابل
    انتخاب است ولی نیازمند فراخوانی جداگانه‌ی settle()؛ اگر settle نشود، بانک در ۳ ساعت
    Autoreversal می‌زند. متدهای کمکی ملت: settle()، reverse()، inquiry().

10. **معلق‌سازی درگاه (suspension).** اگر درگاهی که قبلاً عمومی بود در عمل خطا داد یا
    سرویسش بی‌ثبات شد، کدش پاک نمی‌شود؛ به `core/experimental/` منتقل و از `_REGISTRY`
    خارج می‌شود، با docstring که علت و راه بازگردانی را توضیح دهد. تفاوتش با درگاه
    تجربیِ اسکلت: درگاه معلق پیاده‌سازی کامل و سالم دارد. تست رگرسیون باید تأیید کند
    که `get_gateway_class("<slug>")` خطا می‌دهد ولی import صریح از experimental کار می‌کند.

---

## ۶. روند تست (مهم)

سبک پروژه: **ادعا با مدرک (اجرای کد)، نه از حافظه.** هر تغییر منطقی باید تست داشته
باشد و تست‌ها واقعاً اجرا و سبز شوند.

```bash
uv run pytest tests/ -v
```

- `test_fee.py` و `test_gateways.py`: بدون Django، فقط هسته.
- `test_django_layer.py`: تست مدل/state machine/سرویس. نیازمند `pytest-django`.
- `test_views.py`: تست view با Django TestClient (جریان کامل HTTP callback). برای
  شبیه‌سازی پاسخ بانک، `RequestsTransport.post` را monkeypatch می‌کند.
- `conftest.py` (ریشه): یک settings حداقلی با `settings.configure` می‌سازد و
  `ROOT_URLCONF="urls_test"` را تنظیم می‌کند.
- `urls_test.py` (ریشه): urlconf فقط برای تست که مسیرهای پکیج را mount می‌کند تا
  TestClient بتواند `/payment/callback/...` را resolve کند. در توزیع نمی‌رود.
- تست‌های درگاه از InMemoryTransport استفاده می‌کنند: پاسخ بانک را شبیه‌سازی می‌کنند،
  منطق ما واقعاً اجرا می‌شود. این اثبات می‌کند با پاسخ فرضی درست رفتار می‌کنیم — ولی
  اثبات نمی‌کند شکل پاسخ واقعی بانک همان است. آن نیاز به تست sandbox واقعی دارد.
- مجموعاً ۶۶ تست خودکار.

### اسکریپت‌های تست sandbox دستی (`scripts/`)
این‌ها تست خودکار pytest نیستند؛ ابزار دستی برای تست با ترمینال/کلید واقعی هر
درگاه‌اند و گام لازم پیش از عمومی‌کردن یک درگاه (بخش ۷). دومرحله‌ای‌اند: مرحله‌ی
۱ درگاه را می‌سازد و URL پرداخت می‌دهد؛ پس از پرداخت در مرورگر، مرحله‌ی ۲ با
توکن بازگشتی verify می‌زند.

```bash
uv run python scripts/test_zarinpal.py                         # merchant_id واقعی لازم
uv run python scripts/test_zarinpal.py verify <AUTHORITY> <AMOUNT>
uv run python scripts/test_idpay.py                            # api_key واقعی لازم
uv run python scripts/test_idpay.py verify <ID> <AMOUNT>
uv run python scripts/test_zibal.py                            # merchant="zibal" بدون ثبت‌نام
uv run python scripts/test_zibal.py verify <TRACK_ID> <AMOUNT>
uv run python scripts/test_pay_ir.py                           # ⚠️ معلق (پایین را ببین)
uv run python scripts/test_pay_ir.py verify <TOKEN> <AMOUNT>
```

- نام‌گذاری گمراه‌کننده: این فایل‌ها `test_*.py` نام دارند ولی در `scripts/`اند، نه
  `tests/`. pytest به‌صورت پیش‌فرض جمعشان نمی‌کند چون فقط `tests/` را اجرا می‌کنیم
  (`pytest tests/`). اگر روزی `pytest` بدون مسیر زدی، ممکن است این‌ها هم جمع شوند
  و چون main-guard دارند، چیزی اجرا نمی‌شود ولی import می‌شوند. آگاه باش.
- هر اسکریپت `AMOUNT` و مقادیر config را بالای فایل دارد؛ پیش از اجرا پر کن.
- نتیجه‌ی این اسکریپت‌ها همان «مدرک واقعی» است که InMemoryTransport نمی‌تواند بدهد:
  اثبات اینکه شکل پاسخ واقعی بانک با فرض ما یکی است.

---

## ۷. روند افزودن یک درگاه به registry عمومی (پس از تست واقعی)

1. `TODO`های `core/experimental/<bank>.py` را با مستندات رسمی پر و با sandbox/ترمینال
   واقعی تست کن. در initiate حتماً `request.resolve_amount().amount_to_send` استفاده شود.
2. فایل را به `core/gateways/<bank>.py` منتقل کن (importهای `..base` و `..models`
   تغییر نمی‌کنند چون عمق یکسان است).
3. هشدار «تجربی» را از docstring بردار.
4. در `core/gateways/__init__.py`: import و افزودن به `_REGISTRY`.
5. از `core/experimental/__init__.py` خط آن را حذف کن.
6. تست با InMemoryTransport بنویس (مثل test_gateways.py).
7. نسخه را بالا ببر (`0.2.0`) و منتشر کن.

---

## ۸. روند انتشار نسخه

1. شماره را در **دو جا** بالا ببر: `pyproject.toml` و `django_iranian_payment/__init__.py`.
2. نسخه‌بندی معنایی: رفع باگ → `0.1.x`، قابلیت جدید → `0.x.0`، پایدار → `1.0.0`.
3. build تمیز: `rm -rf dist/ && uv build`
4. آپلود (SOCKS برای دسترسی از ایران):
   ```bash
   uvx --with "requests[socks]" twine upload --repository testpypi dist/*
   uvx --with "requests[socks]" twine upload dist/*
   ```
5. هر شماره‌ی نسخه فقط یک‌بار قابل آپلود است — حتی روی TestPyPI.

---

## ۹. وضعیت فعلی و کارهای باز

- ✅ هسته‌ی بدون state، ۲ درگاه با تست واقعی موفق: zarinpal/zibal (REST، sandbox باز،
  از هر IP قابل تست).
- ⚠️ mellat (SOAP): کد کامل از مستند نگارش ۱.۳۸، منطق با soap_call تست‌شده (۱۶ تست
  هسته + ۳ تست Django)، ولی **هیچ‌وقت با ترمینال واقعی تست نشده**. در registry عمومی
  هست ولی تا تست واقعی، ادعای آماده‌بودن درباره‌اش نکن. تست واقعی ملت برخلاف
  zarinpal/zibal از لپ‌تاپ ممکن نیست؛ نیاز دارد به: (۱) ترمینال/قرارداد پذیرندگی
  واقعی، (۲) ثبت IP سرور نزد ملت طی نامه (وگرنه کد 421)، (۳) دسترسی شبکه به
  bpm.shaparak.ir از داخل ایران. عملاً باید روی سرور با IP ثبت‌شده اجرا شود.
  گزینه‌ی محافظه‌کارانه طبق قانون طلایی: تا تست واقعی، ملت به experimental برگردد.
- ⏸️ pay_ir معلق شد: کد سالم، ولی به‌دلیل خطای دسترسی و بی‌ثباتی شبکهٔ پرداخت پی
  از registry عمومی به core/experimental منتقل شد. با import صریح هنوز در دسترس.
- ⏸️ idpay معلق شد: کد سالم، ولی سرویس از کار افتاده (آخرین فعالیت پشتیبانی
  ~2025-11-20). به core/experimental منتقل شد. با import صریح هنوز در دسترس.
- ✅ کارمزد (fee.py) — ۱۶ تست.
- ✅ لایه‌ی Django: مدل، state machine، سرویس، view، url، migration — ۸ تست.
- ✅ تست view با Django TestClient (جریان کامل callback→redirect) — ۷ تست.
- ✅ مجموعاً ۶۶ تست خودکار سبز.
- ⚠️ هنوز **هیچ تراکنش واقعی sandbox تست نشده** — فقط منطق با InMemoryTransport و monkeypatch.
- ⬜ ۱۳ درگاه تجربی فقط اسکلت‌اند (منتظر مستندات واقعی هر بانک). pay_ir چهاردهمین
  ساکن experimental است ولی برخلاف بقیه، پیاده‌سازی کاملش را دارد (معلق، نه اسکلت).
- ⬜ celery/cron برای reverify_pending در مستندات هست ولی نمونه‌ی آماده ندارد.

### باگ‌های اصلاح‌شده که نباید برگردند (تست رگرسیون دارند)
- زرین‌پال: تناقض دامنه‌ی startpay (حالا payment.zarinpal.com).
- زرین‌پال: استخراج code از errors وقتی list است.
- آیدی‌پی: status رشته‌ای ("100") که verify موفق را FAILED می‌کرد.
- services: import نسبی `...core` (نه `..core`) از contrib/django.

### تصمیم‌های ثبت‌شده که نباید بی‌دلیل برگردند
- ملت در registry عمومی است با ۱۶ تست هسته (soap_call) + ۳ تست Django. تغییر
  امضای verify (افزودن extra=None) نباید زرین‌پال/زیبال را بشکند؛ کل سوییت سبز است.
- pay_ir در registry عمومی نیست (معلق). دو تست رگرسیون در test_gateways.py این را
  قفل کرده‌اند: `test_pay_ir_not_in_public_registry` و
  `test_pay_ir_still_importable_from_experimental`. اگر کسی pay_ir را دوباره به
  _REGISTRY افزود بدون تست واقعی موفق، این تست‌ها باید بشکنند تا جلوی برگشت ناآگاهانه را بگیرند.

### سبک پاسخ مورد انتظار نویسنده
فرض‌ها را به چالش بکش، سطح اطمینان را برچسب بزن ([Certain]/[Probable]/[Speculative])،
حقیقت ناخوشایند را اول بگو، و با مدرک واقعی (اجرای کد) ادعا کن نه از حافظه.
```