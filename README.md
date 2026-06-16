# django-iranian-payment

درگاه‌های پرداخت ایرانی برای Django. درگاه به‌صورت کلاس استاندارد پیاده شده و config از `settings.py` خوانده می‌شود.

درگاه‌های آماده و تست‌شده (نسخه‌ی `0.1.0`): زرین‌پال، زیبال، آیدی‌پی، پی‌آی‌آر — همه دارای sandbox واقعی.

درگاه‌های تجربی (تست‌نشده، فقط برای توسعه‌دهنده): ملت و سایر درگاه‌های بانکی در ماژول `experimental` قرار دارند و در پروداکشن استفاده نشوند.

## نصب

```bash
pip install django-iranian-payment
# برای درگاه‌های SOAP (ملت و ...):
pip install "django-iranian-payment[soap]"
```

## تنظیمات

در `settings.py`:

```python
IRANIAN_PAYMENT = {
    "sandbox": True,  # روی پروداکشن False
    "gateways": {
        "zarinpal": {"merchant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"},
        "zibal": {"merchant": "zibal"},
        "idpay": {"api_key": "your-api-key"},
        "pay_ir": {"api": "test"},
    },
}
```

## استفاده

شروع پرداخت:

```python
from django_iranian_payment import get_gateway, PaymentRequest

def start_payment(request, order):
    gw = get_gateway("zarinpal")
    result = gw.initiate(PaymentRequest(
        amount=order.amount,  # ریال
        callback_url="https://yoursite.com/payment/verify/",
        order_id=str(order.id),
        description="پرداخت سفارش",
    ))
    # authority را حتماً با سفارش ذخیره کن تا در verify پیدایش کنی
    order.authority = result.authority
    order.save()
    return redirect(result.redirect_url)
```

تأیید پرداخت (callback):

```python
def verify_payment(request):
    authority = request.GET.get("Authority")
    order = Order.objects.get(authority=authority)
    gw = get_gateway("zarinpal")
    result = gw.verify(
        authority=authority,
        amount=order.amount,   # از دیتابیس خودت
        order_id=str(order.id),
    )
    if result.is_success:
        order.mark_paid(result.reference_id)
        return redirect("/success/")
    return redirect("/failure/")
```

> همه‌ی مبالغ به ریال هستند. authority را در `initiate` ذخیره کن چون بعضی درگاه‌ها (زرین‌پال) مبلغ را در callback برنمی‌گردانند.

## افزودن درگاه جدید

درگاه تجربی پس از تست با اطلاعات واقعی، با افزودن یک خط به `gateways/__init__.py` عمومی می‌شود.

## لایسنس

MIT
