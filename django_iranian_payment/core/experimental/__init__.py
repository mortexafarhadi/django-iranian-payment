"""
core/experimental/__init__.py — re-export درگاه‌های تجربی و معلق/ازکارافتاده.

⚠️ نکته‌ی ادغام: فایل واقعی __init__ این پوشه در کپی پروژه‌ای که Claude دید موجود
نبود. این یک نسخه‌ی محتمل بر اساس README/CLAUDE.md است. تنها تغییر لازم نسبت به
نسخه‌ی فعلی پروژه، افزودن خط DigipayGateway است؛ بقیه را با موجودی خودت تطبیق بده
و خطوط تکراری/جاافتاده را اصلاح کن.

این درگاه‌ها در registry عمومی (core/gateways) نیستند و با get_gateway در دسترس
نیستند؛ فقط با import صریح از همین‌جا.
"""

# درگاه‌های تجربی: کد کامل از مستند رسمی، تست‌نشده با ترمینال/sandbox واقعی
from .mellat import MellatGateway  # noqa: F401
from .saman import SamanGateway  # noqa: F401
from .irankish import IrankishGateway  # noqa: F401
from .nextpay import NextPayGateway  # noqa: F401
from .sadad import SadadGateway  # noqa: F401
from .digipay import DigipayGateway  # noqa: F401  ← خط جدید دیجی‌پی

# درگاه‌های از کار افتاده (سرویس دیگر فعال نیست؛ کد به‌عنوان آرشیو)
from .pay_ir import PayIrGateway  # noqa: F401
from .idpay import IDPayGateway  # noqa: F401

__all__ = [
    "MellatGateway",
    "SamanGateway",
    "IrankishGateway",
    "NextPayGateway",
    "SadadGateway",
    "DigipayGateway",
    "PayIrGateway",
    "IDPayGateway",
]
