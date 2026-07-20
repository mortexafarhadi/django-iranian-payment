"""
تست get_gateway و به‌ویژه «sandbox مجزای هر درگاه».

اولویت: آرگومان صریح > config درگاه > sandbox سراسری > False.
نیازمند pytest-django نیست؛ از override_settings روی settings پیکربندی‌شده‌ی
conftest استفاده می‌کنیم.
"""

import pytest
from django.test import override_settings

from django_iranian_payment import get_gateway
from django_iranian_payment.core.exceptions import GatewayConfigurationError


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


# ── درگاه‌های بدون sandbox: sandbox=True باید خطا بدهد (سامان/ملت) ──────────


@override_settings(
    IRANIAN_PAYMENT={
        "gateways": {"saman": {"terminal_id": "t", "sandbox": True}},
    }
)
def test_saman_sandbox_true_raises_via_get_gateway():
    # رگرسیون: سامان sandbox ندارد؛ config درگاه sandbox=True → خطای صریح.
    with pytest.raises(GatewayConfigurationError):
        get_gateway("saman")


@override_settings(
    IRANIAN_PAYMENT={
        "sandbox": True,  # سراسری True؛ سامان صریحاً override نکرده
        "gateways": {"saman": {"terminal_id": "t"}},
    }
)
def test_saman_inherits_global_sandbox_true_raises():
    # سامان sandbox سراسری True را ارث می‌برد → همان خطا. راه‌حل: sandbox=False صریح.
    with pytest.raises(GatewayConfigurationError):
        get_gateway("saman")


@override_settings(
    IRANIAN_PAYMENT={
        "sandbox": True,
        "gateways": {"saman": {"terminal_id": "t", "sandbox": False}},
    }
)
def test_saman_with_explicit_sandbox_false_works_under_global_true():
    # راه درست: sandbox این درگاه را False کن تا با وجود sandbox سراسری True کار کند.
    gw = get_gateway("saman")
    assert gw.sandbox is False


@override_settings(
    IRANIAN_PAYMENT={
        "gateways": {
            "mellat": {
                "terminal_id": "t",
                "username": "u",
                "password": "p",
                "sandbox": True,
            }
        },
    }
)
def test_mellat_sandbox_true_raises_via_get_gateway():
    # رگرسیون: ملت هم sandbox ندارد؛ sandbox=True → خطای صریح.
    with pytest.raises(GatewayConfigurationError):
        get_gateway("mellat")


# ── system check سطح startup: پروژه با sandbox روی سامان/ملت اجرا نشود ──────

from django_iranian_payment.contrib.django.apps import (  # noqa: E402
    check_no_sandbox_gateways,
)


@override_settings(
    IRANIAN_PAYMENT={"gateways": {"saman": {"terminal_id": "t", "sandbox": True}}}
)
def test_system_check_flags_saman_sandbox_true():
    # رگرسیون باگ کاربر: runserver با saman sandbox=True نباید بالا بیاید.
    errors = check_no_sandbox_gateways(None)
    assert len(errors) == 1
    assert errors[0].id == "iranian_payment.E001"
    assert "saman" in errors[0].msg


@override_settings(
    IRANIAN_PAYMENT={"sandbox": True, "gateways": {"saman": {"terminal_id": "t"}}}
)
def test_system_check_flags_saman_inheriting_global_sandbox():
    # سامان بدون کلید sandbox ولی سراسری True → باز هم خطا.
    errors = check_no_sandbox_gateways(None)
    assert len(errors) == 1
    assert errors[0].id == "iranian_payment.E001"


@override_settings(
    IRANIAN_PAYMENT={
        "sandbox": True,
        "gateways": {"saman": {"terminal_id": "t", "sandbox": False}},
    }
)
def test_system_check_ok_when_saman_sandbox_false():
    # راه درست: sandbox این درگاه False → بدون خطا، پروژه بالا می‌آید.
    assert check_no_sandbox_gateways(None) == []


@override_settings(
    IRANIAN_PAYMENT={
        "gateways": {
            "mellat": {
                "terminal_id": "t",
                "username": "u",
                "password": "p",
                "sandbox": True,
            }
        }
    }
)
def test_system_check_flags_mellat_sandbox_true():
    errors = check_no_sandbox_gateways(None)
    assert len(errors) == 1
    assert "mellat" in errors[0].msg


