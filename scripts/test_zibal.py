#!/usr/bin/env python3
"""
تست sandbox درگاه زیبال (zibal).

اجرا از ریشه‌ی پروژه:
    uv run python scripts/test_zibal.py                      # مرحله‌ی ۱: تولید درگاه
    uv run python scripts/test_zibal.py verify <TRACK_ID> <AMOUNT>   # مرحله‌ی ۲: تأیید

زیبال با merchant='zibal' بدون ثبت‌نام قابل تست است.
در callback مقدار trackId را بردار و در مرحله‌ی ۲ بده.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from django_iranian_payment.core.gateways.zibal import ZibalGateway
from django_iranian_payment.core.models import PaymentRequest
from django_iranian_payment.core.exceptions import GatewayError

# --- پیکربندی ---
CONFIG = {"merchant": "zibal"}  # sandbox رسمی زیبال
SANDBOX = True
AMOUNT = 100_000  # ریال
CALLBACK = "https://example.com/callback/"
ORDER_ID = "TEST-ZIBAL-001"


def gateway():
    return ZibalGateway(config=CONFIG, sandbox=SANDBOX, timeout=20)


def initiate():
    print("=== زیبال: مرحله‌ی ۱ (initiate) ===")
    req = PaymentRequest(
        amount=AMOUNT,
        callback_url=CALLBACK,
        order_id=ORDER_ID,
        description="تست sandbox زیبال",
    )
    try:
        r = gateway().initiate(req)
    except GatewayError as e:
        print(f"❌ {type(e).__name__}: {e}")
        print(f"   gateway={e.gateway} code={e.code} raw={e.raw}")
        return
    print("✅ initiate موفق")
    print(f"   authority      = {r.authority}")
    print(f"   amount_to_send = {r.amount_to_send:,} ریال")
    print(f"\n👉 این URL را در مرورگر باز کن و پرداخت کن:\n   {r.redirect_url}\n")
    print("پس از بازگشت، trackId را از callback بردار و اجرا کن:")
    print(
        f"   uv run python scripts/test_zibal.py verify {r.authority} {r.amount_to_send}"
    )


def verify(authority, amount):
    print("=== زیبال: مرحله‌ی ۲ (verify) ===")
    try:
        r = gateway().verify(authority=authority, amount=int(amount), order_id=ORDER_ID)
    except GatewayError as e:
        print(f"❌ {type(e).__name__}: {e}")
        return
    print(
        f"{'✅' if r.is_success else '❌'} status={r.status.value} "
        f"is_success={r.is_success}"
    )
    print(f"   reference_id={r.reference_id} amount={r.amount} card={r.card_number}")
    print(f"   raw={r.raw}")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "verify":
        if len(sys.argv) < 4:
            print("استفاده: verify <TRACK_ID> <AMOUNT>")
        else:
            verify(sys.argv[2], sys.argv[3])
    else:
        initiate()
