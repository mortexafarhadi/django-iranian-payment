"""
مدل‌های داده‌ی مشترک بین همه‌ی درگاه‌ها.

قاعده‌ی طلایی: amount همیشه و همه‌جا به ریال است.
کارمزد در سطح PaymentRequest تعریف می‌شود، نه داخل تک‌تک درگاه‌ها — درگاه فقط
amount نهایی (amount_to_send) را می‌بیند و می‌فرستد. این تله‌ی «verify با مبلغ
اشتباه» را از ریشه می‌بندد.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .fee import FeeConfig, FeeResult, apply_fee


class PaymentStatus(str, Enum):
    SUCCESS = "success"  # پرداخت تأیید و نهایی شد
    FAILED = "failed"  # بانک رد کرد یا verify ناموفق بود
    CANCELLED = "cancelled"  # کاربر بدون پرداخت برگشت
    PENDING = "pending"  # شروع شد ولی هنوز تأیید نشده
    DUPLICATE = "duplicate"  # قبلاً تأیید شده — مثل success رفتار کن


@dataclass
class PaymentRequest:
    """ورودی شروع یک پرداخت."""

    amount: int  # ریال، حتماً بزرگ‌تر از صفر (مبلغ پایه‌ی سفارش)
    callback_url: str  # آدرس کاملی که بانک کاربر را به آن برمی‌گرداند
    order_id: str  # شناسه‌ی یکتای سفارش در سیستم تو
    description: str = ""  # متن نمایشی روی صفحه‌ی بانک (اختیاری)
    mobile: Optional[str] = None  # موبایل پرداخت‌کننده (اختیاری)
    email: Optional[str] = None  # ایمیل پرداخت‌کننده (اختیاری)
    fee: Optional[FeeConfig] = None  # تنظیم کارمزد؛ None یعنی بدون کارمزد

    def __post_init__(self):
        if self.amount <= 0:
            raise ValueError("amount باید بزرگ‌تر از صفر باشد (ریال)")

    def resolve_amount(self) -> FeeResult:
        """
        مبلغ نهایی ارسالی به بانک را محاسبه می‌کند.
        اگر fee تنظیم نشده باشد، amount_to_send == amount است (بدون تغییر).
        خروجی این متد مرجع یکتاست: همان amount_to_send به initiate و verify می‌رود.
        """
        if self.fee is None:
            return FeeResult(
                base_amount=self.amount,
                fee=0,
                amount_to_send=self.amount,
                who_pays=None,  # type: ignore[arg-type]
            )
        return apply_fee(self.amount, self.fee)


@dataclass
class InitiateResult:
    """خروجی شروع پرداخت — کاربر را به redirect_url بفرست."""

    redirect_url: str
    authority: str  # توکنی که باید با سفارش ذخیره کنی تا در callback پیدایش کنی
    amount_to_send: int = 0  # مبلغ واقعی ارسال‌شده (با کارمزد). همین را در verify بده.
    fee: int = 0  # کارمزد محاسبه‌شده (برای ثبت/گزارش)
    raw: dict = field(default_factory=dict)


@dataclass
class PaymentResult:
    """خروجی verify."""

    status: PaymentStatus
    gateway_slug: str
    order_id: str
    reference_id: Optional[str] = None  # شماره‌ی پیگیری بانک (RRN/ref_id)
    amount: Optional[int] = None  # مبلغ تأییدشده به ریال
    card_number: Optional[str] = None  # شماره‌ی کارت ماسک‌شده (اگر بانک بدهد)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw: dict = field(default_factory=dict)

    @property
    def is_success(self):
        return self.status in (PaymentStatus.SUCCESS, PaymentStatus.DUPLICATE)
