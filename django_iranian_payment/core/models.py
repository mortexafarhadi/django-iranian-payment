"""
مدل‌های داده‌ی مشترک بین همه‌ی درگاه‌ها.

قاعده‌ی طلایی: واحد «بانک» همیشه و همه‌جا ریال است. amount_to_send که به درگاه و
verify می‌رود همیشه ریال است. ولی کاربر می‌تواند مبلغ ورودی را به تومان بدهد:
PaymentRequest.currency واحد ورودی را مشخص می‌کند و resolve_amount() آن را در همان
لبه به ریال تبدیل می‌کند. پس تبدیل واحد فقط یک‌بار و در ابتدای کار انجام می‌شود و
بقیه‌ی مسیر (درگاه، fee، verify) دست‌نخورده ریالی می‌ماند.

کارمزد در سطح PaymentRequest تعریف می‌شود، نه داخل تک‌تک درگاه‌ها — درگاه فقط
amount نهایی (amount_to_send) را می‌بیند و می‌فرستد. این تله‌ی «verify با مبلغ
اشتباه» را از ریشه می‌بندد.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .fee import FeeConfig, FeeResult, apply_fee


class Currency(str, Enum):
    """واحد مبلغی که کاربر ورودی می‌دهد. بانک همیشه ریال می‌گیرد."""

    RIAL = "rial"
    TOMAN = "toman"


# ضریب تبدیل هر واحد به ریال. ۱ تومان = ۱۰ ریال.
_RIAL_PER_UNIT = {Currency.RIAL: 1, Currency.TOMAN: 10}


def to_rial(amount: int, currency) -> int:
    """مبلغ را از واحد ورودی به ریال (واحد بانک) تبدیل می‌کند. ریال→ریال بدون تغییر."""
    return amount * _RIAL_PER_UNIT[Currency(currency)]


class PaymentStatus(str, Enum):
    SUCCESS = "success"  # پرداخت تأیید و نهایی شد
    FAILED = "failed"  # بانک رد کرد یا verify ناموفق بود
    CANCELLED = "cancelled"  # کاربر بدون پرداخت برگشت
    PENDING = "pending"  # شروع شد ولی هنوز تأیید نشده
    DUPLICATE = "duplicate"  # قبلاً تأیید شده — مثل success رفتار کن


@dataclass
class PaymentRequest:
    """ورودی شروع یک پرداخت."""

    amount: int  # مبلغ پایه‌ی سفارش در واحد currency (پیش‌فرض ریال)، حتماً > صفر
    callback_url: str  # آدرس کاملی که بانک کاربر را به آن برمی‌گرداند
    order_id: str  # شناسه‌ی یکتای سفارش در سیستم تو
    description: str = ""  # متن نمایشی روی صفحه‌ی بانک (اختیاری)
    mobile: Optional[str] = None  # موبایل پرداخت‌کننده (اختیاری)
    email: Optional[str] = None  # ایمیل پرداخت‌کننده (اختیاری)
    fee: Optional[FeeConfig] = None  # تنظیم کارمزد؛ None یعنی بدون کارمزد
    # واحد amount و fee. None یعنی «مشخص‌نشده»: هسته آن را ریال می‌گیرد (رفتار
    # پیش‌فرض)، ولی لایه‌ی Django (get_gateway) واحد سراسری IRANIAN_PAYMENT["currency"]
    # را در initiate تزریق می‌کند. پس مسیر toolkit هم مثل start_payment واحد سراسری
    # را رعایت می‌کند بدون اینکه کاربر currency را در هر PaymentRequest بدهد.
    currency: Optional[Currency] = None

    def __post_init__(self):
        if self.amount <= 0:
            raise ValueError("amount باید بزرگ‌تر از صفر باشد")
        # نرمال‌سازی currency رشته‌ای به enum (و اعتبارسنجی)؛ None دست‌نخورده می‌ماند.
        if self.currency is not None:
            self.currency = Currency(self.currency)

    def _unit(self) -> Currency:
        """واحد مؤثر: currency مشخص‌شده، وگرنه ریال (پیش‌فرض هسته)."""
        return self.currency if self.currency is not None else Currency.RIAL

    def _fee_in_rial(self) -> FeeConfig:
        """نسخه‌ی ریالی از fee می‌سازد (fixed و max_fee از واحد ورودی به ریال)."""
        f = self.fee
        unit = self._unit()
        if unit == Currency.RIAL:
            return f
        return FeeConfig(
            rate_bps=f.rate_bps,  # نرخ bps واحد‌مستقل است
            fixed=to_rial(f.fixed, unit),
            who_pays=f.who_pays,
            max_fee=(to_rial(f.max_fee, unit) if f.max_fee is not None else None),
        )

    def resolve_amount(self) -> FeeResult:
        """
        مبلغ نهایی ارسالی به بانک را محاسبه می‌کند — همیشه به ریال.
        ابتدا amount از واحد currency به ریال تبدیل می‌شود، سپس (در صورت وجود) کارمزد
        ریالی اعمال می‌شود. خروجی این متد مرجع یکتاست: همان amount_to_send (ریال) به
        initiate و verify می‌رود.
        """
        rial_amount = to_rial(self.amount, self._unit())
        if self.fee is None:
            return FeeResult(
                base_amount=rial_amount,
                fee=0,
                amount_to_send=rial_amount,
                who_pays=None,  # type: ignore[arg-type]
            )
        return apply_fee(rial_amount, self._fee_in_rial())


@dataclass
class InitiateResult:
    """خروجی شروع پرداخت — کاربر را به redirect_url بفرست."""

    redirect_url: str
    authority: str  # توکنی که باید با سفارش ذخیره کنی تا در callback پیدایش کنی
    amount_to_send: int = 0  # مبلغ واقعی ارسال‌شده (با کارمزد). همین را در verify بده.
    fee: int = 0  # کارمزد محاسبه‌شده (برای ثبت/گزارش)
    raw: dict = field(default_factory=dict)
    redirect_method: str = (
        "GET"  # روش هدایت: GET (redirect ساده) یا POST (فرم auto-submit)
    )
    redirect_fields: dict = field(
        default_factory=dict
    )  # فیلدهای فرم POST (مثلاً RefId ملت)


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
