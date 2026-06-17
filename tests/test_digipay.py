"""
تست درگاه دیجی‌پی (تجربی) با InMemoryTransport — بدون شبکه، بدون mock.
منطق کامل OAuth + initiate + verify اجرا می‌شود.

⚠️ این تست‌ها فقط ثابت می‌کنند منطق ما با پاسخ فرضیِ مطابق مستند درست رفتار می‌کند؛
اثبات نمی‌کنند شکل پاسخ واقعی دیجی‌پی همان است. آن نیاز به تست sandbox واقعی دارد.
"""

import pytest

from django_iranian_payment.core.base import InMemoryTransport
from django_iranian_payment.core.fee import FeeConfig, FeePayer
from django_iranian_payment.core.models import PaymentRequest, PaymentStatus
from django_iranian_payment.core.experimental.digipay import DigipayGateway

_BASE = "https://uat.mydigipay.info/digipay/api"
TOKEN = f"{_BASE}/oauth/token"
TICKET = f"{_BASE}/tickets/business?type=11"
VERIFY = f"{_BASE}/purchases/verify?type=11"

_CFG = {
    "username": "u",
    "password": "p",
    "client_id": "cid",
    "client_secret": "sec",
    "provider_id": "PRV",
}


def _gw(transport):
    return DigipayGateway(_CFG, sandbox=True, transport=transport)


# ---------- initiate ----------


def test_digipay_initiate_success():
    t = InMemoryTransport(
        {
            TOKEN: {"access_token": "AT", "token_type": "bearer"},
            TICKET: {
                "result": {"status": 0, "title": "SUCCESS", "message": "ok"},
                "ticket": "TK1",
                "redirectUrl": "https://uatweb.mydigipay.info/web-pay/tgs/TK1",
            },
        }
    )
    gw = _gw(t)
    res = gw.initiate(
        PaymentRequest(amount=100_000, callback_url="https://s.com/cb", order_id="ORD1")
    )
    assert res.authority == "TK1"
    assert "TK1" in res.redirect_url
    assert res.amount_to_send == 100_000
    # توکن اول با Basic auth گرفته شد، سپس تیکت با Bearer ساخته شد
    log = t.requests_log
    assert log[0]["url"] == TOKEN
    assert log[0]["data"]["grant_type"] == "password"
    assert log[0]["headers"]["Authorization"].startswith("Basic ")
    assert log[1]["headers"]["Authorization"] == "Bearer AT"
    assert log[1]["json"]["amount"] == 100_000
    assert log[1]["json"]["providerId"] == "ORD1"


def test_digipay_initiate_with_fee_customer_pays():
    t = InMemoryTransport(
        {
            TOKEN: {"access_token": "AT"},
            TICKET: {"result": {"status": 0}, "ticket": "TK", "redirectUrl": "u/TK"},
        }
    )
    gw = _gw(t)
    fee = FeeConfig(rate_bps=200, who_pays=FeePayer.CUSTOMER)  # ۲٪
    res = gw.initiate(
        PaymentRequest(amount=100_000, callback_url="x", order_id="O", fee=fee)
    )
    assert res.amount_to_send == 102_000
    assert res.fee == 2_000
    # مبلغ با کارمزد به تیکت رفت
    assert t.requests_log[1]["json"]["amount"] == 102_000


def test_digipay_initiate_includes_mobile_when_given():
    t = InMemoryTransport(
        {
            TOKEN: {"access_token": "AT"},
            TICKET: {"result": {"status": 0}, "ticket": "TK", "redirectUrl": "u/TK"},
        }
    )
    _gw(t).initiate(
        PaymentRequest(
            amount=10_000, callback_url="x", order_id="O", mobile="09120000000"
        )
    )
    assert t.requests_log[1]["json"]["cellNumber"] == "09120000000"


def test_digipay_initiate_rejected_when_status_not_zero():
    from django_iranian_payment.core.exceptions import GatewayPaymentError

    t = InMemoryTransport(
        {
            TOKEN: {"access_token": "AT"},
            TICKET: {"result": {"status": 9005, "message": "not payable"}},
        }
    )
    with pytest.raises(GatewayPaymentError) as exc:
        _gw(t).initiate(PaymentRequest(amount=1000, callback_url="x", order_id="O"))
    assert exc.value.code == "9005"


