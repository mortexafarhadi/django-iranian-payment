#!/usr/bin/env python3
"""
تست sandbox درگاه ایران کیش (irankish).

اجرا از ریشه‌ی پروژه:
    uv run python scripts/test_irankish.py                              # مرحله‌ی ۱: توکن + فرم HTML
    uv run python scripts/test_irankish.py verify <TOKEN> <REFID> <AMOUNT>  # مرحله‌ی ۲

⚠️ پیش‌نیازهای تست واقعی:
  ۱. terminal_id, acceptor_id, pass_phrase واقعی از ایران کیش (شاپرک).
  ۲. فایل کلید عمومی RSA بانک (.pem) — مسیرش را در PUBLIC_KEY_FILE بگذار.
  ۳. ثبت IP سرور پذیرنده نزد ایران کیش.
  ۴. وابستگی‌ها: uv add pycryptodome rsa

نکته‌ی امنیتی: برخلاف کد مرجع، این پیاده‌سازی SSL را خاموش نمی‌کند. اگر گواهی
سرور بانک مشکل داشت، خطای اتصال می‌گیری — این درست است، نه باگ.

تفاوت با زرین‌پال/سامان:
  - initiate یک authenticationEnvelope رمزنگاری‌شده می‌سازد (AES+RSA).
  - verify به token و reference_id نیاز دارد که در callbackِ POST برمی‌گردند.
    پس از پرداخت آن‌ها را از پارامترهای POST بردار و به مرحله‌ی ۲ بده.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from django_iranian_payment.core.experimental.irankish import (  # noqa: E402
    IrankishGateway,
)
from django_iranian_payment.core.models import PaymentRequest  # noqa: E402
from django_iranian_payment.core.exceptions import GatewayError  # noqa: E402

# --- پیکربندی (پر کن) ---
TERMINAL_ID = "0000"  # TODO: hex معتبر
ACCEPTOR_ID = "0000"  # TODO
PASS_PHRASE = "00000000000000000000000000000000"  # TODO: hex معتبر طول زوج
PUBLIC_KEY_FILE = "irankish_public.pem"  # TODO: مسیر کلید عمومی بانک

CONFIG = {
    "terminal_id": TERMINAL_ID,
    "acceptor_id": ACCEPTOR_ID,
    "pass_phrase": PASS_PHRASE,
    "public_key": PUBLIC_KEY_FILE,
}
SANDBOX = True
AMOUNT = 10_000  # ریال
CALLBACK = "https://example.com/callback/"
ORDER_ID = "TEST-IRANKISH-001"

_FORM_FILE = "irankish_redirect.html"


def gateway():
    return IrankishGateway(config=CONFIG, sandbox=SANDBOX, timeout=20)


def _write_redirect_form(token, post_to, token_field):
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>هدایت به درگاه ایران کیش</title></head>
<body onload="document.forms['f'].submit()">
  <p>در حال انتقال به درگاه…</p>
  <form name="f" action="{post_to}" method="post">
    <input type="hidden" name="{token_field}" value="{token}" />
  </form>
</body></html>
"""
    with open(_FORM_FILE, "w", encoding="utf-8") as fh:
        fh.write(html)
    return os.path.abspath(_FORM_FILE)


def initiate():
    print("=== ایران کیش: مرحله‌ی ۱ (دریافت توکن) ===")
    if TERMINAL_ID == "0000":
        print("⚠️ هشدار: مقادیر config هنوز پیش‌فرض‌اند. بانک رد خواهد کرد.")
    if not os.path.exists(PUBLIC_KEY_FILE):
        print(f"⚠️ فایل کلید عمومی پیدا نشد: {PUBLIC_KEY_FILE}")
    req = PaymentRequest(
        amount=AMOUNT,
        callback_url=CALLBACK,
        order_id=ORDER_ID,
        description="تست sandbox ایران کیش",
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

    post_to = r.raw.get("post_to")
    token_field = r.raw.get("token_field", "tokenIdentity")
    form_path = _write_redirect_form(r.authority, post_to, token_field)
    print(f"\n👉 این فایل را در مرورگر باز کن تا به درگاه بروی:\n   file://{form_path}\n")
    print("پس از پرداخت، token و referenceId را از POSTِ callback بردار و اجرا کن:")
    print(
        f"   uv run python scripts/test_irankish.py verify "
        f"{r.authority} <REFERENCE_ID> {r.amount_to_send}"
    )


def verify(token, reference_id, amount):
    print("=== ایران کیش: مرحله‌ی ۲ (verify) ===")
    try:
        r = gateway().verify(
            authority=token,
            amount=int(amount),
            order_id=ORDER_ID,
            extra={"token": token, "reference_id": reference_id, "result_code": "100"},
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


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "verify":
        if len(sys.argv) < 5:
            print("استفاده: verify <TOKEN> <REFERENCE_ID> <AMOUNT>")
        else:
            verify(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        initiate()