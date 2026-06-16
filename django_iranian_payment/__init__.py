"""
django-iranian-payment

پکیج درگاه‌های پرداخت ایرانی برای Django.
رابط عمومی پکیج اینجا تعریف می‌شود.
"""

from .django_integration import get_gateway
from .exceptions import (
    GatewayConfigurationError,
    GatewayConnectionError,
    GatewayError,
    GatewayPaymentError,
)
from .gateways import available_slugs
from .models import (
    InitiateResult,
    PaymentRequest,
    PaymentResult,
    PaymentStatus,
)

__version__ = "0.1.0"

__all__ = [
    "get_gateway",
    "available_slugs",
    "PaymentRequest",
    "PaymentResult",
    "InitiateResult",
    "PaymentStatus",
    "GatewayError",
    "GatewayConfigurationError",
    "GatewayConnectionError",
    "GatewayPaymentError",
]
