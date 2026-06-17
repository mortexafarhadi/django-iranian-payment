#!/usr/bin/env python3
"""
تست sandbox درگاه پی‌آی‌آر (Pay.ir).

⚠️ هشدار — درگاه معلق (suspended):
این درگاه موقتاً از registry عمومی خارج و به core/experimental منتقل شده است.
دلیل: در عمل با خطای دسترسی مواجه شد و وضعیت عملیاتی/حقوقی شبکهٔ پرداخت پی
بی‌ثبات گزارش شده (دوره‌های مسدودیت ترمینال‌ها). کد پیاده‌سازی سالم است؛ این
اسکریپت برای تأیید مجدد پایداری سرویس پیش از بازگردانی به registry نگه داشته شده.
get_gateway("pay_ir") دیگر کار نمی‌کند؛ این اسکریپت مستقیماً از experimental
import می‌کند.

اجرا از ریشه‌ی پروژه:
    uv run python scripts/test_pay_ir.py                     # مرحله‌ی ۱: تولید درگاه
    uv run python scripts/test_pay_ir.py verify <TOKEN> <AMOUNT>    # مرحله‌ی ۲: تأیید

پی‌آی‌آر با api='test' بدون ثبت‌نام قابل تست است (در صورت در دسترس بودن سرویس).
در callback مقدار token را بردار و در مرحله‌ی ۲ بده.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# import از experimental (درگاه معلق)، نه از gateways عمومی
from django_iranian_payment.core.experimental import PayIrGateway
from django_iranian_payment.core.models import PaymentRequest
from django_iranian_payment.core.exceptions import GatewayError

# --- پیکربندی ---
CONFIG = {"api": "test"}  # sandbox رسمی pay.ir
SANDBOX = True
AMOUNT = 10_000  # ریال
CALLBACK = "https://example.com/callback/"
ORDER_ID = "TEST-PAYIR-001"


def gateway():
    return PayIrGateway(config=CONFIG, sandbox=SANDBOX, timeout=20)


def initiate():
    print("=== پی‌آی‌آر (معلق): مرحله‌ی ۱ (initiate) ===")
    print("⚠️ این درگاه معلق است. اگر سرویس در دسترس نباشد، خطای ارتباط طبیعی است.")
    req = PaymentRequest(
        amount=AMOUNT,
        callback_url=CALLBACK,
        order_id=ORDER_ID,
        description="تست sandbox پی‌آی‌آر",
    )
    try:
        r = gateway().initiate(req)
    except GatewayError as e:
        print(f"❌ {type(e).__name__}: {e}")
        print(f"   gateway={e.gateway} code={e.code} raw={e.raw}")
        return
    print("✅ initiate موفق")
    print(f"   authority(token) = {r.authority}")
    print(f"   amount_to_send   = {r.amount_to_send:,} ریال")
    print(f"\n👉 این URL را در مرورگر باز کن و پرداخت کن:\n   {r.redirect_url}\n")
    print("پس از بازگشت، token را از callback بردار و اجرا کن:")
    print(
        f"   uv run python scripts/test_pay_ir.py verify {r.authority} {r.amount_to_send}"
    )


def verify(authority, amount):
    print("=== پی‌آی‌آر (معلق): مرحله‌ی ۲ (verify) ===")
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
            print("استفاده: verify <TOKEN> <AMOUNT>")
        else:
            verify(sys.argv[2], sys.argv[3])
    else:
        initiate()
