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
    Currency,
    FeeConfig,
    FeePayer,
    FeeResult,
    InitiateResult,
    PaymentRequest,
    PaymentResult,
    PaymentStatus,
    available_slugs,
    to_rial,
)
from .core.django_integration import get_default_currency, get_gateway

__version__ = "1.0.0"

__all__ = [
    "get_gateway",
    "get_default_currency",
    "available_slugs",
    "PaymentRequest",
    "PaymentResult",
    "InitiateResult",
    "PaymentStatus",
    "Currency",
    "to_rial",
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
