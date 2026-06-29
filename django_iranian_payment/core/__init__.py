"""
هسته‌ی بدون state پکیج — بدون هیچ وابستگی به Django.
این لایه در FastAPI، اسکریپت ساده، یا هر جای دیگر هم قابل استفاده است.
"""

from .base import BaseGateway, BaseTransport, InMemoryTransport, RequestsTransport
from .exceptions import (
    DuplicatePaymentError,
    GatewayConfigurationError,
    GatewayConnectionError,
    GatewayError,
    GatewayPaymentError,
    MissingDependencyError,
)
from .fee import FeeConfig, FeePayer, FeeResult, apply_fee
from .gateways import available_slugs, get_gateway_class
from .models import (
    Currency,
    InitiateResult,
    PaymentRequest,
    PaymentResult,
    PaymentStatus,
    to_rial,
)

__all__ = [
    "BaseGateway",
    "BaseTransport",
    "RequestsTransport",
    "InMemoryTransport",
    "available_slugs",
    "get_gateway_class",
    "FeeConfig",
    "FeePayer",
    "FeeResult",
    "apply_fee",
    "PaymentRequest",
    "PaymentResult",
    "InitiateResult",
    "PaymentStatus",
    "Currency",
    "to_rial",
    "GatewayError",
    "GatewayConfigurationError",
    "GatewayConnectionError",
    "GatewayPaymentError",
    "DuplicatePaymentError",
    "MissingDependencyError",
]
