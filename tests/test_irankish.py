"""
تست درگاه ایران کیش (irankish) با InMemoryTransport — بدون شبکه.

دو دسته تست:
  - منطق initiate/verify: با monkeypatch کردن envelope تا رمزنگاری واقعی لازم نباشد.
  - رمزنگاری واقعی: یک تست جدا با کلید RSA تستی که اثبات می‌کند envelope
    ساختاراً معتبر تولید می‌شود (مسیر crypto نمی‌شکند).

اثبات می‌کند با پاسخ فرضیِ مطابق کد مرجع درست رفتار می‌کنیم؛ اثبات شکل پاسخ
واقعی بانک نیست (آن نیاز به ترمینال واقعی دارد).
"""

import pytest

from django_iranian_payment.core.base import InMemoryTransport
from django_iranian_payment.core.fee import FeeConfig, FeePayer
from django_iranian_payment.core.models import PaymentRequest, PaymentStatus
from django_iranian_payment.core.experimental.irankish import (
    IrankishGateway,
    _TOKEN_URL,
    _CONFIRM_URL,
)
from django_iranian_payment.core.exceptions import (
    GatewayPaymentError,
    GatewayConfigurationError,
)

CONF = {
    "terminal_id": "12345678",
    "acceptor_id": "1122334455",
    "pass_phrase": "ABCDEF0123456789ABCDEF0123456789",  # hex معتبر طول زوج
    "public_key": "dummy-key-for-tests",  # _validate_config فقط non-empty می‌خواهد
}

_FAKE_ENVELOPE = {"iv": "00" * 16, "data": "11" * 256}


def _gw(transport, monkeypatch=None, **extra_conf):
    gw = IrankishGateway({**CONF, **extra_conf}, sandbox=True, transport=transport)
    if monkeypatch is not None:
        # رمزنگاری واقعی را دور می‌زنیم تا به کلید PEM واقعی نیاز نباشد
        monkeypatch.setattr(gw, "_build_auth_envelope", lambda amount: _FAKE_ENVELOPE)
    return gw


# ---------- initiate ----------


def test_irankish_initiate_success(monkeypatch):
    t = InMemoryTransport(
        {_TOKEN_URL: {"responseCode": "00", "result": {"token": "TOK123"}}}
    )
    res = _gw(t, monkeypatch).initiate(
        PaymentRequest(amount=10_000, callback_url="https://s.com/cb", order_id="INV1")
    )
    assert res.authority == "TOK123"
    assert res.amount_to_send == 10_000
    assert "TOK123" in res.redirect_url
    sent = t.requests_log[0]["json"]
    assert sent["request"]["amount"] == 10_000
    assert sent["request"]["requestId"] == "INV1"
    assert sent["request"]["transactionType"] == "Purchase"
    assert sent["authenticationEnvelope"] == _FAKE_ENVELOPE


def test_irankish_initiate_with_fee(monkeypatch):
    t = InMemoryTransport(
        {_TOKEN_URL: {"responseCode": "00", "result": {"token": "T"}}}
    )
    fee = FeeConfig(rate_bps=200, who_pays=FeePayer.CUSTOMER)  # ۲٪
    res = _gw(t, monkeypatch).initiate(
        PaymentRequest(amount=100_000, callback_url="cb", order_id="1", fee=fee)
    )
    assert res.amount_to_send == 102_000
    assert res.fee == 2_000
    assert t.requests_log[0]["json"]["request"]["amount"] == 102_000


def test_irankish_initiate_rejected(monkeypatch):
    t = InMemoryTransport({_TOKEN_URL: {"responseCode": "99", "description": "خطا"}})
    with pytest.raises(GatewayPaymentError) as exc:
        _gw(t, monkeypatch).initiate(
            PaymentRequest(amount=1000, callback_url="cb", order_id="1")
        )
    assert exc.value.code == "99"


def test_irankish_initiate_ok_but_no_token(monkeypatch):
    t = InMemoryTransport({_TOKEN_URL: {"responseCode": "00", "result": {}}})
    with pytest.raises(GatewayPaymentError):
        _gw(t, monkeypatch).initiate(
            PaymentRequest(amount=1000, callback_url="cb", order_id="1")
        )


# ---------- verify ----------


def test_irankish_verify_success():
    t = InMemoryTransport(
        {
            _CONFIRM_URL: {
                "status": True,
                "result": {
                    "retrievalReferenceNumber": "987654",
                    "maskedPan": "6037****1234",
                },
            }
        }
    )
    res = _gw(t).verify(
        authority="TOK",
        amount=10_000,
        order_id="INV1",
        extra={"token": "TOK", "reference_id": "REF99", "result_code": "100"},
    )
    assert res.is_success
    assert res.reference_id == "987654"
    assert res.card_number == "6037****1234"
    sent = t.requests_log[0]["json"]
    assert sent["referenceId"] == "REF99"
    assert sent["token"] == "TOK"


