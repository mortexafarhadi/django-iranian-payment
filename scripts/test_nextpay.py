#!/usr/bin/env python3
"""
تست واقعی درگاه نکست‌پی (nextpay).

اجرا از ریشه‌ی پروژه:
    uv run python scripts/test_nextpay.py                          # مرحله‌ی ۱: توکن
    uv run python scripts/test_nextpay.py verify <TRANS_ID> <AMOUNT>  # مرحله‌ی ۲

⚠️ پیش‌نیاز: api_key واقعی از پنل نکست‌پی. هنگام ثبت درگاه، دامنه/IP سرور را
درست وارد کن وگرنه خطای «کلید مجوز دهی صحیح نیست» (code -33) می‌گیری.

نکته‌ی واحد پول: این پکیج ریال می‌گیرد و currency=IRR به نکست‌پی می‌فرستد. اگر
در پنل نکست‌پی مبلغ‌ها را تومان می‌بینی، تقسیم بر ۱۰ همان است (تبدیل سمت نکست‌پی).

برخلاف سامان/ایران‌کیش، هدایت ساده است: کاربر مستقیم به
gateway/payment/<trans_id> ریدایرکت می‌شود (نیازی به فرم POST نیست).
trans_id را پس از پرداخت از callback (پارامتر GET) بردار و به مرحله‌ی ۲ بده.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from django_iranian_payment.core.experimental.nextpay import (  # noqa: E402
    NextPayGateway,
)
from django_iranian_payment.core.models import PaymentRequest  # noqa: E402
from django_iranian_payment.core.exceptions import GatewayError  # noqa: E402

# --- پیکربندی (پر کن) ---
API_KEY = "00000000-0000-0000-0000-000000000000"  # TODO: api_key واقعی نکست‌پی
CONFIG = {"api_key": API_KEY}
SANDBOX = True
AMOUNT = 10_000  # ریال (نکست‌پی آن را تومان‌سازی می‌کند چون currency=IRR می‌فرستیم)
CALLBACK = "https://example.com/callback/"
ORDER_ID = "TEST-NEXTPAY-001"


def gateway():
    return NextPayGateway(config=CONFIG, sandbox=SANDBOX, timeout=20)


def initiate():
    print("=== نکست‌پی: مرحله‌ی ۱ (دریافت توکن) ===")
    if API_KEY == "00000000-0000-0000-0000-000000000000":
        print("⚠️ هشدار: API_KEY هنوز پیش‌فرض است. نکست‌پی رد خواهد کرد (code -33).")
    req = PaymentRequest(
        amount=AMOUNT,
        callback_url=CALLBACK,
        order_id=ORDER_ID,
        description="تست واقعی نکست‌پی",
    )
    try:
        r = gateway().initiate(req)
    except GatewayError as e:
        print(f"❌ {type(e).__name__}: {e}")
        print(f"   gateway={e.gateway} code={e.code} raw={e.raw}")
        return
    print("✅ دریافت توکن موفق")
    print(f"   trans_id       = {r.authority}")
    print(f"   amount_to_send = {r.amount_to_send:,} ریال")
    print(f"\n👉 این URL را در مرورگر باز کن و پرداخت کن:\n   {r.redirect_url}\n")
    print("پس از بازگشت، trans_id را از callback بردار و اجرا کن:")
    print(
        f"   uv run python scripts/test_nextpay.py verify "
        f"{r.authority} {r.amount_to_send}"
    )


def verify(trans_id, amount):
    print("=== نکست‌پی: مرحله‌ی ۲ (verify) ===")
    try:
        r = gateway().verify(authority=trans_id, amount=int(amount), order_id=ORDER_ID)
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
        if len(sys.argv) < 4:
            print("استفاده: verify <TRANS_ID> <AMOUNT>")
        else:
            verify(sys.argv[2], sys.argv[3])
    else:
        initiate()
