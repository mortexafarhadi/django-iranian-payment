#!/usr/bin/env python3
"""
تست درگاه سامان کیش — تجربی/تست‌نشده.

⚠️⚠️ درگاه سامان کاملاً اسکلت است: initiate و verify هر دو NotImplementedError
می‌دهند و آدرس‌ها خالی‌اند. جریان سامان: initiate یک توکن می‌گیرد، سپس با فرم
POST (نه redirect ساده) به درگاه می‌رود. callback هم POST است. تا TODOهای
core/experimental/saman.py با مستندات رسمی سامان کیش پر نشوند، این اسکریپت
با خطا متوقف می‌شود — عمدی و درست.

اجرا از ریشه‌ی پروژه:
    uv run python scripts/test_saman.py                        # مرحله‌ی ۱: گرفتن توکن + ساخت فرم
    uv run python scripts/test_saman.py verify <REF_NUM> <AMOUNT>      # مرحله‌ی ۲: تأیید

نکته: در callback سامان (POST)، معمولاً RefNum و ResNum و State برمی‌گردند.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from django_iranian_payment.core.experimental import SamanGateway
from django_iranian_payment.core.models import PaymentRequest
from django_iranian_payment.core.exceptions import GatewayError

# --- پیکربندی (پر کن) ---
TERMINAL_ID = "your-terminal-id"   # TODO: terminal_id (MID) واقعی سامان
PASSWORD = "your-password"         # TODO: password واقعی
CONFIG = {"terminal_id": TERMINAL_ID, "password": PASSWORD}
SANDBOX = False                    # سامان sandbox عمومی شناخته‌شده‌ای ندارد
AMOUNT = 10_000                    # ریال
CALLBACK = "https://example.com/callback/"
ORDER_ID = "TEST-SAMAN-001"


def gateway():
    return SamanGateway(config=CONFIG, sandbox=SANDBOX, timeout=30)


def initiate():
    print("=== سامان: مرحله‌ی ۱ (دریافت توکن) ===")
    if TERMINAL_ID == "your-terminal-id":
        print("⚠️ هشدار: مقادیر config هنوز پیش‌فرض‌اند.")
    req = PaymentRequest(
        amount=AMOUNT, callback_url=CALLBACK, order_id=ORDER_ID, description="تست سامان"
    )
    try:
        r = gateway().initiate(req)
    except NotImplementedError as e:
        print(f"⛔ درگاه سامان هنوز پیاده نشده: {e}")
        print("   ابتدا TODOهای core/experimental/saman.py را با مستندات رسمی پر کن.")
        return
    except GatewayError as e:
        print(f"❌ {type(e).__name__}: {e}")
        print(f"   gateway={e.gateway} code={e.code} raw={e.raw}")
        return

    print("✅ initiate موفق")
    print(f"   authority(token) = {r.authority}")
    print(f"   amount_to_send   = {r.amount_to_send:,} ریال")

    # سامان با POST فرم (token) به درگاه می‌رود — فرم HTML auto-submit
    token = r.authority
    startpay = r.redirect_url or "https://sep.shaparak.ir/OnlinePG/OnlinePG"
    html = f"""<!doctype html><html><body onload="document.forms[0].submit()">
<form action="{startpay}" method="post">
  <input type="hidden" name="Token" value="{token}">
  <input type="hidden" name="GetMethod" value="true">
  <noscript><button type="submit">برو به درگاه سامان</button></noscript>
</form></body></html>"""
    out = "saman_redirect.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n👉 فایل {out} ساخته شد. در مرورگر باز کن تا به درگاه سامان POST شود.")
    print("پس از پرداخت، از callback (POST) مقدار RefNum را بردار:")
    print(f"   uv run python scripts/test_saman.py verify <REF_NUM> {r.amount_to_send}")


def verify(ref_num, amount):
    print("=== سامان: مرحله‌ی ۲ (verifyTransaction) ===")
    try:
        r = gateway().verify(authority=ref_num, amount=int(amount), order_id=ORDER_ID)
    except NotImplementedError as e:
        print(f"⛔ verify سامان هنوز پیاده نشده: {e}")
        return
    except GatewayError as e:
        print(f"❌ {type(e).__name__}: {e}")
        return
    print(f"{'✅' if r.is_success else '❌'} status={r.status.value} ref={r.reference_id}")
    print(f"   amount={r.amount} card={r.card_number} raw={r.raw}")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "verify":
        if len(sys.argv) < 4:
            print("استفاده: verify <REF_NUM> <AMOUNT>")
        else:
            verify(sys.argv[2], sys.argv[3])
    else:
        initiate()