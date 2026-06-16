"""
محاسبه‌ی کارمزد — تابع خالص، بدون state، بدون شبکه.

قواعد طلایی:
- همه‌جا ریال است. ورودی ریال، خروجی ریال.
- کارمزد همیشه «رو به بالا» (ceil) گرد می‌شود تا پذیرنده هیچ‌وقت کسری ضرر نکند.
- محاسبه‌ی پول هرگز با float انجام نمی‌شود؛ نرخ به bps (واحد پایه) است:
      ۱٪ = ۱۰۰ bps ، ۲٪ = ۲۰۰ bps ، ۲.۵٪ = ۲۵۰ bps.
- خروجی amount_to_send تنها مرجع است: همان عدد به initiate و verify می‌رود،
  هیچ‌جا دوباره محاسبه نمی‌شود.
"""

from dataclasses import dataclass
from enum import Enum


class FeePayer(str, Enum):
    CUSTOMER = "customer"  # کارمزد به مبلغ تراکنش اضافه می‌شود؛ مشتری می‌پردازد
    MERCHANT = "merchant"  # مبلغ بانک تغییر نمی‌کند؛ کارمزد فقط گزارشی است


@dataclass(frozen=True)
class FeeConfig:
    """تنظیم کارمزد یک درگاه. در config هر درگاه قرار می‌گیرد."""

    rate_bps: int = 0  # نرخ به bps. مثلا 200 یعنی ۲٪
    fixed: int = 0  # کارمزد ثابت به ریال، به ازای هر تراکنش
    who_pays: FeePayer = FeePayer.MERCHANT
    max_fee: int | None = None  # سقف کارمزد به ریال (None = بدون سقف)

    def __post_init__(self):
        if self.rate_bps < 0:
            raise ValueError("rate_bps نمی‌تواند منفی باشد")
        if self.fixed < 0:
            raise ValueError("fixed نمی‌تواند منفی باشد")
        if self.max_fee is not None and self.max_fee < 0:
            raise ValueError("max_fee نمی‌تواند منفی باشد")
        if not isinstance(self.who_pays, FeePayer):
            object.__setattr__(self, "who_pays", FeePayer(self.who_pays))


@dataclass(frozen=True)
class FeeResult:
    base_amount: int  # مبلغ اصلی سفارش (ریال)
    fee: int  # کارمزد محاسبه‌شده‌ی گردشده (ریال)
    amount_to_send: int  # مبلغی که واقعاً به بانک می‌رود (ریال) — مرجع یکتا
    who_pays: FeePayer


def _ceil_div(numerator: int, denominator: int) -> int:
    """تقسیم صحیح با گرد رو به بالا. بدون float."""
    if denominator <= 0:
        raise ValueError("denominator باید مثبت باشد")
    return -(-numerator // denominator)  # ceil برای اعداد نامنفی


def apply_fee(base_amount: int, config: FeeConfig) -> FeeResult:
    """
    کارمزد را روی مبلغ پایه (ریال) اعمال می‌کند و یک FeeResult برمی‌گرداند.

    - fee = ceil(base * rate_bps / 10000) + fixed ، سپس محدود به max_fee.
    - اگر who_pays == CUSTOMER : amount_to_send = base + fee.
    - اگر who_pays == MERCHANT : amount_to_send = base (کارمزد فقط گزارشی).
    """
    if base_amount <= 0:
        raise ValueError("base_amount باید بزرگ‌تر از صفر باشد")

    percentage_part = _ceil_div(base_amount * config.rate_bps, 10000)
    fee = percentage_part + config.fixed

    if config.max_fee is not None:
        fee = min(fee, config.max_fee)

    if config.who_pays is FeePayer.CUSTOMER:
        amount_to_send = base_amount + fee
    else:
        amount_to_send = base_amount

    return FeeResult(
        base_amount=base_amount,
        fee=fee,
        amount_to_send=amount_to_send,
        who_pays=config.who_pays,
    )
