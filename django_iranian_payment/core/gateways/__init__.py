"""
registry عمومی — فقط درگاه‌های تست‌شده و پایدار اینجا ثبت می‌شوند.

درگاه‌های معلق (کد سالم، ولی سرویس بی‌ثبات/از کار افتاده) در experimental هستند:
- pay_ir: بی‌ثباتی شبکهٔ پرداخت پی.
- idpay: سرویس از کار افتاده (آخرین فعالیت پشتیبانی ~2025-11-20).
"""
from .mellat import MellatGateway
from .zarinpal import ZarinpalGateway
from .zibal import ZibalGateway

_REGISTRY = {cls.slug: cls for cls in (ZarinpalGateway, ZibalGateway, MellatGateway)}


def available_slugs():
    """لیست درگاه‌های آماده و تست‌شده."""
    return sorted(_REGISTRY.keys())


def get_gateway_class(slug):
    from ..exceptions import GatewayConfigurationError

    try:
        return _REGISTRY[slug]
    except KeyError:
        raise GatewayConfigurationError(
            f"درگاه «{slug}» ثبت نشده. درگاه‌های موجود: {available_slugs()}",
            gateway=slug,
        )