def test_irankish_verify_failed_when_status_false():
    t = InMemoryTransport(
        {_CONFIRM_URL: {"status": False, "description": "ناموفق", "responseCode": "21"}}
    )
    res = _gw(t).verify(
        authority="TOK",
        amount=1000,
        order_id="1",
        extra={"reference_id": "REF", "result_code": "100"},
    )
    assert not res.is_success
    assert res.error_code == "21"


def test_irankish_verify_callback_result_code_not_100_short_circuits():
    t = InMemoryTransport({})  # هیچ فراخوانی نباید انجام شود
    res = _gw(t).verify(
        authority="TOK",
        amount=1000,
        order_id="1",
        extra={"reference_id": "REF", "result_code": "200"},
    )
    assert not res.is_success
    assert res.error_code == "200"
    assert len(t.requests_log) == 0


def test_irankish_verify_missing_reference_id_raises():
    t = InMemoryTransport({_CONFIRM_URL: {"status": True}})
    with pytest.raises(GatewayPaymentError) as exc:
        _gw(t).verify(authority="TOK", amount=1000, order_id="1")
    assert exc.value.code == "missing_reference_id"


# ---------- config ----------


def test_irankish_missing_public_key_raises():
    from django_iranian_payment.core.base import InMemoryTransport as T

    conf = {k: v for k, v in CONF.items() if k != "public_key"}
    with pytest.raises(GatewayConfigurationError):
        IrankishGateway(conf, transport=T({}))


# ---------- رمزنگاری واقعی (بدون monkeypatch) ----------


# کلید عمومی RSA تستی ثابت (X.509 PEM) — همان فرمتی که
# rsa.load_pkcs1_openssl_pem می‌خواند. ثابت است تا تست به هیچ کتابخانه‌ی
# تولید کلید (cryptography) وابسته نباشد و قطعی بماند.
_TEST_PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAw6URDvhf60F3TlcFBaDr
re5505KBo3HOwYeWM0kW3WL4+EfWXBMG41mxzfCCv7Tzbw0qUbV+dWUqM1My5dUX
Qc4p3fb1wPnddcCY4b/oXNSuE63uptVl5ozpk5hxQfa+bLQN8kbbrdwS95/GZYYE
nWS+kPJ6IMaztbdt/PuJakjx2HpphAO45zlrcPqTKaveZIobwtpO4KLRe3iCAbcj
OL03GQ11W1ROYs+Me2DuoCKp3lmoQk0YBX2pJGCxGAN9BC2KsUt30ox9XKYpcFUd
aV8Pl0NJJxo+fOgnNQMvUmf0hS4Nmw1fews/TAcW7TajiRgogiKE6nM04jgt7v2t
BQIDAQAB
-----END PUBLIC KEY-----
"""


def test_irankish_real_envelope_structure():
    """
    اثبات می‌کند مسیر رمزنگاری با یک کلید RSA واقعی، envelope ساختاراً معتبر
    تولید می‌کند: iv = ۳۲ کاراکتر hex، data غیرخالی hex.
    """
    pytest.importorskip("rsa")
    pytest.importorskip("Crypto")

    conf = {**CONF, "public_key": _TEST_PUBLIC_KEY_PEM}
    gw = IrankishGateway(conf, sandbox=True, transport=InMemoryTransport({}))
    env = gw._build_auth_envelope(10_000)
    assert len(env["iv"]) == 32  # ۱۶ بایت hex
    assert len(env["data"]) > 0
    # hex معتبر؟
    bytes.fromhex(env["iv"])
    bytes.fromhex(env["data"])


def test_irankish_invalid_passphrase_hex_raises():
    """pass_phrase غیرhex باید خطای واضح config بدهد، نه crash مبهم."""
    pytest.importorskip("rsa")
    conf = {**CONF, "public_key": _TEST_PUBLIC_KEY_PEM, "pass_phrase": "NOT-HEX-!!!"}
    gw = IrankishGateway(conf, transport=InMemoryTransport({}))
    with pytest.raises(GatewayConfigurationError):
        gw._build_auth_envelope(1000)


def test_irankish_importable_from_experimental():
    from django_iranian_payment.core.experimental.irankish import (
        IrankishGateway as G,
    )

    assert G is IrankishGateway
