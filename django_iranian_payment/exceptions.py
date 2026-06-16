"""
همه‌ی خطاهای پکیج از GatewayError ارث می‌برند.
این کار به کاربر اجازه می‌دهد با یک except تمام خطاهای درگاه را بگیرد،
یا با except دقیق‌تر فقط یک نوع خاص را مدیریت کند.
"""


class GatewayError(Exception):
    """کلاس پایه‌ی همه‌ی خطاهای درگاه."""

    def __init__(self, message, *, gateway=None, code=None, raw=None):
        super().__init__(message)
        self.gateway = gateway
        self.code = code
        self.raw = raw


class GatewayConfigurationError(GatewayError):
    """تنظیمات اشتباه یا درگاه ناشناخته (مثلاً merchant_id داده نشده)."""


class GatewayConnectionError(GatewayError):
    """خطای شبکه در ارتباط با بانک (timeout، قطع اتصال و ...)."""


class GatewayPaymentError(GatewayError):
    """بانک پرداخت را رد کرد یا verify ناموفق بود."""
