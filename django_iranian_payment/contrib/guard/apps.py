from django.apps import AppConfig
from django.core.checks import register

# همان تابع چکِ اپ کامل را دوباره استفاده می‌کنیم (منبع واحد). ثبت دوباره‌ی همان
# شیء تابع بی‌اثر است چون رجیستری چک‌های Django یک set است.
from ..django.apps import check_no_sandbox_gateways


class IranianPaymentGuardConfig(AppConfig):
    name = "django_iranian_payment.contrib.guard"
    label = "iranian_payment_guard"
    verbose_name = "گارد پیکربندی درگاه پرداخت ایرانی"

    def ready(self):
        register(check_no_sandbox_gateways)
