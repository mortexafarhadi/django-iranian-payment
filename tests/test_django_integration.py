"""
تست get_gateway و به‌ویژه «sandbox مجزای هر درگاه».

اولویت: آرگومان صریح > config درگاه > sandbox سراسری > False.
نیازمند pytest-django نیست؛ از override_settings روی settings پیکربندی‌شده‌ی
conftest استفاده می‌کنیم.
"""

from django.test import override_settings

from django_iranian_payment import get_gateway


@override_settings(
    IRANIAN_PAYMENT={
        "sandbox": True,
        "gateways": {"zarinpal": {"merchant_id": "m"}},
    }
)
def test_gateway_follows_global_sandbox_when_not_overridden():
    # درگاه کلید sandbox ندارد → از مقدار سراسری (True) پیروی می‌کند.
    gw = get_gateway("zarinpal")
    assert gw.sandbox is True


@override_settings(
    IRANIAN_PAYMENT={
        "sandbox": True,
        "gateways": {"zarinpal": {"merchant_id": "m", "sandbox": False}},
    }
)
def test_per_gateway_sandbox_overrides_global():
    # سراسری True است ولی این درگاه صریحاً False گذاشته → باید live باشد.
    gw = get_gateway("zarinpal")
    assert gw.sandbox is False


@override_settings(
    IRANIAN_PAYMENT={
        "gateways": {"zarinpal": {"merchant_id": "m", "sandbox": True}},
    }
)
def test_per_gateway_sandbox_without_global_key():
    # کلید سراسری اصلاً نیست (پیش‌فرض False) ولی درگاه True گذاشته.
    gw = get_gateway("zarinpal")
    assert gw.sandbox is True


@override_settings(
    IRANIAN_PAYMENT={
        "gateways": {"zarinpal": {"merchant_id": "m"}},
    }
)
def test_default_is_live_when_nothing_set():
    # نه سراسری نه درگاه → پیش‌فرض False (live).
    gw = get_gateway("zarinpal")
    assert gw.sandbox is False


@override_settings(
    IRANIAN_PAYMENT={
        "sandbox": False,
        "gateways": {"zarinpal": {"merchant_id": "m", "sandbox": False}},
    }
)
def test_explicit_arg_overrides_everything():
    # هم سراسری هم درگاه False؛ ولی آرگومان صریح True بر هر دو اولویت دارد.
    gw = get_gateway("zarinpal", sandbox=True)
    assert gw.sandbox is True


@override_settings(
    IRANIAN_PAYMENT={
        "sandbox": True,
        "gateways": {"zarinpal": {"merchant_id": "m", "sandbox": False}},
    }
)
def test_sandbox_key_not_leaked_into_gateway_config():
    # کلید کنترلی sandbox نباید به config خود درگاه نشت کند.
    gw = get_gateway("zarinpal")
    assert "sandbox" not in gw.config
    assert gw.config == {"merchant_id": "m"}


@override_settings(
    IRANIAN_PAYMENT={
        "sandbox": True,
        "gateways": {
            "zarinpal": {"merchant_id": "m"},
            "zibal": {"merchant": "z", "sandbox": False},
        },
    }
)
def test_two_gateways_independent_sandbox():
    # سناریوی اصلی کاربر: یک درگاه sandbox، دیگری live، هم‌زمان.
    zp = get_gateway("zarinpal")
    zb = get_gateway("zibal")
    assert zp.sandbox is True
    assert zb.sandbox is False
