"""
django-iranian-payment

پکیج درگاه‌های پرداخت ایرانی برای Django.
رابط عمومی پکیج اینجا تعریف می‌شود و به هسته‌ی بدون state (core) متصل است.
"""

from .core import (
    DuplicatePaymentError,
    GatewayConfigurationError,
    GatewayConnectionError,
    GatewayError,
    GatewayPaymentError,
    MissingDependencyError,
    FeeConfig,
    FeePayer,
    FeeResult,
    InitiateResult,
    PaymentRequest,
    PaymentResult,
    PaymentStatus,
    available_slugs,
)
from .core.django_integration import get_gateway

__version__ = "0.5.0"

__all__ = [
    "get_gateway",
    "available_slugs",
    "PaymentRequest",
    "PaymentResult",
    "InitiateResult",
    "PaymentStatus",
    "FeeConfig",
    "FeePayer",
    "FeeResult",
    "GatewayError",
    "GatewayConfigurationError",
    "GatewayConnectionError",
    "GatewayPaymentError",
    "DuplicatePaymentError",
    "MissingDependencyError",
]
