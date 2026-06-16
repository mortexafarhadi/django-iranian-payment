# CLAUDE.md — راهنمای پروژه برای دستیار هوش مصنوعی

این فایل را در ابتدای هر مکالمه‌ی جدید بفرست تا سریع با ساختار، تصمیم‌های معماری و قراردادهای این پروژه آشنا شوی. لطفاً قبل از پیشنهاد هر تغییری، این قراردادها را رعایت کن.

---

## ۱. پروژه چیست

`django-iranian-payment` — یک پکیج پایتون برای Django که درگاه‌های پرداخت ایرانی را یکپارچه می‌کند. روی PyPI منتشر می‌شود تا توسعه‌دهنده‌های دیگر با `pip install` از آن استفاده کنند.

- نویسنده: Morteza Farhadi
- مخزن: https://github.com/mortexafarhadi/django-iranian-payment
- مدیریت محیط با **uv** (نه pip/poetry).
- نسخه‌ی فعلی: `0.1.0` (روی TestPyPI منتشر شده؛ هنوز روی PyPI اصلی نه).

---

## ۲. فلسفه‌ی اصلی — مهم‌ترین بخش

این پکیج پول واقعی جابه‌جا می‌کند. پس قانون طلایی:

> **هیچ درگاهی عمومی نمی‌شود مگر با اطلاعات/ترمینال واقعی تست شده باشد.**

به همین دلیل دو دسته درگاه داریم:

- **درگاه‌های تست‌شده** (`gateways/`): REST/JSON با sandbox واقعی. کامل پیاده و قابل استفاده. در «registry عمومی» ثبت شده‌اند و با `get_gateway("slug")` در دسترس‌اند.
- **درگاه‌های تجربی** (`experimental/`): اسکلت با `TODO` و `NotImplementedError`. در registry عمومی **نیستند**. فقط با import صریح در دسترس‌اند. تست‌نشده.

اگر از من (مدل) خواسته شد درگاه تجربی را «کامل» کنم بدون مستندات واقعی آن بانک، باید هشدار بدهم و فقط اسکلت با TODO بسازم — نه کد حدسی که تظاهر به درستی کند.

---

## ۳. ساختار فایل‌ها

```
django_iranian_payment/
├── __init__.py            # رابط عمومی: get_gateway, available_slugs, PaymentRequest, ...
├── base.py                # BaseGateway: کلاس انتزاعی پایه، _post() امن با timeout
├── models.py              # PaymentRequest, PaymentResult, InitiateResult, PaymentStatus
├── exceptions.py          # GatewayError و زیرشاخه‌ها
├── django_integration.py  # get_gateway(): config را از settings.IRANIAN_PAYMENT می‌خواند
├── gateways/              # درگاه‌های تست‌شده (registry عمومی)
│   ├── __init__.py        # _REGISTRY اینجاست
│   ├── zarinpal.py
│   ├── zibal.py
│   ├── idpay.py
│   └── pay_ir.py
└── experimental/          # درگاه‌های تجربی تست‌نشده (۱۳ عدد)
    ├── __init__.py        # import صریح، خارج از registry عمومی
    ├── mellat.py  saman.py  saderat.py  pasargad.py  sepah.py
    ├── parsian.py  melli.py  irankish.py  tejarat.py
    └── eghtesad_novin.py  nextpay.py  payping.py  vandar.py
```

---

## ۴. قراردادهای معماری (رعایت اجباری)

1. **مبلغ همیشه به ریال است** در سراسر API. هر درگاهی که با تومان کار می‌کند (مثل payping)، تبدیل را *داخل خودش* انجام می‌دهد، نه بیرون. این یکدستی حیاتی است.

2. **بدون state روی کلاس درگاه.** کد قدیمی متغیرهای کلاسی mutable داشت که بین requestها نشت می‌کرد — این رفع شده. هر چیز موقت در متد می‌ماند یا برگردانده می‌شود.

3. **هر درگاه دقیقاً دو متد دارد:** `initiate(request: PaymentRequest) -> InitiateResult` و `verify(*, authority, amount, order_id) -> PaymentResult`.

4. **`amount` و `order_id` در verify از بیرون پاس داده می‌شوند**، چون بعضی درگاه‌ها (زرین‌پال) آن‌ها را در callback برنمی‌گردانند. کاربر باید `authority` را موقع initiate در DB ذخیره کند.

