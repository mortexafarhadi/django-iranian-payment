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
- وابستگی‌های اختیاری درگاه‌ها در `[project.optional-dependencies]`: `soap` (zeep
  برای ملت)، `irankish` (pycryptodome + rsa)، `sadad` (pycryptodome). این‌ها فقط
  وقتی نصب می‌شوند که کاربر آن درگاه خاص را بخواهد. zeep/pycryptodome/rsa در
  `[dependency-groups].dev` هم تکرار شده‌اند تا تست‌های ملت/ایران‌کیش/سداد اجرا شوند
  (وگرنه با importorskip بی‌صدا skip می‌شوند).
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
│   └── experimental/          # درگاه‌های تجربی + کاملِ تست‌نشده، خارج از registry
└── contrib/django/            # لایه‌ی اختیاری Django
    ├── models.py              # Payment + PaymentStatus + state machine
    ├── services.py            # start_payment, verify_payment, reverify_pending, expire_stale
    ├── views.py               # callback داخلی + go_to_gateway
    ├── urls.py                # مسیرهای داخلی
    ├── apps.py                # AppConfig (label="iranian_payment")
    └── migrations/

tests/                         # بیرون از پکیج، در توزیع نمی‌رود
├── test_fee.py                # تست تابع خالص کارمزد
├── test_currency.py           # تست واحد پول (ریال/تومان) و تبدیل به ریال
├── test_gateways.py           # تست درگاه‌ها با InMemoryTransport
├── test_django_layer.py       # تست مدل/state machine/سرویس (نیازمند pytest-django)
├── test_django_integration.py # تست get_gateway و sandbox مجزای هر درگاه
└── test_views.py              # تست view ها + _locate_payment/_extract_extra (callback spec)
conftest.py                    # settings حداقلی برای تست‌های Django (ROOT_URLCONF=urls_test)
urls_test.py                   # urlconf تستی که مسیرهای پکیج را mount می‌کند