def test_digipay_initiate_auth_failure_when_no_token():
    from django_iranian_payment.core.exceptions import GatewayPaymentError

    t = InMemoryTransport({TOKEN: {"error": "invalid_grant"}})
    with pytest.raises(GatewayPaymentError) as exc:
        _gw(t).initiate(PaymentRequest(amount=1000, callback_url="x", order_id="O"))
    assert exc.value.code == "auth_failed"


def test_digipay_initiate_ok_but_missing_ticket():
    from django_iranian_payment.core.exceptions import GatewayPaymentError

    t = InMemoryTransport(
        {
            TOKEN: {"access_token": "AT"},
            TICKET: {"result": {"status": 0}},  # بدون ticket/redirectUrl
        }
    )
    with pytest.raises(GatewayPaymentError) as exc:
        _gw(t).initiate(PaymentRequest(amount=1000, callback_url="x", order_id="O"))
    assert exc.value.code == "missing_ticket"


# ---------- verify ----------


def test_digipay_verify_success():
    t = InMemoryTransport(
        {
            TOKEN: {"access_token": "AT"},
            VERIFY: {"result": {"status": 0, "title": "SUCCESS"}, "rrn": "RRN9"},
        }
    )
    res = _gw(t).verify(
        authority="TK1",
        amount=100_000,
        order_id="ORD1",
        extra={"tracking_code": "TC123"},
    )
    assert res.is_success
    assert res.status == PaymentStatus.SUCCESS
    assert res.reference_id == "RRN9"
    # trackingCode و providerId درست به verify رفتند
    assert t.requests_log[1]["json"]["trackingCode"] == "TC123"
    assert t.requests_log[1]["json"]["providerId"] == "ORD1"


def test_digipay_verify_failed_status_not_zero():
    t = InMemoryTransport(
        {
            TOKEN: {"access_token": "AT"},
            VERIFY: {
                "result": {"status": 9007, "message": "خرید با موفقیت انجام نشده"}
            },
        }
    )
    res = _gw(t).verify(
        authority="TK", amount=1000, order_id="O", extra={"tracking_code": "TC"}
    )
    assert not res.is_success
    assert res.status == PaymentStatus.FAILED
    assert res.error_code == "9007"


def test_digipay_verify_missing_tracking_code_raises():
    from django_iranian_payment.core.exceptions import GatewayPaymentError

    t = InMemoryTransport({TOKEN: {"access_token": "AT"}})
    with pytest.raises(GatewayPaymentError) as exc:
        _gw(t).verify(authority="TK", amount=1000, order_id="O")  # بدون extra
    assert exc.value.code == "missing_tracking_code"


def test_digipay_verify_callback_failure_short_circuits():
    # اگر نتیجه‌ی پرداخت در callback موفق نبود، اصلاً verify نباید زده شود
    t = InMemoryTransport({TOKEN: {"access_token": "AT"}})
    res = _gw(t).verify(
        authority="TK",
        amount=1000,
        order_id="O",
        extra={"tracking_code": "TC", "result": "FAILURE"},
    )
    assert not res.is_success
    assert res.status == PaymentStatus.FAILED
    # هیچ درخواستی به سرور نرفت (نه توکن، نه verify)
    assert len(t.requests_log) == 0


def test_digipay_result_status_accepts_string():
    # رگرسیون: status رشته‌ای "0" نباید FAILED شود
    t = InMemoryTransport(
        {
            TOKEN: {"access_token": "AT"},
            VERIFY: {"result": {"status": "0", "title": "SUCCESS"}, "rrn": "R1"},
        }
    )
    res = _gw(t).verify(
        authority="TK", amount=1000, order_id="O", extra={"tracking_code": "TC"}
    )
    assert res.is_success


# ---------- config ----------


def test_digipay_missing_config_raises():
    from django_iranian_payment.core.exceptions import GatewayConfigurationError

    with pytest.raises(GatewayConfigurationError):
        DigipayGateway({"username": "u"}, transport=InMemoryTransport({}))


# ---------- خارج از registry عمومی ----------


def test_digipay_importable_from_experimental():
    from django_iranian_payment.core.experimental.digipay import DigipayGateway

    assert DigipayGateway.slug == "digipay"


def test_digipay_not_in_public_registry():
    from django_iranian_payment.core.gateways import available_slugs

    assert "digipay" not in available_slugs()
