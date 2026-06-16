#!/usr/bin/env python3
"""
تست درگاه تجارت (مبنا) — تجربی/تست‌نشده.

⚠️⚠️ درگاه تجارت کاملاً اسکلت است: initiate و verify هر دو NotImplementedError
می‌دهند و آدرس‌های request/verify/startpay خالی‌اند. callback از نوع POST است.
تا TODOهای core/experimental/tejarat.py با مستندات رسمی «مبنا/تجارت» پر نشوند،
این اسکریپت با خطا متوقف می‌شود — عمدی و درست.

اجرا از ریشه‌ی پروژه:
    uv run python scripts/test_tejarat.py                      # مرحله‌ی ۱: initiate
    uv run python scripts/test_tejarat.py verify <AUTHORITY> <AMOUNT>   # مرحله‌ی ۲
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from django_iranian_payment.core.experimental import TejaratGateway
from django_iranian_payment.core.models import PaymentRequest
from django_iranian_payment.core.exceptions import GatewayError

# --- پیکربندی (پر کن) ---
TERMINAL_ID = "your-terminal-id"   # TODO: terminal_id واقعی از بانک تجارت
CONFIG = {"terminal_id": TERMINAL_ID}
SANDBOX = False                    # تجارت sandbox عمومی شناخته‌شده‌ای ندارد
AMOUNT = 10_000                    # ریال
CALLBACK = "https://example.com/callback/"
ORDER_ID = "TEST-TEJARAT-001"


def gateway():
    return TejaratGateway(config=CONFIG, sandbox=SANDBOX, timeout=30)


def initiate():
    print("=== تجارت: مرحله‌ی ۱ (initiate) ===")
    if TERMINAL_ID == "your-terminal-id":
        print("⚠️ هشدار: terminal_id هنوز پیش‌فرض است.")
    req = PaymentRequest(
        amount=AMOUNT, callback_url=CALLBACK, order_id=ORDER_ID, description="تست تجارت"
    )
    try:
        r = gateway().initiate(req)
    except NotImplementedError as e:
        print(f"⛔ درگاه تجارت هنوز پیاده نشده: {e}")
        print("   ابتدا TODOهای core/experimental/tejarat.py را با مستندات رسمی پر کن.")
        return
    except GatewayError as e:
        print(f"❌ {type(e).__name__}: {e}")
        print(f"   gateway={e.gateway} code={e.code} raw={e.raw}")
        return
    print("✅ initiate موفق")
    print(f"   authority      = {r.authority}")
    print(f"   amount_to_send = {r.amount_to_send:,} ریال")
    print(f"\n👉 این URL را باز کن:\n   {r.redirect_url}\n")
    print("⚠️ callback تجارت POST است؛ authority را از بدنه‌ی POST بردار:")
    print(f"   uv run python scripts/test_tejarat.py verify {r.authority} {r.amount_to_send}")


def verify(authority, amount):
    print("=== تجارت: مرحله‌ی ۲ (verify) ===")
    try:
        r = gateway().verify(authority=authority, amount=int(amount), order_id=ORDER_ID)
    except NotImplementedError as e:
        print(f"⛔ verify تجارت هنوز پیاده نشده: {e}")
        return
    except GatewayError as e:
        print(f"❌ {type(e).__name__}: {e}")
        return
    print(f"{'✅' if r.is_success else '❌'} status={r.status.value} ref={r.reference_id}")
    print(f"   amount={r.amount} card={r.card_number} raw={r.raw}")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "verify":
        if len(sys.argv) < 4:
            print("استفاده: verify <AUTHORITY> <AMOUNT>")
        else:
            verify(sys.argv[2], sys.argv[3])
    else:
        initiate()