"""
اسکریپت تست دستی sandbox درگاه دیجی‌پی — این تست خودکار pytest نیست.
ابزار دستی برای تست با کلید/کاربر واقعی دیجی‌پی، گام لازم پیش از عمومی‌کردن درگاه.

⚠️ تا کلید واقعی (username/password/client_id/client_secret/provider_id) از دیجی‌پی
نگیری، این اجرا نمی‌شود. دیجی‌پی محیط staging دارد (uat.mydigipay.info) که با
sandbox=True استفاده می‌شود.

دو مرحله‌ای:
  مرحله ۱) ساخت تیکت و گرفتن payUrl:
      uv run python scripts/test_digipay.py
    خروجی: redirect_url را در مرورگر باز کن و پرداخت را کامل کن. پس از بازگشت،
    دیجی‌پی در callback مقدار trackingCode و providerId را برمی‌گرداند.

  مرحله ۲) تأیید با trackingCode بازگشتی:
      uv run python scripts/test_digipay.py verify <TRACKING_CODE> <AMOUNT>
    که <AMOUNT> همان amount_to_send مرحله‌ی ۱ است (با کارمزد، اگر بود).

نکته: providerId را همین اسکریپت می‌سازد و چاپ می‌کند؛ در مرحله‌ی verify باید
همان providerId استفاده شود (اینجا با ثابت ماندن ORDER_ID تضمین شده).
"""

import sys

from django_iranian_payment.core.experimental.digipay import DigipayGateway
from django_iranian_payment.core.models import PaymentRequest

# ---------- مقادیر را پیش از اجرا پر کن ----------
CONFIG = {
    "username": "",
    "password": "",
    "client_id": "",
    "client_secret": "",
    "provider_id": "",
    # "ticket_type": 11,  # پیش‌فرض 11 (UPG)؛ در صورت نیاز تغییر بده
}
AMOUNT = 10_000  # ریال
CALLBACK_URL = "https://example.com/callback"
ORDER_ID = "test-digipay-001"  # همان providerId که در verify هم لازم است
MOBILE = ""  # اختیاری، مثل "09120000000"
# -------------------------------------------------


def _check_config():
    missing = [k for k in DigipayGateway.requires if not CONFIG.get(k)]
    if missing:
        print(f"✗ مقادیر config را پر کن: {missing}")
        sys.exit(1)


def do_initiate():
    _check_config()
    gw = DigipayGateway(CONFIG, sandbox=True)
    req = PaymentRequest(
        amount=AMOUNT,
        callback_url=CALLBACK_URL,
        order_id=ORDER_ID,
        mobile=MOBILE or None,
    )
    res = gw.initiate(req)
    print("✓ تیکت ساخته شد")
    print(f"  ticket (authority): {res.authority}")
    print(f"  amount_to_send:     {res.amount_to_send}")
    print(f"  providerId:         {ORDER_ID}")
    print()
    print("این آدرس را در مرورگر باز کن و پرداخت را کامل کن:")
    print(f"  {res.redirect_url}")
    print()
    print("پس از بازگشت، trackingCode را از callback بردار و اجرا کن:")
    print(
        f"  uv run python scripts/test_digipay.py verify <TRACKING_CODE> {res.amount_to_send}"
    )


def do_verify(tracking_code, amount):
    _check_config()
    gw = DigipayGateway(CONFIG, sandbox=True)
    res = gw.verify(
        authority=tracking_code,
        amount=int(amount),
        order_id=ORDER_ID,
        extra={"tracking_code": tracking_code},
    )
    print(f"  status:       {res.status}")
    print(f"  is_success:   {res.is_success}")
    print(f"  reference_id: {res.reference_id}")
    if not res.is_success:
        print(f"  error_code:    {res.error_code}")
        print(f"  error_message: {res.error_message}")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "verify":
        if len(sys.argv) != 4:
            print("استفاده: test_digipay.py verify <TRACKING_CODE> <AMOUNT>")
            sys.exit(1)
        do_verify(sys.argv[2], sys.argv[3])
    else:
        do_initiate()