docs/gateways/                 # راهنمای .md هر درگاه (هر دو حالت مدیریت دیتابیس)، خارج از توزیع
├── README.md                  # فهرست و توضیح دو حالت + sandbox مجزا
└── <slug>.md                  # راهنمای خودکفای هر درگاه (zarinpal.md، mellat.md، ...)
scripts/                       # خارج از توزیع
├── test_<slug>.py             # تست دستی sandbox/ترمینال واقعی (بخش ۶)
├── django_<slug>.py           # کد نمونه‌ی هر دو حالت Django برای هر درگاه (اجراشدنی/کپی)
└── django_custom_db.py        # الگوی عمومی حالت «مدیریت دستی DB» + CALLBACK_SPEC
```

---

## ۵. قراردادهای معماری (رعایت اجباری)

1. **واحد بانک همیشه ریال است.** `amount_to_send` (مرجع یکتا که به درگاه و verify
   می‌رود) همیشه ریال است و هر درگاهی که با تومان کار می‌کند (payping) تبدیل را داخل
   خودش انجام می‌دهد. **ولی واحد ورودی کاربر قابل انتخاب است** (از نسخه‌ی `0.7.0`):
   `PaymentRequest.currency` (پیش‌فرض `None` = «مشخص‌نشده») و کلید سراسری
   `IRANIAN_PAYMENT["currency"]`. تبدیل تومان→ریال (×۱۰) فقط در
   `PaymentRequest.resolve_amount()` و یک‌بار انجام می‌شود، پس درگاه‌ها دست‌نخورده
   ماندند (همه از `resolve_amount().amount_to_send` ریالی استفاده می‌کنند). مبالغ
   ذخیره‌شده در مدل `Payment` و مقادیر بازگشتی همیشه ریال‌اند؛ `currency` فقط واحد
   ورودی را تعیین می‌کند. **واحد سراسری در هر دو مسیر اعمال می‌شود:** `start_payment`
   واحد را از `get_default_currency()` می‌گیرد و صریح پاس می‌دهد؛ و **`get_gateway`
   واحد سراسری را در `initiate` به هر درخواستی که `currency=None` است تزریق می‌کند**
   (پیش‌فرض `None` دقیقاً برای همین است — تمایز «کاربر ریال خواست» از «چیزی نگذاشت»).
   این باگ واقعی را بست: کاربری که مسیر toolkit
   (`get_gateway(...).initiate(PaymentRequest(amount=...))` طبق `scripts/django_*.py`)
   را می‌رفت و `currency` نمی‌داد، تومان با ریال فرقی نداشت. حالا هر دو مسیر یکسان‌اند؛
   `currency` صریح روی `PaymentRequest` بر تزریق سراسری اولویت دارد. هسته‌ی خالص (بدون
   `get_gateway`) همچنان `None`→ریال می‌گیرد پس رفتار FastAPI/async دست‌نخورده است.
   fee: `rate_bps` واحد‌مستقل، ولی `fixed`/`max_fee` در همان واحد ورودی و خودکار ریالی
   می‌شوند. تست: `tests/test_currency.py` و `tests/test_django_integration.py`
   (`test_get_gateway_injects_global_toman_into_toolkit_request`).

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

8.1. **sandbox مجزای هر درگاه.** `get_gateway` (در `core/django_integration.py`)
    sandbox را با این اولویت می‌خواند: آرگومان صریح `get_gateway(..., sandbox=...)` ←
    کلید `"sandbox"` داخل config همان درگاه ← `"sandbox"` سراسری `IRANIAN_PAYMENT` ←
    `False`. کلید کنترلی `sandbox` پیش از پاس‌دادن به سازنده از config جدا می‌شود
    (بدون mutate کردن دیکشنری settings کاربر). سازگار با قبل: فقط `sandbox` سراسری
    مثل قبل کار می‌کند. تست رگرسیون: `tests/test_django_integration.py`. توجه: فقط
    درگاه‌هایی که `self.sandbox` را برای سوییچ URL استفاده می‌کنند
    (زرین‌پال/ملت/دیجی‌پی) واکنش می‌دهند؛ زیبال با `merchant="zibal"` و
    سامان/ایران‌کیش/نکست‌پی/سداد URL سندباکس جدا ندارند (فلگ برایشان بی‌اثر است).

9. **کارمزد:** نرخ به bps (۲٪ = ۲۰۰)، گرد رو به بالا (ceil)، بدون float. تابع
   `apply_fee` خالص است و در `core/fee.py` تست کامل دارد.

11. **verify می‌تواند پارامتر `extra` (دیکشنری، پیش‌فرض None) بگیرد.** درگاه‌های ساده
    (زرین‌پال/زیبال) آن را نادیده می‌گیرند. درگاه‌های شاپرکی مثل ملت که در verify به
    داده‌ی بیشتری از یک authority نیاز دارند (sale_reference_id و sale_order_id که در
    callbackِ POST برمی‌گردند)، آن‌ها را از `extra` می‌خوانند. لایه‌ی Django این مقادیر
    را در view از POST استخراج و به verify_payment پاس می‌دهد.

11.1. **`_CALLBACK_SPEC` — منبع واحد پیدا کردن رکورد و ساخت extra در callback.**
    در `contrib/django/views.py` یک جدول per-gateway هست که برای هر slug تعریف می‌کند:
    (الف) رکورد را با کدام فیلد (`authority` یا `order_id`) و کدام نام پارامتر callback
    پیدا کن، (ب) چه کلیدهایی برای `extra` از callback استخراج شوند. علت وجودش یک باگ
    واقعی بود: `_extract_authority` قدیمی فقط چند نام محدود می‌شناخت و برای نکست‌پی
    (`trans_id`)، سداد (`Token`)، سامان (`ResNum` — توکن در callback نیست) و دیجی‌پی
    (`providerId` — ticket در callback نیست) رکورد را نمی‌یافت و ۴۰۴ می‌داد. نکته‌ی
    مهم: سامان/دیجی‌پی توکن/ticket را در callback برنمی‌گردانند، پس با `order_id`
    (که خودمان فرستادیم و بانک echo می‌کند) پیدا می‌شوند؛ بقیه با `authority` یکتا.
    **ملت عمداً با `RefId` (authority یکتا) پیدا می‌شود** نه `SaleOrderId`، تا رفتار
    live تست‌شده‌اش دست‌نخورده بماند (RefId یکتاتر از order_id است که در retry تکرار
    می‌شود). درگاه ناشناخته (خارج از spec) به کلیدهای عمومی authority برمی‌گردد.
    تست رگرسیون: `tests/test_views.py` (`test_locate_*`). همین spec به‌صورت مستقل در
    `scripts/django_custom_db.py` (`CALLBACK_SPEC`) برای حالت مدیریت دستی هم هست.

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
- تعداد تست‌ها متغیر است؛ پس از هر تغییر با `uv run pytest tests/ -v` شمارش واقعی
  را بگیر. (مرجع تاریخی: پیش از انتقال ملت ۱۲۰ تست بود؛ با حذف ۴ تست ملت و افزودن
  تست‌های دیجی‌پی این عدد تغییر می‌کند — به عدد ثابت در مستند اعتماد نکن، اجرا کن.)

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
uv run python scripts/test_pay_ir.py                           # ❌ از کار افتاده (پایین را ببین)
uv run python scripts/test_pay_ir.py verify <TOKEN> <AMOUNT>
uv run python scripts/test_saman.py                            # terminal_id واقعی + IP ثبت‌شده
uv run python scripts/test_saman.py verify <REFNUM> <AMOUNT>
uv run python scripts/test_irankish.py                         # terminal/acceptor/pass + کلید .pem
uv run python scripts/test_irankish.py verify <TOKEN> <REFID> <AMOUNT>
uv run python scripts/test_nextpay.py                          # api_key واقعی + دامنه ثبت‌شده
uv run python scripts/test_nextpay.py verify <TRANS_ID> <AMOUNT>
uv run python scripts/test_sadad.py                            # merchant/terminal/key(Base64)
uv run python scripts/test_sadad.py verify <TOKEN> <AMOUNT>
uv run python scripts/test_digipay.py                          # username/password/client_id/client_secret/provider_id
uv run python scripts/test_digipay.py verify <TRACKING_CODE> <AMOUNT>
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

1. شماره را فقط در `django_iranian_payment/__init__.py` (متغیر `__version__`) بالا ببر.
   `pyproject.toml` نسخه را به‌صورت dynamic از همین attr می‌خواند
   (`version = { attr = "django_iranian_payment.__version__" }`)، پس یک منبع است.
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

- ✅ نسخه‌ی `1.0.0`: **سامان (SEP) پس از تست تراکنش واقعی با ترمینال واقعی به
  registry عمومی منتقل شد** (طبق قانون طلایی). از `core/experimental/saman.py` به
  `core/gateways/saman.py` منتقل و به `_REGISTRY` افزوده شد؛ حالا با
  `get_gateway("saman")` در دسترس است. دو تست رگرسیون قفلش می‌کنند:
  `test_saman_in_public_registry` و `test_saman_no_longer_in_experimental`. سامان
  URL سندباکس جدا ندارد (فلگ sandbox بی‌اثر). دو حالت `mode`: `classic` (پیش‌فرض) و
  `neo_pg` (بلوپی).

- ✅ نسخه‌ی `0.7.0`: **انتخاب واحد پول (ریال/تومان)** با کلید سراسری
  `IRANIAN_PAYMENT["currency"]` و `PaymentRequest.currency` (بند ۱). تبدیل در
  `resolve_amount()` انجام می‌شود؛ هیچ درگاهی تغییر نکرد. مبالغ ذخیره/بازگشتی ریال
  می‌مانند. تست: `tests/test_currency.py`. توابع/کلاس‌های عمومی جدید: `Currency`،
  `to_rial`، `get_default_currency`.

- ✅ نسخه‌ی `0.6.0`: دو تغییر مهم.
  - **sandbox مجزای هر درگاه** (بند ۸.۱). هر درگاه می‌تواند مستقل sandbox/live باشد.
  - **رفع باگ callback لایه‌ی Django** برای درگاه‌های شاپرکی با `_CALLBACK_SPEC`
    (بند ۱۱.۱): پیش‌تر callback نکست‌پی/سداد/سامان/دیجی‌پی در حالت پکیج رکورد را
    نمی‌یافت و ۴۰۴ می‌داد؛ حالا کار می‌کند (پس از register شدن درگاه تجربی).
  - راهنمای کامل هر درگاه برای هر دو حالت مدیریت دیتابیس در `docs/gateways/` اضافه شد.

- ✅ هسته‌ی بدون state، ۴ درگاه در registry عمومی:
  - zarinpal/zibal (REST، sandbox باز، از هر IP قابل تست). توجه: فقط sandbox تست
    شده — **تراکنش live این دو هنوز تست نشده**.
  - **saman** (SEP، REST/JSON): با **تراکنش واقعی روی ترمینال واقعی** تست شد و طبق
    قانون طلایی به registry عمومی منتقل شد (نسخه‌ی `1.0.0`). توکن → redirect (فرم
    POST با فیلد `Token`) → callback POST → VerifyTransaction. verify به `RefNum`
    از extra نیاز دارد؛ رکورد در callback با `order_id` (==`ResNum`) پیدا می‌شود
    چون توکن در callback برنمی‌گردد. ResultCode=2 → DUPLICATE. تطبیق مبلغ
    (OrginalAmount) داخل verify. دو حالت `mode`: `classic` (پیش‌فرض) / `neo_pg`.
  - **mellat** (SOAP): با **تراکنش واقعی روی محیط عملیاتی (bpm.shaparak.ir)**
    تست شد و طبق قانون طلایی به registry عمومی منتقل شد (۱۴۰۵/۰۴/۰۳). داده‌ی واقعی
    تأییدشده: تراکنش موفق (ResCode=0، SaleReferenceId، CardHolderPan، FinalAmount)
    و سناریوی کنسل کاربر (ResCode=17 بدون SaleReferenceId). برای فراخوانی به zeep
    نیاز است: `pip install "django-iranian-payment[soap]"`. نکات تستِ واقعی: محیط
    sandbox ملت (pgw.dev.bpmellat.ir) در عمل پاسخ نداد؛ تست روی live با ترمینال/
    قرارداد واقعی، IP ثبت‌شده نزد ملت و دسترسی شبکه به bpm.shaparak.ir انجام شد.
    دو باگ که در تست live کشف و رفع شد (تست رگرسیون دارند): (۱) کنسل کاربر بدون
    SaleReferenceId باعث crash می‌شد — حالا verify ابتدا res_code از callback را
    چک می‌کند و بدون تماس SOAP، CANCELLED/FAILED برمی‌گرداند؛ (۲) CardHolderPan از
    callback ذخیره نمی‌شد. sale_order_id/sale_reference_id/final_amount در
    PaymentResult.raw ذخیره می‌شوند تا settle/reverse بعدی در دسترس باشند.
- ❌ pay_ir از کار افتاده: سرویس کلاً از دسترس خارج شده و دیگر سرویس نمی‌دهد.
  کد در core/experimental به‌عنوان آرشیو مانده ولی توصیه نمی‌شود. با import صریح
  هنوز در دسترس (برای صورت بازگشت احتمالی سرویس).
- ❌ idpay از کار افتاده: سرویس کلاً از دسترس خارج شده و دیگر سرویس نمی‌دهد
  (آخرین فعالیت پشتیبانی ~2025-11-20). کد در core/experimental به‌عنوان آرشیو
  مانده ولی توصیه نمی‌شود. با import صریح هنوز در دسترس.
- ⚠️ چهار درگاه تجربیِ دیگر (پیاده‌سازی کامل از مستند رسمی + تست InMemoryTransport،
  ولی هنوز در experimental چون **حتی تست script سندباکس هم نشده** — به‌دلیل
  محدودیت دسترسی، قرارداد پذیرندگی، ثبت IP و کلید واقعی):
  - **irankish** (ایران‌کیش): REST/JSON با authenticationEnvelope (AES+RSA+SHA256).
    verify به token و reference_id از extra نیاز دارد. وابستگی اختیاری: [irankish]
    (pycryptodome + rsa). ⚠️ برخلاف کد مرجع، SSL هرگز خاموش نمی‌شود.
  - **nextpay** (نکست‌پی): REST/JSON. ⚠️ کد موفقیت ساخت توکن code=-1 است (نه 0).
    مبلغ پیش‌فرض تومان است ولی currency=IRR می‌فرستیم تا amount ریالی بدون تبدیل
    برود. code=-25/-49 → DUPLICATE. refund() دارد.
  - **sadad** (سداد): REST/JSON (WebApi) با SignData رمزنگاری‌شده 3DES(ECB,PKCS7).
    کلید پذیرنده Base64 (پس از دیکد ۱۶/۲۴ بایت). verify ResCode=100 → DUPLICATE.
    وابستگی اختیاری: [sadad] (pycryptodome).
  - **digipay** (دیجی‌پی): REST/JSON با احراز هویت دومرحله‌ای OAuth2. config پنج
    فیلد اجباری: username/password/client_id/client_secret/provider_id. هر
    initiate/verify اول oauth/token (Basic base64(client_id:client_secret) +
    form username/password) می‌زند، سپس با Bearer سرویس را صدا می‌کند (بدون state،
    توکن تازه هر بار). کلید موفقیت result.status==0 است (نه HTTP code). initiate:
    tickets/business?type=11 → ticket + redirectUrl. verify: purchases/verify با
    trackingCode (از callback، در extra) + providerId (همان order_id). providerId
    در verify دوباره لازم است و باید با تراکنش ثبت‌شده تطبیق داده شود (هشدار مستند).
- ✅ کارمزد (fee.py) — ۱۶ تست.
- ✅ لایه‌ی Django: مدل، state machine، سرویس، view، url، migration — ۸ تست.
- ✅ تست view با Django TestClient (جریان کامل callback→redirect) — ۷ تست.
- ✅ سوییت تست خودکار سبز (تعداد دقیق را با pytest بگیر، نه از این مستند — بخش ۶).
- ⚠️ هنوز **هیچ تراکنش واقعی برای درگاه‌های تجربی تست نشده** — فقط منطق با
  InMemoryTransport و monkeypatch. zarinpal/zibal تست script سندباکس دارند و
  mellat/saman تست تراکنش واقعی دارند (هر چهار در registry عمومی). سداد/ایران‌کیش/
  نکست‌پی/دیجی‌پی به‌دلیل محدودیت‌های دسترسی حتی تست script سندباکسشان هم انجام نشده
  و کدشان صرفاً از روی مستندات رسمی نوشته شده است.
- ⬜ درگاه‌های تجربیِ باقی‌مانده اسکلت‌اند (منتظر مستندات واقعی هر بانک).
- ⬜ celery/cron برای reverify_pending در مستندات هست ولی نمونه‌ی آماده ندارد.

### درگاه‌های حذف‌شده (۱۴۰۵/۰۳/۲۷)
بانک تجارت و بانک ملی درگاه مستقل خود را حذف و به PSP دیگر سپرده‌اند:
- **تجارت → ایران‌کیش**: اسکلت tejarat.py حذف شد. به‌جایش IrankishGateway.
- **ملی → سداد**: اسکلت melli.py حذف شد. به‌جایش SadadGateway.
این دو فقط اسکلت TODO بودند (هرگز پیاده‌سازی واقعی نداشتند)، پس حذفشان با بند ۱۰
(معلق‌سازی کدِ سالم) تضاد ندارد — آن بند کد ارزشمند را حفظ می‌کند نه placeholder را.
اگر روزی این بانک‌ها درگاه مستقل راه‌اندازی کنند، در نسخه‌های بعدی افزوده می‌شوند.

### باگ‌های اصلاح‌شده که نباید برگردند (تست رگرسیون دارند)
- زرین‌پال: تناقض دامنه‌ی startpay (حالا payment.zarinpal.com).
- زرین‌پال: استخراج code از errors وقتی list است.
- آیدی‌پی: status رشته‌ای ("100") که verify موفق را FAILED می‌کرد.
- services: import نسبی `...core` (نه `..core`) از contrib/django.
- **پول‌گم‌شده هنگام در دسترس نبودن درگاه در verify (هر دو حالت DB).** پیش‌تر اگر
  `gw.verify()` با `GatewayConnectionError` (بی‌پاسخ/۵۰۰) شکست می‌خورد، هیچ `mark`
  اجرا نمی‌شد و رکورد در `REDIRECT_TO_BANK` می‌ماند؛ `reverify_pending` فقط
  `RETURN_FROM_BANK` را می‌گیرد پس هرگز تمامش نمی‌کرد و `expire_stale` اشتباه
  منقضی‌اش می‌کرد — پرداختِ پول‌داده گم می‌شد. رفع: `verify_payment` اکنون **پیش از**
  تماس شبکه‌ای رکورد را `RETURN_FROM_BANK` «پیش‌علامت» می‌زند و `extra` را در
  `raw["callback_extra"]` ذخیره می‌کند؛ تماس شبکه‌ای بیرون از قفل DB است؛ خطای
  شبکه بالا می‌رود ولی رکورد returned مانده تا reverify بگیردش. `reverify_pending`
  حالا `extra` را از raw بازمی‌خواند (verify شاپرکی مثل ملت در reverify هم کار
  می‌کند) و خطای اتصال را می‌بلعد. view callback خطای اتصال را می‌گیرد و
  `payment_status=pending` برمی‌گرداند (نه ۵۰۰). تست رگرسیون:
  `test_verify_connection_error_marks_returned_not_lost`،
  `test_expire_stale_ignores_returned_after_connection_error`،
  `test_reverify_pending_passes_extra_from_raw` (test_django_layer.py) و
  `test_callback_gateway_down_redirects_pending_not_500` (test_views.py). حالت
  مدیریت دستی DB همین الگو را در `scripts/django_custom_db.py` دارد
  (callback + `reverify_pending` + management command). **این الگو اکنون در
  مستندات و کدِ کپیِ همه‌ی درگاه‌ها اعمال شده** (نه فقط زرین‌پال): هر
  `docs/gateways/<slug>.md` و `scripts/django_<slug>.py` در حالت ۲ خطای
  `GatewayConnectionError` را می‌گیرد، رکورد را `"returned"` (نه `"failed"`)
  «پیش‌علامت» می‌زند، `extra` را در `raw["callback_extra"]` ذخیره می‌کند (برای
  reverify درگاه‌های شاپرکی مثل ملت/سامان/ایران‌کیش/دیجی‌پی)، و یک تابع
  `reverify_pending` برای cron دارد؛ و `payment_result`/نتیجه‌ی هر دو حالت شاخه‌ی
  `payment_status=pending` را هندل می‌کند. بخش مشترک توضیحی در
  `docs/gateways/README.md` («در دسترس نبودن درگاه هنگام verify») است.

### تصمیم‌های ثبت‌شده که نباید بی‌دلیل برگردند
- ملت پس از **تست تراکنش واقعی روی محیط عملیاتی** به registry عمومی منتقل شد
  (۱۴۰۵/۰۴/۰۳) — از experimental خارج و به `core/gateways/mellat.py`. قبلاً به‌دلیل
  نبود تست واقعی در experimental بود؛ حالا قانون طلایی برآورده شده. دو تست رگرسیون
  این را قفل می‌کنند: `test_mellat_in_public_registry` و
  `test_mellat_no_longer_in_experimental` (در test_gateways.py). اگر کسی ملت را
  دوباره به experimental برگرداند، این تست‌ها باید بشکنند. نکته: ملت تنها درگاه
  SOAP در registry است و برای فراخوانی به zeep (`[soap]`) نیاز دارد — ولی import
  ماژولش بدون zeep هم سالم است (zeep فقط داخل `_client()` لازی import می‌شود)، پس
  افزودنش به registry، import کاربران بدون [soap] را نمی‌شکند.
  تغییر امضای verify (افزودن extra=None) زرین‌پال/زیبال را نشکست؛ کل سوییت سبز است.
- سامان پس از **تست تراکنش واقعی با ترمینال واقعی** به registry عمومی منتقل شد
  (نسخه‌ی `1.0.0`) — از experimental خارج و به `core/gateways/saman.py`. دو تست
  رگرسیون قفلش می‌کنند: `test_saman_in_public_registry` و
  `test_saman_no_longer_in_experimental` (در test_gateways.py). اگر کسی سامان را
  دوباره به experimental برگرداند، این تست‌ها باید بشکنند. `_CALLBACK_SPEC` سامان
  (پیدا کردن رکورد با `order_id`/`ResNum`) از قبل موجود بود و دست‌نخورده ماند.
- pay_ir و idpay از کار افتاده‌اند (سرویس کلاً قطع است، نه معلق موقت). در registry
  عمومی نیستند. تست‌های رگرسیون موجود در test_gateways.py این را قفل کرده‌اند:
  `test_pay_ir_not_in_public_registry` و `test_pay_ir_still_importable_from_experimental`
  (و قرینه‌ی idpay اگر هست). اگر کسی این‌ها را دوباره به _REGISTRY افزود، تست‌ها
  باید بشکنند تا جلوی برگشت ناآگاهانه را بگیرند.

### سبک پاسخ مورد انتظار نویسنده
فرض‌ها را به چالش بکش، سطح اطمینان را برچسب بزن ([Certain]/[Probable]/[Speculative])،
حقیقت ناخوشایند را اول بگو، و با مدرک واقعی (اجرای کد) ادعا کن نه از حافظه.
```