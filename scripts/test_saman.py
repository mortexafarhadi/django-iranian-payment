#!/usr/bin/env python3
"""
تست sandbox درگاه سامان (saman / SEP).

اجرا از ریشه‌ی پروژه:
    uv run python scripts/test_saman.py                          # مرحله‌ی ۱: دریافت توکن + فرم HTML
    uv run python scripts/test_saman.py verify <REFNUM> <AMOUNT> # مرحله‌ی ۲: تأیید
    uv run python scripts/test_saman.py reverse <REFNUM>         # برگشت وجه (اختیاری)

⚠️ پیش‌نیازهای تست واقعی سامان (برخلاف زرین‌پال از لپ‌تاپ به‌سادگی ممکن نیست):
  ۱. شماره ترمینال (TerminalId) واقعی از پرداخت الکترونیک سامان.
  ۲. ثبت IP سرور پذیرنده نزد سامان — وگرنه در دریافت توکن کد ۸
     (MerchantIpAddressIsInvalid) می‌گیری. یعنی باید از سرور با IP ثبت‌شده
     اجرا کنی، نه از هر جا.

تفاوت مهم با زرین‌پال:
  - مرحله‌ی ۱ یک «توکن» می‌دهد، نه URL آماده. کاربر باید با فرم POST (فیلد Token)
    از صفحه‌ای که Referrer دارد به درگاه برود؛ ریدایرکت خام رد می‌شود. این اسکریپت
    یک فایل HTML با فرم auto-submit می‌سازد که در مرورگر باز می‌کنی.
  - verify با RefNum انجام می‌شود (نه توکن). RefNum را پس از پرداخت از صفحه‌ی رسید
    یا از پارامترهای POST که به RedirectUrl شما می‌آید بردار و به مرحله‌ی ۲ بده.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from django_iranian_payment.core.gateways.saman import (  # noqa: E402
    SamanGateway,
    _TOKEN_URL,
)
from django_iranian_payment.core.models import PaymentRequest  # noqa: E402
from django_iranian_payment.core.exceptions import GatewayError  # noqa: E402

# --- پیکربندی (پر کن) ---
TERMINAL_ID = "0000"  # TODO: شماره ترمینال واقعی از سامان
CONFIG = {"terminal_id": TERMINAL_ID}
SANDBOX = False  # ⛔ سامان sandbox ندارد؛ SANDBOX=True خطا می‌دهد. فقط live.
AMOUNT = 12_000  # ریال
CALLBACK = "https://example.com/callback/"  # باید با RedirectUrl ثبت‌شده بخواند
ORDER_ID = "TEST-SAMAN-001"  # همان ResNum

_FORM_FILE = "saman_redirect.html"


def gateway():
    return SamanGateway(config=CONFIG, sandbox=SANDBOX, timeout=20)


def _write_redirect_form(token, post_to):
    """
    یک فرم HTML با auto-submit می‌سازد. باز کردنش در مرورگر، Referrer را تولید
    و کاربر را به درگاه می‌فرستد (الزام مستند صفحه‌ی ۱۰).
    """
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>هدایت به درگاه سامان</title></head>
<body onload="document.forms['f'].submit()">
  <p>در حال انتقال به درگاه سامان…</p>
  <form name="f" action="{post_to}" method="post">
    <input type="hidden" name="Token" value="{token}" />
    <input type="hidden" name="GetMethod" value="false" />
  </form>
</body></html>
"""
    with open(_FORM_FILE, "w", encoding="utf-8") as fh:
        fh.write(html)
    return os.path.abspath(_FORM_FILE)


def initiate():
    print("=== سامان: مرحله‌ی ۱ (دریافت توکن) ===")
    if TERMINAL_ID == "0000":
        print("⚠️ هشدار: TERMINAL_ID هنوز مقدار پیش‌فرض است. ممکن است بانک رد کند.")
    req = PaymentRequest(
        amount=AMOUNT,
        callback_url=CALLBACK,
        order_id=ORDER_ID,
        description="تست sandbox سامان",
    )
    try:
        r = gateway().initiate(req)
    except GatewayError as e:
        print(f"❌ {type(e).__name__}: {e}")
        print(f"   gateway={e.gateway} code={e.code} raw={e.raw}")
        return
    print("✅ دریافت توکن موفق")
    print(f"   token          = {r.authority}")
    print(f"   amount_to_send = {r.amount_to_send:,} ریال")

    post_to = r.raw.get("post_to") or _TOKEN_URL
    form_path = _write_redirect_form(r.authority, post_to)
    print(
        f"\n👉 این فایل را در مرورگر باز کن تا به درگاه بروی:\n   file://{form_path}\n"
    )
    print(
        "پس از پرداخت، RefNum را از صفحه‌ی رسید یا از POSTِ callback بردار و اجرا کن:"
    )
    print(f"   uv run python scripts/test_saman.py verify <REFNUM> {r.amount_to_send}")


def verify(ref_num, amount):
    print("=== سامان: مرحله‌ی ۲ (verify) ===")
    try:
        r = gateway().verify(
            authority=ref_num,  # سامان توکن را در verify لازم ندارد
            amount=int(amount),
            order_id=ORDER_ID,
            extra={"ref_num": ref_num, "state": "OK"},
        )
    except GatewayError as e:
        print(f"❌ {type(e).__name__}: {e}")
        return
    print(
        f"{'✅' if r.is_success else '❌'} status={r.status.value} "
        f"is_success={r.is_success}"
    )
    print(f"   reference_id={r.reference_id} amount={r.amount} card={r.card_number}")
    print(f"   error_code={r.error_code} error_message={r.error_message}")
    print(f"   raw={r.raw}")


def reverse(ref_num):
    print("=== سامان: برگشت وجه (reverse) ===")
    try:
        r = gateway().reverse(ref_num=ref_num)
    except GatewayError as e:
        print(f"❌ {type(e).__name__}: {e}")
        return
    print(
        f"{'✅' if r.is_success else '❌'} status={r.status.value} "
        f"reference_id={r.reference_id}"
    )
    print(f"   error_code={r.error_code} error_message={r.error_message}")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "verify":
        if len(sys.argv) < 4:
            print("استفاده: verify <REFNUM> <AMOUNT>")
        else:
            verify(sys.argv[2], sys.argv[3])
    elif len(sys.argv) >= 2 and sys.argv[1] == "reverse":
        if len(sys.argv) < 3:
            print("استفاده: reverse <REFNUM>")
        else:
            reverse(sys.argv[2])
    else:
        initiate()
