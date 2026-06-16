"""
لایه‌ی اتصال سبک به Django (بدون مدل، بدون state).

کاربر در settings.py می‌نویسد:

    IRANIAN_PAYMENT = {
        "sandbox": True,
        "gateways": {
            "zarinpal": {"merchant_id": "xxxx-...."},
            "zibal": {"merchant": "zibal"},
        },
    }

سپس:
    from django_iranian_payment import get_gateway
    gw = get_gateway("zarinpal")

این تابع state نگه نمی‌دارد. اگر مدل و ردیابی خودکار می‌خواهی، از لایه‌ی
اختیاری django_iranian_payment.contrib.django استفاده کن.
"""

from .exceptions import GatewayConfigurationError
from .gateways import get_gateway_class


def _get_settings():
    # import داخل تابع تا هسته بدون راه‌اندازی Django هم قابل import باشد
    from django.conf import settings

    conf = getattr(settings, "IRANIAN_PAYMENT", None)
    if conf is None:
        raise GatewayConfigurationError(
            "تنظیمات IRANIAN_PAYMENT در settings.py یافت نشد."
        )
    return conf


def get_gateway(slug, *, timeout=15, transport=None):
    """
    یک نمونه‌ی آماده از درگاه می‌سازد، با config خوانده‌شده از settings.
    transport اختیاری است؛ برای تست می‌توانی InMemoryTransport بدهی.
    """
    conf = _get_settings()
    sandbox = bool(conf.get("sandbox", False))
    gateways_conf = conf.get("gateways", {})

    gw_config = gateways_conf.get(slug)
    if gw_config is None:
        raise GatewayConfigurationError(
            f'تنظیمات درگاه «{slug}» در IRANIAN_PAYMENT["gateways"] نیست.',
            gateway=slug,
        )

    gateway_cls = get_gateway_class(slug)
    return gateway_cls(
        config=gw_config, sandbox=sandbox, timeout=timeout, transport=transport
    )
