#!/usr/bin/env python3
"""
تست sandbox واقعی درگاه ملت (SOAP) — نگارش مستند ۱.۳۸.

⚠️ این اسکریپت با zeep واقعی به سرور تست ملت وصل می‌شود. نیاز دارد:
    uv add zeep
و مقادیر واقعی terminal_id/username/password که IP سرورت نزد ملت ثبت شده باشد
(بدون ثبت IP، سرور درخواست را رد می‌کند — کد پاسخ 421).

سرور تست: pgw.dev.bpmellat.ir   |   سرور عملیاتی: bpm.shaparak.ir

جریان (طبق مستند):
  ۱. initiate → bpPayRequest → خروجی "ResCode,RefId". اگر ResCode=0، یک فرم
     HTML auto-submit ساخته می‌شود که RefId را با POST به startpay می‌فرستد.
  ۲. در مرورگر فرم را submit کن و پرداخت را انجام بده.
  ۳. بانک به callBackUrl تو (POST) برمی‌گردد با SaleReferenceId و SaleOrderId.
     این دو را از بدنه‌ی POST بردار.
  ۴. verify → بسته به settle_mode:
       verify_settle (پیش‌فرض): bpVerifySettleRequest (تأیید+واریز اتمیک)
       verify_only: bpVerifyRequest، سپس باید جداگانه settle بزنی.

اجرا از ریشه‌ی پروژه:
    uv run python scripts/test_mellat.py
    uv run python scripts/test_mellat.py verify <ORDER_ID> <SALE_ORDER_ID> <SALE_REFERENCE_ID>
    uv run python scripts/test_mellat.py settle <ORDER_ID> <SALE_ORDER_ID> <SALE_REFERENCE_ID>
    uv run python scripts/test_mellat.py reverse <ORDER_ID> <SALE_ORDER_ID> <SALE_REFERENCE_ID>
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from django_iranian_payment.core.gateways.mellat import MellatGateway
from django_iranian_payment.core.models import PaymentRequest
from django_iranian_payment.core.exceptions import GatewayError

# --- پیکربندی (پر کن) ---
TERMINAL_ID = "0000000"          # TODO: terminalId واقعی
USERNAME = "your-username"       # TODO: userName واقعی
PASSWORD = "your-password"       # TODO: userPassword واقعی
SETTLE_MODE = "verify_settle"    # یا "verify_only"
CONFIG = {
    "terminal_id": TERMINAL_ID,
    "username": USERNAME,
    "password": PASSWORD,
    "settle_mode": SETTLE_MODE,
}
SANDBOX = True                   # True = pgw.dev.bpmellat.ir
AMOUNT = 10_000                  # ریال
CALLBACK = "https://example.com/callback/"  # باید در دامنه‌ی ثبت‌شده باشد
ORDER_ID = "1001"                # ملت orderId عددی می‌خواهد (یکتا)


def gateway():
    return MellatGateway(config=CONFIG, sandbox=SANDBOX, timeout=30)


def _check_filled():
    if TERMINAL_ID == "0000000" or USERNAME == "your-username":
        print("⚠️ هشدار: مقادیر config پیش‌فرض‌اند. بانک با کد 21/24/421 رد می‌کند.")


def initiate():
    print("=== ملت: مرحله‌ی ۱ (bpPayRequest) ===")
    _check_filled()
    req = PaymentRequest(
        amount=AMOUNT, callback_url=CALLBACK, order_id=ORDER_ID, description="تست ملت"
    )
    try:
        r = gateway().initiate(req)
    except GatewayError as e:
        print(f"❌ {type(e).__name__}: {e}")
        print(f"   gateway={e.gateway} code={e.code} raw={e.raw}")
        return

    print("✅ initiate موفق")
    print(f"   authority(RefId) = {r.authority}")
    print(f"   amount_to_send   = {r.amount_to_send:,} ریال")

    # ملت با POST فرم به startpay می‌رود — فرم auto-submit
    startpay = r.raw.get("startpay_url")
    html = f"""<!doctype html><html><head><meta charset="utf-8"></head>
<body onload="document.forms[0].submit()">
<form action="{startpay}" method="post">
  <input type="hidden" name="RefId" value="{r.authority}">
  <noscript><button type="submit">برو به درگاه ملت</button></noscript>
</form></body></html>"""
    out = "mellat_redirect.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n👉 فایل {out} را در مرورگر باز کن تا به درگاه ملت POST شود.")
    print("پس از پرداخت، از callback (POST) مقادیر SaleReferenceId و SaleOrderId را بردار:")
    print(
        f"   uv run python scripts/test_mellat.py verify {ORDER_ID} <SALE_ORDER_ID> <SALE_REFERENCE_ID>"
    )


def verify(order_id, sale_order_id, sale_reference_id):
    print(f"=== ملت: مرحله‌ی ۲ (verify، حالت {SETTLE_MODE}) ===")
    try:
        r = gateway().verify(
            authority=sale_reference_id,
            amount=AMOUNT,
            order_id=order_id,
            extra={
                "sale_reference_id": sale_reference_id,
                "sale_order_id": sale_order_id,
            },
        )
    except GatewayError as e:
        print(f"❌ {type(e).__name__}: {e}")
        return
    print(
        f"{'✅' if r.is_success else '❌'} status={r.status.value} "
        f"ref={r.reference_id} code={r.error_code or '0'}"
    )
    if SETTLE_MODE == "verify_only" and r.is_success:
        print("⚠️ حالت verify_only: پول هنوز واریز نشده. settle را صدا بزن:")
        print(
            f"   uv run python scripts/test_mellat.py settle {order_id} {sale_order_id} {sale_reference_id}"
        )


def settle(order_id, sale_order_id, sale_reference_id):
    print("=== ملت: settle (bpSettleRequest) ===")
    try:
        r = gateway().settle(
            order_id=order_id,
            sale_order_id=sale_order_id,
            sale_reference_id=sale_reference_id,
        )
    except GatewayError as e:
        print(f"❌ {type(e).__name__}: {e}")
        return
    print(f"{'✅' if r.is_success else '❌'} status={r.status.value} code={r.error_code or '0'}")


def reverse(order_id, sale_order_id, sale_reference_id):
    print("=== ملت: reverse (bpReversalRequest) ===")
    try:
        r = gateway().reverse(
            order_id=order_id,
            sale_order_id=sale_order_id,
            sale_reference_id=sale_reference_id,
        )
    except GatewayError as e:
        print(f"❌ {type(e).__name__}: {e}")
        return
    print(f"status={r.status.value} code={r.error_code or '0'}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) >= 2 else "initiate"
    if cmd in ("verify", "settle", "reverse"):
        if len(sys.argv) < 5:
            print(f"استفاده: {cmd} <ORDER_ID> <SALE_ORDER_ID> <SALE_REFERENCE_ID>")
        else:
            {"verify": verify, "settle": settle, "reverse": reverse}[cmd](
                sys.argv[2], sys.argv[3], sys.argv[4]
            )
    else:
        initiate()