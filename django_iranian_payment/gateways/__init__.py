"""
registry عمومی — فقط درگاه‌های تست‌شده اینجا ثبت می‌شوند.

وقتی یک درگاه تجربی را تست کردی و مطمئن شدی، فقط import و یک خط در
_REGISTRY اضافه کن. تا آن لحظه، کاربر عادی به آن دسترسی ندارد.
"""

from .idpay import IDPayGateway
from .pay_ir import PayIrGateway
from .zarinpal import ZarinpalGateway
from .zibal import ZibalGateway

_REGISTRY = {
    cls.slug: cls
    for cls in (ZarinpalGateway, ZibalGateway, IDPayGateway, PayIrGateway)
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
