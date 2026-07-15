"""
registry عمومی — فقط درگاه‌های تست‌شده و پایدار اینجا ثبت می‌شوند.

درگاه‌های فعلی:
- zarinpal، zibal: REST، تست sandbox موفق.
- mellat: SOAP، تست تراکنش واقعی موفق روی محیط عملیاتی (bpm.shaparak.ir).
  برای فراخوانی به zeep نیاز دارد: pip install "django-iranian-payment[soap]".
- saman: REST/JSON (SEP)، تست تراکنش واقعی موفق با ترمینال واقعی.
  URL سندباکس جدا ندارد؛ فلگ sandbox بی‌اثر است.

درگاه‌های معلق (کد سالم، ولی سرویس بی‌ثبات/از کار افتاده) در experimental هستند:
- pay_ir: بی‌ثباتی شبکهٔ پرداخت پی.
- idpay: سرویس از کار افتاده (آخرین فعالیت پشتیبانی ~2025-11-20).
"""

from .zarinpal import ZarinpalGateway
from .zibal import ZibalGateway
from .mellat import MellatGateway
from .saman import SamanGateway

_REGISTRY = {
    cls.slug: cls
    for cls in (ZarinpalGateway, ZibalGateway, MellatGateway, SamanGateway)
}


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