@override_settings(
    IRANIAN_PAYMENT={"sandbox": True, "gateways": {"zarinpal": {"merchant_id": "m"}}}
)
def test_system_check_allows_zarinpal_sandbox():
    # زرین‌پال sandbox واقعی دارد → sandbox=True مجاز، بدون خطا.
    assert check_no_sandbox_gateways(None) == []


def test_system_check_no_settings_is_ok():
    # نبود IRANIAN_PAYMENT نباید خطا بدهد.
    assert check_no_sandbox_gateways(None) == []


def test_guard_app_reuses_same_check_object():
    # اپ سبک contrib.guard (برای حالت مدیریت دستی DB) همان تابع چک را ثبت می‌کند.
    # شیء یکسان یعنی ثبت دوباره در رجیستری set دوباره‌کاری نمی‌کند.
    from django_iranian_payment.contrib.guard import apps as guard_apps

    assert guard_apps.check_no_sandbox_gateways is check_no_sandbox_gateways


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


# ─────────────────────────────────────────────────────────────
#  تزریق واحد پول سراسری در مسیر toolkit (get_gateway().initiate())
# ─────────────────────────────────────────────────────────────
#
# رگرسیون باگِ واقعی: کاربر IRANIAN_PAYMENT["currency"]="toman" گذاشت ولی چون از
# get_gateway().initiate(PaymentRequest(amount=...)) استفاده می‌کرد (نه start_payment)
# و currency را روی PaymentRequest نمی‌داد، مبلغِ تومان خام به بانک می‌رفت (تومان با
# ریال فرقی نداشت). حالا get_gateway واحد سراسری را به درخواستِ بدون currency تزریق
# می‌کند، پس مسیر toolkit هم تبدیل را انجام می‌دهد.

from django_iranian_payment.core.base import InMemoryTransport
from django_iranian_payment.core.models import Currency, PaymentRequest

ZP_REQ = "https://sandbox.zarinpal.com/pg/v4/payment/request.json"


@override_settings(
    IRANIAN_PAYMENT={
        "sandbox": True,
        "currency": "toman",
        "gateways": {"zarinpal": {"merchant_id": "m"}},
    }
)
def test_get_gateway_injects_global_toman_into_toolkit_request():
    t = InMemoryTransport({ZP_REQ: {"data": {"authority": "A"}, "errors": []}})
    gw = get_gateway("zarinpal", transport=t)
    # کاربر currency نمی‌دهد (مثل اسکریپت‌های toolkit)
    req = PaymentRequest(amount=15_000, callback_url="cb", order_id="1")
    result = gw.initiate(req)
    # واحد سراسری toman تزریق شد → ۱۵۰۰۰ تومان = ۱۵۰۰۰۰ ریال به بانک
    assert t.requests_log[0]["json"]["amount"] == 150_000
    assert result.amount_to_send == 150_000
    assert req.currency == Currency.TOMAN  # تزریق روی خود درخواست هم دیده می‌شود


@override_settings(
    IRANIAN_PAYMENT={
        "sandbox": True,
        "currency": "toman",
        "gateways": {"zarinpal": {"merchant_id": "m"}},
    }
)
def test_explicit_request_currency_overrides_global_injection():
    t = InMemoryTransport({ZP_REQ: {"data": {"authority": "A"}, "errors": []}})
    gw = get_gateway("zarinpal", transport=t)
    # کاربر صریحاً ریال خواسته → تزریق سراسری (toman) نباید غالب شود
    req = PaymentRequest(
        amount=15_000, callback_url="cb", order_id="1", currency="rial"
    )
    gw.initiate(req)
    assert t.requests_log[0]["json"]["amount"] == 15_000  # ریال دست‌نخورده


@override_settings(
    IRANIAN_PAYMENT={
        "sandbox": True,
        "gateways": {"zarinpal": {"merchant_id": "m"}},
    }
)
def test_default_rial_toolkit_request_unchanged():
    # بدون کلید currency سراسری (پیش‌فرض rial) → رفتار قبلی: بدون تبدیل.
    t = InMemoryTransport({ZP_REQ: {"data": {"authority": "A"}, "errors": []}})
    gw = get_gateway("zarinpal", transport=t)
    req = PaymentRequest(amount=15_000, callback_url="cb", order_id="1")
    gw.initiate(req)
    assert t.requests_log[0]["json"]["amount"] == 15_000
