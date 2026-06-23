"""
تست درگاه ملت (SOAP) با InMemoryTransport.soap_call — بدون شبکه، بدون zeep.
منطق کامل initiate/verify/settle/reverse اجرا می‌شود.

این اثبات می‌کند با پاسخ فرضی درست رفتار می‌کنیم؛ اثبات شکل پاسخ واقعی بانک
نیست (آن نیاز به ترمینال واقعی دارد — scripts/test_mellat.py).
"""

import pytest

from django_iranian_payment.core.base import InMemoryTransport
from django_iranian_payment.core.fee import FeeConfig, FeePayer
from django_iranian_payment.core.models import PaymentRequest, PaymentStatus
from django_iranian_payment.core.experimental.mellat import MellatGateway
from django_iranian_payment.core.exceptions import (
    GatewayPaymentError,
    GatewayConfigurationError,
)

CONF = {"terminal_id": "1234", "username": "user", "password": "pass"}


def _gw(transport, **extra_conf):
    conf = {**CONF, **extra_conf}
    return MellatGateway(conf, sandbox=True, transport=transport)


# ---------- initiate ----------


def test_mellat_initiate_success():
    t = InMemoryTransport({"bpPayRequest": "0,AF82041a2Bf6989c7fF9"})
    gw = _gw(t)
    res = gw.initiate(
        PaymentRequest(amount=10_000, callback_url="https://s.com/cb", order_id="100")
    )
    assert res.authority == "AF82041a2Bf6989c7fF9"
    assert res.amount_to_send == 10_000
    # ملت با POST فرم کار می‌کند؛ redirect_url مقصد فرم است و RefId در redirect_fields است
    assert "startpay.mellat" in res.redirect_url
    assert res.redirect_method == "POST"
    assert res.redirect_fields == {"RefId": "AF82041a2Bf6989c7fF9"}
    # مبلغ واقعی به بانک رفت
    assert t.requests_log[0]["params"]["amount"] == 10_000
    assert t.requests_log[0]["params"]["orderId"] == 100


def test_mellat_initiate_with_fee():
    t = InMemoryTransport({"bpPayRequest": "0,REF1"})
    fee = FeeConfig(rate_bps=200, who_pays=FeePayer.CUSTOMER)  # ۲٪
    res = _gw(t).initiate(
        PaymentRequest(amount=100_000, callback_url="cb", order_id="1", fee=fee)
    )
    assert res.amount_to_send == 102_000
    assert res.fee == 2_000
    assert t.requests_log[0]["params"]["amount"] == 102_000


def test_mellat_initiate_rejected():
    t = InMemoryTransport({"bpPayRequest": "21,"})  # کد 21: پذیرنده نامعتبر
    with pytest.raises(GatewayPaymentError) as exc:
        _gw(t).initiate(PaymentRequest(amount=1000, callback_url="cb", order_id="1"))
    assert exc.value.code == "21"


# ---------- verify: حالت تک‌مرحله‌ای (پیش‌فرض) ----------


def test_mellat_verify_settle_default_success():
    t = InMemoryTransport({"bpVerifySettleRequest": "0"})
    gw = _gw(t)  # settle_mode پیش‌فرض = verify_settle
    res = gw.verify(
        authority="REF1",
        amount=10_000,
        order_id="11",
        extra={"sale_reference_id": "127926981246", "sale_order_id": "10"},
    )
    assert res.is_success
    assert res.reference_id == "127926981246"
    # متد درست صدا زده شد (تک‌مرحله‌ای)
    assert t.requests_log[0]["soap_method"] == "bpVerifySettleRequest"
    assert t.requests_log[0]["params"]["saleReferenceId"] == 127926981246


def test_mellat_verify_only_uses_verify_method():
    t = InMemoryTransport({"bpVerifyRequest": "0"})
    gw = _gw(t, settle_mode="verify_only")
    res = gw.verify(
        authority="REF1",
        amount=10_000,
        order_id="11",
        extra={"sale_reference_id": "999", "sale_order_id": "10"},
    )
    assert res.is_success
    # متد جدا صدا زده شد (نه verify_settle)
    assert t.requests_log[0]["soap_method"] == "bpVerifyRequest"


def test_mellat_verify_already_verified_is_duplicate():
    t = InMemoryTransport({"bpVerifySettleRequest": "43"})  # قبلاً verify
    res = _gw(t).verify(
        authority="R",
        amount=1000,
        order_id="1",
        extra={"sale_reference_id": "5"},
    )
    assert res.is_success
    assert res.status == PaymentStatus.DUPLICATE


def test_mellat_verify_failed():
    t = InMemoryTransport({"bpVerifySettleRequest": "17"})  # کاربر منصرف شد
    res = _gw(t).verify(
        authority="R",
        amount=1000,
        order_id="1",
        extra={"sale_reference_id": "5"},
    )
    assert not res.is_success
    assert res.error_code == "17"


def test_mellat_verify_missing_sale_reference_raises():
    t = InMemoryTransport({"bpVerifySettleRequest": "0"})
    with pytest.raises(GatewayPaymentError) as exc:
        _gw(t).verify(authority="R", amount=1000, order_id="1")  # بدون extra
    assert (
        "sale_reference_id" in str(exc.value).lower()
        or exc.value.code == "missing_sale_reference_id"
    )


def test_mellat_sale_order_id_defaults_to_order_id():
    # اگر sale_order_id در extra نباشد، باید با order_id یکسان شود
    t = InMemoryTransport({"bpVerifySettleRequest": "0"})
    _gw(t).verify(
        authority="R",
        amount=1000,
        order_id="55",
        extra={"sale_reference_id": "5"},
    )
    assert t.requests_log[0]["params"]["saleOrderId"] == 55


# ---------- settle (حالت verify_only) ----------


def test_mellat_settle_success():
    t = InMemoryTransport({"bpSettleRequest": "0"})
    res = _gw(t, settle_mode="verify_only").settle(
        order_id="12", sale_order_id="10", sale_reference_id="127926981246"
    )
    assert res.is_success
    assert t.requests_log[0]["soap_method"] == "bpSettleRequest"


def test_mellat_settle_already_settled_duplicate():
    t = InMemoryTransport({"bpSettleRequest": "45"})
    res = _gw(t).settle(order_id="12", sale_order_id="10", sale_reference_id="5")
    assert res.status == PaymentStatus.DUPLICATE


# ---------- reverse ----------


def test_mellat_reverse_success():
    t = InMemoryTransport({"bpReversalRequest": "0"})
    res = _gw(t).reverse(
        order_id="14", sale_order_id="10", sale_reference_id="127926981246"
    )
    assert res.status == PaymentStatus.CANCELLED
    assert t.requests_log[0]["soap_method"] == "bpReversalRequest"


def test_mellat_reverse_already_reversed_duplicate():
    t = InMemoryTransport({"bpReversalRequest": "48"})
    res = _gw(t).reverse(order_id="14", sale_order_id="10", sale_reference_id="5")
    assert res.status == PaymentStatus.DUPLICATE


# ---------- inquiry ----------


def test_mellat_inquiry_returns_code():
    t = InMemoryTransport({"bpInquiryRequest": "43"})
    code = _gw(t).inquiry(order_id="13", sale_order_id="10", sale_reference_id="5")
    assert code == "43"


# ---------- config ----------


def test_mellat_invalid_settle_mode_raises():
    t = InMemoryTransport({"bpVerifySettleRequest": "0"})
    gw = _gw(t, settle_mode="bogus")
    with pytest.raises(GatewayConfigurationError):
        gw.verify(
            authority="R", amount=1, order_id="1", extra={"sale_reference_id": "5"}
        )
