"""
تست‌های fee.py — هدف: اثبات گرد رو به بالا، نبود خطای float، و درستی who_pays.
هیچ شبکه/state ای لازم نیست؛ کاملاً قابل اجرا روی هر ماشین.
"""

import pytest

from django_iranian_payment.core.fee import FeeConfig, FeePayer, FeeResult, apply_fee

# ---------- گرد رو به بالا (ceil) ----------


def test_ceil_rounds_up_fraction():
    # 49 * 2% = 0.98 ریال → باید به 1 گرد شود (نه 0)
    r = apply_fee(49, FeeConfig(rate_bps=200, who_pays=FeePayer.MERCHANT))
    assert r.fee == 1


def test_exact_value_not_rounded_up():
    # 50 * 2% = 1.0 دقیق → باید 1 بماند، نه 2
    r = apply_fee(50, FeeConfig(rate_bps=200))
    assert r.fee == 1


def test_just_above_integer_rounds_up():
    # 51 * 2% = 1.02 → باید 2 شود
    r = apply_fee(51, FeeConfig(rate_bps=200))
    assert r.fee == 2


def test_no_float_error_on_large_amount():
    # مبلغ بزرگ که در float خطا می‌داد: 1_000_000_033 * 2%
    # ریاضی دقیق: 20_000_000.66 → ceil = 20_000_001
    r = apply_fee(1_000_000_033, FeeConfig(rate_bps=200))
    assert r.fee == 20_000_001


def test_bankers_rounding_not_used():
    # اگر round() پایتون بود، مقادیر .5 به جفت گرد می‌شدند.
    # 25 * 2% = 0.5 → ceil باید 1 بدهد (banker's می‌داد 0)
    r = apply_fee(25, FeeConfig(rate_bps=200))
    assert r.fee == 1


# ---------- who_pays ----------


def test_customer_pays_adds_to_amount():
    r = apply_fee(100_000, FeeConfig(rate_bps=200, who_pays=FeePayer.CUSTOMER))
    assert r.fee == 2_000
    assert r.amount_to_send == 102_000  # مشتری کارمزد را هم می‌دهد


def test_merchant_pays_does_not_change_amount():
    r = apply_fee(100_000, FeeConfig(rate_bps=200, who_pays=FeePayer.MERCHANT))
    assert r.fee == 2_000
    assert r.amount_to_send == 100_000  # بانک همان مبلغ اصلی را می‌گیرد


# ---------- کارمزد ثابت و ترکیبی ----------


def test_fixed_fee_only():
    r = apply_fee(100_000, FeeConfig(fixed=1_200, who_pays=FeePayer.CUSTOMER))
    assert r.fee == 1_200
    assert r.amount_to_send == 101_200


def test_percentage_plus_fixed():
    r = apply_fee(
        100_000, FeeConfig(rate_bps=200, fixed=500, who_pays=FeePayer.CUSTOMER)
    )
    assert r.fee == 2_500


# ---------- سقف ----------


def test_max_fee_caps_the_fee():
    # 1_000_000 * 2% = 20_000 ولی سقف 5_000 است
    r = apply_fee(
        1_000_000, FeeConfig(rate_bps=200, max_fee=5_000, who_pays=FeePayer.CUSTOMER)
    )
    assert r.fee == 5_000
    assert r.amount_to_send == 1_005_000


def test_max_fee_not_triggered_when_below():
    r = apply_fee(100_000, FeeConfig(rate_bps=200, max_fee=5_000))
    assert r.fee == 2_000  # زیر سقف، دست‌نخورده


# ---------- اعتبارسنجی ورودی ----------


def test_zero_amount_rejected():
    with pytest.raises(ValueError):
        apply_fee(0, FeeConfig(rate_bps=200))


def test_negative_amount_rejected():
    with pytest.raises(ValueError):
        apply_fee(-100, FeeConfig(rate_bps=200))


def test_negative_rate_rejected():
    with pytest.raises(ValueError):
        FeeConfig(rate_bps=-1)


def test_string_who_pays_coerced_to_enum():
    cfg = FeeConfig(who_pays="customer")
    assert cfg.who_pays is FeePayer.CUSTOMER


# ---------- ثبات مرجع یکتا ----------


def test_amount_to_send_is_single_source_of_truth():
    # شبیه‌سازی: همان عددی که initiate می‌فرستد باید در verify هم استفاده شود.
    cfg = FeeConfig(rate_bps=200, who_pays=FeePayer.CUSTOMER)
    r = apply_fee(100_000, cfg)
    initiate_amount = r.amount_to_send
    # verify نباید دوباره محاسبه کند؛ همان عدد را می‌گیرد
    verify_amount = r.amount_to_send
    assert initiate_amount == verify_amount == 102_000
