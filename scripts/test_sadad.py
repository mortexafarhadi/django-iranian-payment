#!/usr/bin/env python3
"""
تست واقعی درگاه سداد (sadad) — درگاهی که از سایت بانک ملی به آن هدایت می‌شوید.

اجرا از ریشه‌ی پروژه:
    uv run python scripts/test_sadad.py                          # مرحله‌ی ۱: توکن
    uv run python scripts/test_sadad.py verify <TOKEN> <AMOUNT>  # مرحله‌ی ۲

⚠️ پیش‌نیاز:
  ۱. MerchantId, TerminalId, TerminalKey واقعی از سداد (TerminalKey به‌صورت Base64).
  ۲. ثبت IP سرور پذیرنده نزد سداد (وگرنه کد 1029/1003).
  ۳. وابستگی: uv add pycryptodome

برخلاف ایران‌کیش (AES+RSA)، سداد امضا را با 3DES می‌سازد. هدایت ساده است:
کاربر مستقیم به Purchase?Token=<token> ریدایرکت می‌شود.
Token را پس از پرداخت از callback POST بردار و به مرحله‌ی ۲ بده.

⚠️ verify را حداکثر ۱۵ دقیقه پس از پرداخت بزن، وگرنه مبلغ خودکار برمی‌گردد.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from django_iranian_payment.core.experimental.sadad import SadadGateway  # noqa: E402
from django_iranian_payment.core.models import PaymentRequest  # noqa: E402
from django_iranian_payment.core.exceptions import GatewayError  # noqa: E402

# --- پیکربندی (پر کن) ---
MERCHANT_ID = "0000"  # TODO
TERMINAL_ID = "0000"  # TODO
TERMINAL_KEY = "PUT_BASE64_KEY_HERE"  # TODO: کلید پذیرنده به‌صورت Base64

CONFIG = {
    "merchant_id": MERCHANT_ID,
    "terminal_id": TERMINAL_ID,
    "terminal_key": TERMINAL_KEY,
}
SANDBOX = True
AMOUNT = 10_000  # ریال
CALLBACK = "https://example.com/callback/"
ORDER_ID = "1001"  # باید عددی و یکتا باشد


def gateway():
    return SadadGateway(config=CONFIG, sandbox=SANDBOX, timeout=20)


def initiate():
    print("=== سداد: مرحله‌ی ۱ (دریافت توکن) ===")
    if TERMINAL_ID == "0000":
        print("⚠️ هشدار: مقادیر config هنوز پیش‌فرض‌اند. سداد رد خواهد کرد.")
    req = PaymentRequest(
        amount=AMOUNT,
        callback_url=CALLBACK,
        order_id=ORDER_ID,
        description="تست واقعی سداد",
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
    print(f"\n👉 این URL را در مرورگر باز کن و پرداخت کن:\n   {r.redirect_url}\n")
    print("پس از بازگشت، Token را از callback POST بردار و اجرا کن (ظرف ۱۵ دقیقه):")
    print(f"   uv run python scripts/test_sadad.py verify {r.authority} {r.amount_to_send}")


def verify(token, amount):
    print("=== سداد: مرحله‌ی ۲ (verify) ===")
    try:
        r = gateway().verify(authority=token, amount=int(amount), order_id=ORDER_ID)
    except GatewayError as e:
        print(f"❌ {type(e).__name__}: {e}")
        return
    print(
        f"{'✅' if r.is_success else '❌'} status={r.status.value} "
        f"is_success={r.is_success}"
    )
    print(f"   reference_id={r.reference_id} amount={r.amount}")
    print(f"   error_code={r.error_code} error_message={r.error_message}")
    print(f"   raw={r.raw}")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "verify":
        if len(sys.argv) < 4:
            print("استفاده: verify <TOKEN> <AMOUNT>")
        else:
            verify(sys.argv[2], sys.argv[3])
    else:
        initiate()