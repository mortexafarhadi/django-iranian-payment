"""
مدل‌های داده‌ی مشترک بین همه‌ی درگاه‌ها.

به‌جای پاس دادن آرگومان‌های پراکنده، یک شیء استاندارد رد و بدل می‌کنیم.
قاعده‌ی طلایی: amount همیشه و همه‌جا به ریال است.
هر درگاهی که با تومان کار می‌کند، تبدیل را داخل خودش انجام می‌دهد، نه بیرون.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PaymentStatus(str, Enum):
    SUCCESS = "success"      # پرداخت تأیید و نهایی شد
    FAILED = "failed"        # بانک رد کرد یا verify ناموفق بود
    CANCELLED = "cancelled"  # کاربر بدون پرداخت برگشت
    DUPLICATE = "duplicate"  # قبلاً تأیید شده — مثل success رفتار کن


@dataclass
class PaymentRequest:
    """ورودی شروع یک پرداخت."""
    amount: int                      # ریال، حتماً بزرگ‌تر از صفر
    callback_url: str                # آدرس کاملی که بانک کاربر را به آن برمی‌گرداند
    order_id: str                    # شناسه‌ی یکتای سفارش در سیستم تو
    description: str = ""            # متن نمایشی روی صفحه‌ی بانک (اختیاری)
    mobile: Optional[str] = None     # موبایل پرداخت‌کننده (اختیاری)
    email: Optional[str] = None      # ایمیل پرداخت‌کننده (اختیاری)


@dataclass
class InitiateResult:
    """خروجی شروع پرداخت — کاربر را به redirect_url بفرست."""
    redirect_url: str
    authority: str                   # توکنی که باید با سفارش ذخیره کنی تا در callback پیدایش کنی
    raw: dict = field(default_factory=dict)


@dataclass
class PaymentResult:
    """خروجی verify."""
    status: PaymentStatus
    gateway_slug: str
    order_id: str
    reference_id: Optional[str] = None   # شماره‌ی پیگیری بانک (RRN/ref_id)
    amount: Optional[int] = None         # مبلغ تأییدشده به ریال
    card_number: Optional[str] = None    # شماره‌ی کارت ماسک‌شده (اگر بانک بدهد)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw: dict = field(default_factory=dict)

    @property
    def is_success(self):
        return self.status in (PaymentStatus.SUCCESS, PaymentStatus.DUPLICATE)
