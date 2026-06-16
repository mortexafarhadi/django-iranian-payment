#!/usr/bin/env python3
"""
تست sandbox درگاه آیدی‌پی (idpay).

اجرا از ریشه‌ی پروژه:
    uv run python scripts/test_idpay.py                      # مرحله‌ی ۱: تولید درگاه
    uv run python scripts/test_idpay.py verify <ID> <AMOUNT>        # مرحله‌ی ۲: تأیید

⚠️ نیاز به api_key واقعی از پنل آیدی‌پی. حالت sandbox با هدر X-SANDBOX:1 فعال می‌شود.
مقدار API_KEY زیر را پر کن.
در callback (که POST است) مقدار id را بردار و در مرحله‌ی ۲ بده.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from django_iranian_payment.core.experimental.idpay import IDPayGateway
from django_iranian_payment.core.models import PaymentRequest
from django_iranian_payment.core.exceptions import GatewayError

# --- پیکربندی (پر کن) ---
API_KEY = "c2461613-dd2b-416b-b4dc-a88b240703ee"  # TODO: api_key واقعی از پنل آیدی‌پی
CONFIG = {"api_key": API_KEY}
SANDBOX = True
AMOUNT = 10_000  # ریال
CALLBACK = "https://example.com/callback/"
ORDER_ID = "TEST-IDPAY-001"


def gateway():
    return IDPayGateway(config=CONFIG, sandbox=SANDBOX, timeout=20)


def initiate():
    print("=== آیدی‌پی: مرحله‌ی ۱ (initiate) ===")
    if API_KEY == "your-idpay-api-key":
        print("⚠️ هشدار: API_KEY هنوز مقدار پیش‌فرض است. بانک رد خواهد کرد.")
    req = PaymentRequest(
        amount=AMOUNT,
        callback_url=CALLBACK,
        order_id=ORDER_ID,
        description="تست sandbox آیدی‌پی",
    )
    try:
        r = gateway().initiate(req)
    except GatewayError as e:
        print(f"❌ {type(e).__name__}: {e}")
        print(f"   gateway={e.gateway} code={e.code} raw={e.raw}")
        return
    print("✅ initiate موفق")
    print(f"   authority(id)  = {r.authority}")
    print(f"   amount_to_send = {r.amount_to_send:,} ریال")
    print(f"\n👉 این URL را در مرورگر باز کن و پرداخت کن:\n   {r.redirect_url}\n")
    print("پس از بازگشت (callback از نوع POST)، id را بردار و اجرا کن:")
    print(
        f"   uv run python scripts/test_idpay.py verify {r.authority} {r.amount_to_send}"
    )


def verify(authority, amount):
    print("=== آیدی‌پی: مرحله‌ی ۲ (verify) ===")
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
            print("استفاده: verify <ID> <AMOUNT>")
        else:
            verify(sys.argv[2], sys.argv[3])
    else:
        initiate()
