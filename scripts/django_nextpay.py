"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 راهنمای کامل استفاده از درگاه نکست‌پی در Django
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

نکست‌پی (NextPay) یک درگاه پرداخت اینترنتی با REST API است که برای SME ها و
استارت‌آپ‌ها محبوب است.

⚠️ وضعیت: تجربی (experimental) — کد از مستند رسمی، sandbox هنوز تأیید نشده.
نیاز به api_key واقعی و دامنه ثبت‌شده در پنل نکست‌پی.

━━ قدم ۱: نصب ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    pip install django-iranian-payment

━━ قدم ۲: تنظیمات settings.py ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    INSTALLED_APPS = [
        ...
        "django_iranian_payment.contrib.django",
    ]

    IRANIAN_PAYMENT = {
        "sandbox": True,
        "gateways": {
            "nextpay": {
                "api_key": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                # api_key را از پنل نکست‌پی (https://nextpay.org) بگیر.
                # هنگام ثبت، دامنه/IP سرورت را وارد کن وگرنه code=-33 می‌گیری.
            },
        },
    }

━━ قدم ۳: ثبت درگاه در registry ━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # yourapp/apps.py
    class YourAppConfig(AppConfig):
        name = "yourapp"

        def ready(self):
            from django_iranian_payment.core.gateways import _REGISTRY
            from django_iranian_payment.core.experimental.nextpay import NextPayGateway
            _REGISTRY["nextpay"] = NextPayGateway

━━ قدم ۴: URL های پکیج ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    urlpatterns = [
        ...
        path("payment/", include("django_iranian_payment.contrib.django.urls")),
    ]

    # مسیرها:
    #   GET  /payment/go/<payment_id>/       → هدایت به درگاه
    #   GET  /payment/callback/nextpay/      → برگشت از بانک (GET)

━━ نکات مهم نکست‌پی ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • واحد ارز: پکیج ریال می‌فرستد (currency=IRR). در پنل نکست‌پی مبلغ‌ها
    به تومان نمایش داده می‌شوند — این طبیعی است (تبدیل سمت نکست‌پی).
  • کد موفقیت ساخت توکن code=-1 است (عجیب ولی طبق مستند رسمی).
    کد code=0 یعنی ناموفق.
  • trans_id در callback GET: /callback/nextpay/?transId=<id>&orderId=...
  • کدهای DUPLICATE: code=-25 و code=-49 (قبلاً تأیید شده).
  • نکست‌پی refund() هم دارد (بازگشت وجه پس از verify).
"""

from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse

from django_iranian_payment.contrib.django.services import start_payment
from django_iranian_payment.contrib.django.models import Payment, PaymentStatus
from django_iranian_payment.core.exceptions import GatewayError


def checkout(request):
    """
    شروع پرداخت با نکست‌پی.
    callback با GET برمی‌گردد و trans_id را می‌فرستد.
    """
    order_id = "NP-ORDER-001"
    amount = 180_000  # ریال (نکست‌پی آن را به تومان نمایش می‌دهد)

    callback_url = request.build_absolute_uri(
        reverse("iranian_payment:callback", kwargs={"slug": "nextpay"})
    )

    try:
        payment, redirect_url = start_payment(
            slug="nextpay",
            amount=amount,
            callback_url=callback_url,
            order_id=order_id,
            description="خرید آنلاین",
            mobile="09120000000",  # اختیاری
        )
    except GatewayError as e:
        return HttpResponse(f"خطا در اتصال به نکست‌پی: {e}", status=502)

    request.session["pending_payment_id"] = payment.id

    # کاربر را به درگاه نکست‌پی هدایت کن (GET redirect ساده)
    return HttpResponseRedirect(redirect_url)


def payment_result(request):
    """نتیجه‌ی پرداخت نکست‌پی."""
    status = request.GET.get("payment_status")
    order_id = request.GET.get("order_id", "")

    if status == "success":
        payment = Payment.objects.filter(
            order_id=order_id, status=PaymentStatus.COMPLETE
        ).first()
        if payment:
            return HttpResponse(f"پرداخت موفق! شماره پیگیری: {payment.reference_id}")
    elif status == "failed":
        return HttpResponse("پرداخت ناموفق.")

    return HttpResponse("وضعیت نامشخص.", status=400)


# ─────────────────────────────────────────────────────────────
#  استرداد وجه (refund) نکست‌پی
# ─────────────────────────────────────────────────────────────
#
# نکست‌پی برخلاف درگاه‌های دیگر، متد refund() دارد:
#
#   from django_iranian_payment import get_gateway
#
#   def refund_nextpay(trans_id, amount):
#       gw = get_gateway("nextpay")
#       result = gw.refund(trans_id=trans_id, amount=amount)
#       return result.is_success


if __name__ == "__main__":
    print(
        "این فایل راهنمای Django درگاه نکست‌پی است.\n"
        "برای تست sandbox: uv run python scripts/test_nextpay.py\n"
        "⚠️  نیاز به api_key واقعی و دامنه ثبت‌شده در پنل نکست‌پی."
    )
