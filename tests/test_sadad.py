"""
تست درگاه سداد (sadad) با InMemoryTransport — بدون شبکه.

اثبات می‌کند با پاسخ فرضیِ مطابق مستند درست رفتار می‌کنیم و رمزنگاری 3DES
واقعی کار می‌کند؛ اثبات شکل پاسخ واقعی بانک نیست (آن نیاز به ترمینال واقعی دارد).
"""

import base64

import pytest

from django_iranian_payment.core.base import InMemoryTransport
from django_iranian_payment.core.fee import FeeConfig, FeePayer
from django_iranian_payment.core.models import PaymentRequest, PaymentStatus
from django_iranian_payment.core.experimental.sadad import (
    SadadGateway,
    _REQUEST_URL,
    _VERIFY_URL,
)
from django_iranian_payment.core.exceptions import (
    GatewayPaymentError,
    GatewayConfigurationError,
)

# کلید ۲۴ بایتی معتبر برای 3DES، به‌صورت Base64 (همان فرمتی که سداد می‌دهد)
_KEY_B64 = base64.b64encode(b"0123456789abcdef01234567").decode()

CONF = {
    "merchant_id": "123456",
    "terminal_id": "12345678",
    "terminal_key": _KEY_B64,
}


def _gw(transport, **extra_conf):
    return SadadGateway({**CONF, **extra_conf}, sandbox=True, transport=transport)


# ---------- initiate ----------


def test_sadad_initiate_success():
    t = InMemoryTransport({_REQUEST_URL: {"ResCode": 0, "Token": "TOK123"}})
    res = _gw(t).initiate(
        PaymentRequest(amount=50_000, callback_url="https://s.com/cb", order_id="1001")
    )
    assert res.authority == "TOK123"
    assert res.amount_to_send == 50_000
    assert "TOK123" in res.redirect_url
    sent = t.requests_log[0]["json"]
    assert sent["Amount"] == 50_000
    assert sent["OrderId"] == 1001
    assert sent["MerchantId"] == "123456"
    # SignData باید رمزنگاری‌شده و غیرخالی باشد
    assert sent["SignData"]
    base64.b64decode(sent["SignData"])  # Base64 معتبر


def test_sadad_initiate_with_fee():
    t = InMemoryTransport({_REQUEST_URL: {"ResCode": 0, "Token": "T"}})
    fee = FeeConfig(rate_bps=200, who_pays=FeePayer.CUSTOMER)  # ۲٪
    res = _gw(t).initiate(
        PaymentRequest(amount=100_000, callback_url="cb", order_id="1", fee=fee)
    )
    assert res.amount_to_send == 102_000
    assert res.fee == 2_000
    assert t.requests_log[0]["json"]["Amount"] == 102_000


def test_sadad_initiate_rejected():
    t = InMemoryTransport({_REQUEST_URL: {"ResCode": 1011, "Description": "تکراری"}})
    with pytest.raises(GatewayPaymentError) as exc:
        _gw(t).initiate(PaymentRequest(amount=1000, callback_url="cb", order_id="1"))
    assert exc.value.code == "1011"


def test_sadad_initiate_ok_but_no_token():
    t = InMemoryTransport({_REQUEST_URL: {"ResCode": 0}})
    with pytest.raises(GatewayPaymentError):
        _gw(t).initiate(PaymentRequest(amount=1000, callback_url="cb", order_id="1"))


# ---------- verify ----------


def test_sadad_verify_success():
    t = InMemoryTransport(
        {
            _VERIFY_URL: {
                "ResCode": 0,
                "Amount": 50_000,
                "OrderId": 1001,
                "RetrivalRefNo": "987654321",
                "SystemTraceNo": "123456",
            }
        }
    )
    res = _gw(t).verify(authority="TOK", amount=50_000, order_id="1001")
    assert res.is_success
    assert res.status == PaymentStatus.SUCCESS
    assert res.reference_id == "987654321"
    assert res.amount == 50_000
    # SignData باید enc(Token) باشد
    sent = t.requests_log[0]["json"]
    assert sent["Token"] == "TOK"
    assert sent["SignData"]


def test_sadad_verify_duplicate_code_100():
    t = InMemoryTransport({_VERIFY_URL: {"ResCode": 100, "RetrivalRefNo": "1"}})
    res = _gw(t).verify(authority="TOK", amount=1000, order_id="1")
    assert res.is_success
    assert res.status == PaymentStatus.DUPLICATE


def test_sadad_verify_failed():
    t = InMemoryTransport({_VERIFY_URL: {"ResCode": -1, "Description": "ناموفق"}})
    res = _gw(t).verify(authority="TOK", amount=1000, order_id="1")
    assert not res.is_success
    assert res.error_code == "-1"


def test_sadad_verify_callback_rescode_not_ok_short_circuits():
    t = InMemoryTransport({})  # نباید فراخوانی شود
    res = _gw(t).verify(
        authority="TOK", amount=1000, order_id="1", extra={"res_code": "-1"}
    )
    assert not res.is_success
    assert len(t.requests_log) == 0


# ---------- رمزنگاری 3DES ----------


def test_sadad_sign_is_deterministic_and_base64():
    gw = _gw(InMemoryTransport({}))
    sig1 = gw._sign("12345;1001;50000")
    sig2 = gw._sign("12345;1001;50000")
    assert sig1 == sig2  # 3DES-ECB قطعی است
    base64.b64decode(sig1)  # Base64 معتبر


def test_sadad_invalid_key_length_raises():
    bad_key = base64.b64encode(b"tooshort").decode()  # ۸ بایت، نه ۱۶/۲۴
    gw = SadadGateway({**CONF, "terminal_key": bad_key}, transport=InMemoryTransport({}))
    with pytest.raises(GatewayConfigurationError):
        gw._sign("data")


def test_sadad_invalid_base64_key_raises():
    gw = SadadGateway(
        {**CONF, "terminal_key": "!!!not-base64!!!"}, transport=InMemoryTransport({})
    )
    with pytest.raises(GatewayConfigurationError):
        gw._sign("data")


# ---------- config / registry ----------


def test_sadad_missing_terminal_key_raises():
    conf = {k: v for k, v in CONF.items() if k != "terminal_key"}
    with pytest.raises(GatewayConfigurationError):
        SadadGateway(conf, transport=InMemoryTransport({}))


def test_sadad_importable_from_experimental():
    from django_iranian_payment.core.experimental.sadad import SadadGateway as S
    assert S is SadadGateway