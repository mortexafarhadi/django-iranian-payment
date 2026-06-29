"""
تست واحد پول (currency) — اثبات اینکه تومان درست به ریال تبدیل می‌شود و پیش‌فرض
ریال رفتار قبلی را عوض نمی‌کند.

قاعده: بانک همیشه ریال می‌گیرد؛ currency فقط واحد ورودی کاربر را تعیین می‌کند و
resolve_amount() آن را به ریال تبدیل می‌کند. ۱ تومان = ۱۰ ریال.
"""

import pytest
from django.test import override_settings

from django_iranian_payment.core.models import Currency, PaymentRequest, to_rial
from django_iranian_payment.core.fee import FeeConfig, FeePayer

# ---------- تابع تبدیل خالص ----------


def test_to_rial_rial_is_identity():
    assert to_rial(150_000, Currency.RIAL) == 150_000


def test_to_rial_toman_times_ten():
    assert to_rial(15_000, Currency.TOMAN) == 150_000


def test_to_rial_accepts_string():
    assert to_rial(15_000, "toman") == 150_000
    assert to_rial(150_000, "rial") == 150_000


# ---------- PaymentRequest.resolve_amount ----------


def test_default_currency_is_rial():
    req = PaymentRequest(amount=150_000, callback_url="x", order_id="1")
    assert req.currency == Currency.RIAL
    assert req.resolve_amount().amount_to_send == 150_000  # بدون تغییر


def test_toman_amount_converted_to_rial():
    req = PaymentRequest(
        amount=15_000, callback_url="x", order_id="1", currency="toman"
    )
    resolved = req.resolve_amount()
    assert resolved.base_amount == 150_000
    assert resolved.amount_to_send == 150_000  # ریال به بانک می‌رود


def test_toman_with_customer_fee_all_in_rial():
    # ۱۵۰۰۰ تومان = ۱۵۰۰۰۰ ریال؛ کارمزد ۲٪ = ۳۰۰۰ ریال → ارسالی ۱۵۳۰۰۰ ریال
    req = PaymentRequest(
        amount=15_000,
        callback_url="x",
        order_id="1",
        currency="toman",
        fee=FeeConfig(rate_bps=200, who_pays=FeePayer.CUSTOMER),
    )
    resolved = req.resolve_amount()
    assert resolved.base_amount == 150_000
    assert resolved.fee == 3_000
    assert resolved.amount_to_send == 153_000


def test_toman_fixed_fee_converted_to_rial():
    # fixed=500 تومان باید به ۵۰۰۰ ریال تبدیل شود
    req = PaymentRequest(
        amount=10_000,
        callback_url="x",
        order_id="1",
        currency="toman",
        fee=FeeConfig(rate_bps=0, fixed=500, who_pays=FeePayer.CUSTOMER),
    )
    resolved = req.resolve_amount()
    assert resolved.base_amount == 100_000
    assert resolved.fee == 5_000
    assert resolved.amount_to_send == 105_000


def test_toman_max_fee_converted_to_rial():
    # max_fee=100 تومان = ۱۰۰۰ ریال؛ کارمزد محاسبه‌شده باید به ۱۰۰۰ ریال محدود شود
    req = PaymentRequest(
        amount=100_000,
        callback_url="x",
        order_id="1",
        currency="toman",
        fee=FeeConfig(rate_bps=500, max_fee=100, who_pays=FeePayer.CUSTOMER),
    )
    resolved = req.resolve_amount()
    # 100000 تومان = 1000000 ریال؛ ۵٪ = ۵۰۰۰۰ ولی سقف ۱۰۰۰ ریال
    assert resolved.fee == 1_000
    assert resolved.amount_to_send == 1_001_000


def test_invalid_currency_raises():
    with pytest.raises(ValueError):
        PaymentRequest(amount=1000, callback_url="x", order_id="1", currency="dollar")


# ---------- get_default_currency از settings ----------


def test_get_default_currency_defaults_to_rial():
    from django_iranian_payment import get_default_currency

    with override_settings(IRANIAN_PAYMENT={"gateways": {}}):
        assert get_default_currency() == Currency.RIAL


@override_settings(IRANIAN_PAYMENT={"currency": "toman", "gateways": {}})
def test_get_default_currency_reads_toman():
    from django_iranian_payment import get_default_currency

    assert get_default_currency() == Currency.TOMAN


@override_settings(IRANIAN_PAYMENT={"currency": "dollar", "gateways": {}})
def test_get_default_currency_invalid_raises():
    from django_iranian_payment import get_default_currency
    from django_iranian_payment.core.exceptions import GatewayConfigurationError

    with pytest.raises(GatewayConfigurationError):
        get_default_currency()
