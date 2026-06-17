"""
تست درگاه نکست‌پی (nextpay) با InMemoryTransport — بدون شبکه.

اثبات می‌کند با پاسخ فرضیِ مطابق مستند درست رفتار می‌کنیم؛ اثبات شکل پاسخ واقعی
بانک نیست (آن نیاز به کلید واقعی دارد).
"""

import pytest

from django_iranian_payment.core.base import InMemoryTransport
from django_iranian_payment.core.fee import FeeConfig, FeePayer
from django_iranian_payment.core.models import PaymentRequest, PaymentStatus
from django_iranian_payment.core.experimental.nextpay import (
    NextPayGateway,
    _TOKEN_URL,
    _VERIFY_URL,
)
from django_iranian_payment.core.exceptions import GatewayPaymentError

CONF = {"api_key": "b11ee9c3-d23d-414e-8b6e-f2370baac97b"}


def _gw(transport, **extra_conf):
    return NextPayGateway({**CONF, **extra_conf}, sandbox=True, transport=transport)


# ---------- initiate ----------


def test_nextpay_initiate_success():
    # ⚠️ کد موفقیت ساخت توکن -1 است، نه 0
    t = InMemoryTransport({_TOKEN_URL: {"code": -1, "trans_id": "TID123"}})
    res = _gw(t).initiate(
        PaymentRequest(amount=74_250, callback_url="https://s.com/cb", order_id="85NX")
    )
    assert res.authority == "TID123"
    assert res.amount_to_send == 74_250
    assert res.redirect_url.endswith("/TID123")
    sent = t.requests_log[0]["json"]
    assert sent["amount"] == 74_250
    assert sent["order_id"] == "85NX"
    assert sent["currency"] == "IRR"  # ریالی اعلام می‌شود تا تله‌ی تومان نباشد


def test_nextpay_initiate_with_fee():
    t = InMemoryTransport({_TOKEN_URL: {"code": -1, "trans_id": "T"}})
    fee = FeeConfig(rate_bps=200, who_pays=FeePayer.CUSTOMER)  # ۲٪
    res = _gw(t).initiate(
        PaymentRequest(amount=100_000, callback_url="cb", order_id="1", fee=fee)
    )
    assert res.amount_to_send == 102_000
    assert res.fee == 2_000
    assert t.requests_log[0]["json"]["amount"] == 102_000


def test_nextpay_initiate_code_zero_is_not_success():
    # تله: code==0 در ساخت توکن موفقیت نیست (موفقیت -1 است)
    t = InMemoryTransport({_TOKEN_URL: {"code": 0, "trans_id": "X"}})
    with pytest.raises(GatewayPaymentError) as exc:
        _gw(t).initiate(PaymentRequest(amount=1000, callback_url="cb", order_id="1"))
    assert exc.value.code == "0"


def test_nextpay_initiate_rejected():
    t = InMemoryTransport({_TOKEN_URL: {"code": -33}})  # کلید مجوز صحیح نیست
    with pytest.raises(GatewayPaymentError) as exc:
        _gw(t).initiate(PaymentRequest(amount=1000, callback_url="cb", order_id="1"))
    assert exc.value.code == "-33"


def test_nextpay_initiate_code_as_string():
    # code گاهی رشته می‌آید؛ باید درست تفسیر شود
    t = InMemoryTransport({_TOKEN_URL: {"code": "-1", "trans_id": "TID"}})
    res = _gw(t).initiate(
        PaymentRequest(amount=1000, callback_url="cb", order_id="1")
    )
    assert res.authority == "TID"


# ---------- verify ----------


def test_nextpay_verify_success():
    t = InMemoryTransport(
        {
            _VERIFY_URL: {
                "code": 0,
                "amount": 74_250,
                "order_id": "85NX",
                "card_holder": "5022-29**-****-5020",
                "Shaparak_Ref_Id": "141196584609",
            }
        }
    )
    res = _gw(t).verify(authority="TID", amount=74_250, order_id="85NX")
    assert res.is_success
    assert res.status == PaymentStatus.SUCCESS
    assert res.reference_id == "141196584609"
    assert res.card_number == "5022-29**-****-5020"
    sent = t.requests_log[0]["json"]
    assert sent["trans_id"] == "TID"
    assert sent["amount"] == 74_250
    assert sent["currency"] == "IRR"


def test_nextpay_verify_duplicate_already_sent():
    t = InMemoryTransport({_VERIFY_URL: {"code": -25}})
    res = _gw(t).verify(authority="TID", amount=1000, order_id="1")
    assert res.is_success
    assert res.status == PaymentStatus.DUPLICATE


def test_nextpay_verify_duplicate_code_49():
    t = InMemoryTransport({_VERIFY_URL: {"code": -49}})
    res = _gw(t).verify(authority="TID", amount=1000, order_id="1")
    assert res.status == PaymentStatus.DUPLICATE


def test_nextpay_verify_failed_cancelled_by_user():
    t = InMemoryTransport({_VERIFY_URL: {"code": -2}})  # رد شده توسط کاربر/بانک
    res = _gw(t).verify(authority="TID", amount=1000, order_id="1")
    assert not res.is_success
    assert res.error_code == "-2"


def test_nextpay_verify_ignores_extra():
    # درگاه ساده: extra را نادیده می‌گیرد (برخلاف ملت/سامان)
    t = InMemoryTransport({_VERIFY_URL: {"code": 0, "Shaparak_Ref_Id": "1"}})
    res = _gw(t).verify(
        authority="TID", amount=1000, order_id="1", extra={"foo": "bar"}
    )
    assert res.is_success


# ---------- refund ----------


def test_nextpay_refund_success():
    t = InMemoryTransport({_VERIFY_URL: {"code": -90, "Shaparak_Ref_Id": "1", "order_id": "85NX"}})
    res = _gw(t).refund(authority="TID", amount=74_250, order_id="85NX")
    assert res.status == PaymentStatus.CANCELLED
    sent = t.requests_log[0]["json"]
    assert sent["refund_request"] == "yes_money_back"


def test_nextpay_refund_failed():
    t = InMemoryTransport({_VERIFY_URL: {"code": -29}})  # کد بازگشت مبلغ صحیح نیست
    res = _gw(t).refund(authority="TID", amount=1000)
    assert not res.is_success
    assert res.error_code == "-29"


# ---------- registry ----------


def test_nextpay_importable_from_experimental():
    from django_iranian_payment.core.experimental.nextpay import (
        NextPayGateway as G,
    )
    assert G is NextPayGateway