5. **config از `settings.IRANIAN_PAYMENT` خوانده می‌شود**، نه از .env مستقیم. ساختار:
   ```python
   IRANIAN_PAYMENT = {
       "sandbox": True,
       "gateways": {
           "zarinpal": {"merchant_id": "..."},
           "zibal": {"merchant": "zibal"},
       },
   }
   ```

6. **همه‌ی درخواست‌های HTTP timeout اجباری دارند** (از طریق `BaseGateway._post`). خطای شبکه به `GatewayConnectionError` تبدیل می‌شود.

7. **هیچ secret در کد hardcode نمی‌شود.** merchant_id و توکن‌ها فقط از config می‌آیند. (نسخه‌ی اولیه این مشکل را داشت و رفع شد.)

---

## ۵. روند افزودن یک درگاه به registry عمومی (پس از تست)

مثال: عمومی کردن `mellat` پس از تست موفق با ترمینال واقعی:

1. `TODO`های `experimental/mellat.py` را با مستندات رسمی پر و تست کن.
2. فایل را به `gateways/mellat.py` منتقل کن (importهای `..base` و `..models` تغییر نمی‌کنند چون عمق پوشه یکسان است).
3. هشدار «تجربی» را از docstring بردار.
4. در `gateways/__init__.py`: `from .mellat import MellatGateway` و افزودن `MellatGateway` به `_REGISTRY`.
5. از `experimental/__init__.py` خط mellat را حذف کن.
6. نسخه را بالا ببر (`0.2.0` چون قابلیت جدید) و منتشر کن.

---

## ۶. روند انتشار نسخه

1. شماره را در **دو جا** بالا ببر: `pyproject.toml` (`version`) و `django_iranian_payment/__init__.py` (`__version__`). همیشه باید یکی باشند.
2. نسخه‌بندی معنایی: رفع باگ → `0.1.x`، قابلیت جدید → `0.x.0`، پایدار/عمومی → `1.0.0`.
3. build تمیز:
   ```bash
   rm -rf dist/
   uv build
   ```
4. آپلود (نیاز به SOCKS به‌خاطر دسترسی از ایران):
   ```bash
   uvx --with "requests[socks]" twine upload --repository testpypi dist/*   # TestPyPI
   uvx --with "requests[socks]" twine upload dist/*                          # PyPI اصلی
   ```
   username: `__token__` ، password: توکن مربوطه.
5. **هر شماره‌ی نسخه فقط یک‌بار قابل آپلود است** — حتی روی TestPyPI. برای آپلود مجدد باید شماره عوض شود.

---

## ۷. نکات محیط

- مدیریت با **uv**. ابزارهای build/twine را با `uvx` (موقت) اجرا کن، نه `uv add` (که آن‌ها را اشتباهاً به وابستگی پروژه تبدیل می‌کند).
- `pyproject.toml`: لایسنس با فرمت SPDX جدید (`license = "MIT"` + `license-files`)، نیازمند `setuptools>=77.0`.
- آپلود به PyPI از ایران به پروکسی SOCKS نیاز دارد؛ به همین خاطر `--with "requests[socks]"`.
- مسیر پروژه نباید `#` یا فاصله داشته باشد (ابزارها می‌شکنند).

---

## ۸. وضعیت فعلی و کارهای باز

- ✅ ساختار، بسته‌بندی، انتشار روی TestPyPI، نصب در پروژه‌ی واقعی — همه کار می‌کنند.
- ✅ ۴ درگاه تست‌شده (import تأیید شده).
- ⚠️ هنوز **هیچ تراکنش واقعی sandbox تست نشده** — فقط import. منطق initiate/verify با پرداخت واقعی امتحان نشده.
- ⬜ ۱۳ درگاه تجربی فقط اسکلت‌اند.
- ⬜ تست خودکار (pytest با mock کردن requests) هنوز نوشته نشده — قبل از `1.0.0` لازم است.

### سبک پاسخ مورد انتظار نویسنده
نویسنده ترجیح می‌دهد دستیار: فرض‌ها را به چالش بکشد، سطح اطمینان را برچسب بزند ([Certain]/[Probable]/[Speculative])، حقیقت ناخوشایند را اول بگوید، و با مدرک واقعی (اجرای کد) ادعا کند نه از حافظه.
