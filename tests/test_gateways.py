"""
تست درگاه‌های REST با InMemoryTransport — بدون شبکه، بدون mock.
منطق کامل initiate/verify اجرا می‌شود. شامل تست‌های رگرسیون برای باگ‌های اصلاح‌شده.
"""

import pytest

from django_iranian_payment.core.base import InMemoryTransport
from django_iranian_payment.core.fee import FeeConfig, FeePayer
from django_iranian_payment.core.models import PaymentRequest, PaymentStatus
from django_iranian_payment.core.gateways.zarinpal import ZarinpalGateway
from django_iranian_payment.core.experimental import (
    IDPayGateway,
)  # از کار افتاده: خارج از registry عمومی
from django_iranian_payment.core.gateways.zibal import ZibalGateway
from django_iranian_payment.core.experimental import (
    PayIrGateway,
)  # از کار افتاده: خارج از registry عمومی

# ============== زرین‌پال ==============

ZP_REQ = "https://sandbox.zarinpal.com/pg/v4/payment/request.json"
ZP_VER = "https://sandbox.zarinpal.com/pg/v4/payment/verify.json"


def _zp(transport):
    return ZarinpalGateway(
        {"merchant_id": "test-id"}, sandbox=True, transport=transport
    )


def test_zarinpal_initiate_success():
    t = InMemoryTransport({ZP_REQ: {"data": {"authority": "A123"}, "errors": []}})
    gw = _zp(t)
    res = gw.initiate(
        PaymentRequest(amount=100_000, callback_url="https://s.com/cb", order_id="O1")
    )
    assert res.authority == "A123"
    assert "A123" in res.redirect_url
    assert res.amount_to_send == 100_000
    # مبلغ ارسالی به بانک واقعاً 100000 بود
    assert t.requests_log[0]["json"]["amount"] == 100_000


def test_zarinpal_initiate_with_fee_customer_pays():
    t = InMemoryTransport({ZP_REQ: {"data": {"authority": "A1"}, "errors": []}})
    gw = _zp(t)
    fee = FeeConfig(rate_bps=200, who_pays=FeePayer.CUSTOMER)  # ۲٪
    res = gw.initiate(
        PaymentRequest(amount=100_000, callback_url="x", order_id="O1", fee=fee)
    )
    # مشتری کارمزد می‌دهد: 102000 باید به بانک رفته باشد
    assert res.amount_to_send == 102_000
    assert res.fee == 2_000
    assert t.requests_log[0]["json"]["amount"] == 102_000


def test_zarinpal_verify_uses_amount_to_send_not_base():
    # تله‌ی اصلی: verify باید با amount_to_send (102000) صدا زده شود، نه 100000
    t = InMemoryTransport(
        {ZP_VER: {"data": {"code": 100, "ref_id": 555, "card_pan": "6037**1234"}}}
    )
    gw = _zp(t)
    res = gw.verify(authority="A1", amount=102_000, order_id="O1")
    assert res.is_success
    assert res.reference_id == "555"
    assert t.requests_log[0]["json"]["amount"] == 102_000  # همان مبلغ افزوده


def test_zarinpal_verify_duplicate():
    t = InMemoryTransport({ZP_VER: {"data": {"code": 101, "ref_id": 9}}})
    res = _zp(t).verify(authority="A1", amount=100_000, order_id="O1")
    assert res.status == PaymentStatus.DUPLICATE
    assert res.is_success


def test_zarinpal_error_code_from_list():
    # رگرسیون: errors به‌صورت list — نباید کل لیست را به‌عنوان code بگذارد
    from django_iranian_payment.core.exceptions import GatewayPaymentError

    t = InMemoryTransport({ZP_REQ: {"errors": [{"code": -9, "message": "merchant"}]}})
    gw = _zp(t)
    with pytest.raises(GatewayPaymentError) as exc:
        gw.initiate(PaymentRequest(amount=1000, callback_url="x", order_id="O1"))
    assert exc.value.code == "-9"  # از اولین آیتم لیست، نه str کل لیست


def test_zarinpal_error_code_from_dict():
    from django_iranian_payment.core.exceptions import GatewayPaymentError

    t = InMemoryTransport({ZP_REQ: {"errors": {"code": -11, "message": "x"}}})
    with pytest.raises(GatewayPaymentError) as exc:
        _zp(t).initiate(PaymentRequest(amount=1000, callback_url="x", order_id="O1"))
    assert exc.value.code == "-11"


# ============== آیدی‌پی ==============

IDP_REQ = "https://api.idpay.ir/v1.1/payment"
IDP_VER = "https://api.idpay.ir/v1.1/payment/verify"


def _idp(transport):
    return IDPayGateway({"api_key": "k"}, sandbox=True, transport=transport)


def test_idpay_verify_status_as_string():
    # رگرسیون: status رشته‌ای "100" نباید FAILED شود
    t = InMemoryTransport(
        {IDP_VER: {"status": "100", "track_id": 42, "amount": 100_000}}
    )
    res = _idp(t).verify(authority="id1", amount=100_000, order_id="O1")
    assert res.is_success
    assert res.reference_id == "42"


def test_idpay_verify_status_as_int():
    t = InMemoryTransport({IDP_VER: {"status": 100, "track_id": 7}})
    res = _idp(t).verify(authority="id1", amount=100_000, order_id="O1")
    assert res.is_success


def test_idpay_sandbox_header_set():
    t = InMemoryTransport({IDP_REQ: {"id": "X", "link": "https://idpay/X"}})
    _idp(t).initiate(PaymentRequest(amount=50_000, callback_url="cb", order_id="O1"))
    assert t.requests_log[0]["headers"]["X-SANDBOX"] == "1"


# ============== زیبال ==============

ZB_REQ = "https://gateway.zibal.ir/v1/request"
ZB_VER = "https://gateway.zibal.ir/v1/verify"


def test_zibal_full_flow():
    t = InMemoryTransport(
        {
            ZB_REQ: {"result": 100, "trackId": 12345},
            ZB_VER: {"result": 100, "refNumber": 999, "amount": 100_000},
        }
    )
    gw = ZibalGateway({"merchant": "zibal"}, transport=t)
    init = gw.initiate(PaymentRequest(amount=100_000, callback_url="cb", order_id="O1"))
    assert init.authority == "12345"
    ver = gw.verify(authority="12345", amount=100_000, order_id="O1")
    assert ver.is_success
    assert ver.reference_id == "999"


# ============== پی‌آی‌آر ==============

PR_REQ = "https://pay.ir/pg/send"
PR_VER = "https://pay.ir/pg/verify"


def test_payir_full_flow():
    t = InMemoryTransport(
        {
            PR_REQ: {"status": 1, "token": "TOK"},
            PR_VER: {"status": 1, "transId": 321, "amount": 100_000},
        }
    )
    gw = PayIrGateway({"api": "test"}, transport=t)
    init = gw.initiate(PaymentRequest(amount=100_000, callback_url="cb", order_id="O1"))
    assert init.authority == "TOK"
    ver = gw.verify(authority="TOK", amount=100_000, order_id="O1")
    assert ver.is_success
    assert ver.reference_id == "321"


# ============== اعتبارسنجی config ==============


def test_missing_required_config_raises():
    from django_iranian_payment.core.exceptions import GatewayConfigurationError

    with pytest.raises(GatewayConfigurationError):
        ZarinpalGateway({}, transport=InMemoryTransport({}))


# ============== رگرسیون: pay_ir از کار افتاده و خارج از registry ==============


def test_pay_ir_not_in_public_registry():
    # pay_ir از کار افتاده و به experimental منتقل شد؛ نباید با get_gateway_class در دسترس باشد
    from django_iranian_payment.core.gateways import available_slugs, get_gateway_class
    from django_iranian_payment.core.exceptions import GatewayConfigurationError

    assert "pay_ir" not in available_slugs()
    with pytest.raises(GatewayConfigurationError):
        get_gateway_class("pay_ir")


def test_pay_ir_still_importable_from_experimental():
    # کد سالم است و با import صریح هنوز قابل استفاده است
    from django_iranian_payment.core.experimental import PayIrGateway

    assert PayIrGateway.slug == "pay_ir"


# ============== رگرسیون: idpay از کار افتاده و خارج از registry ==============


def test_idpay_not_in_public_registry():
    # idpay به‌دلیل از کار افتادن سرویس به experimental منتقل شد
    from django_iranian_payment.core.gateways import available_slugs, get_gateway_class
    from django_iranian_payment.core.exceptions import GatewayConfigurationError

    assert "idpay" not in available_slugs()
    with pytest.raises(GatewayConfigurationError):
        get_gateway_class("idpay")


def test_idpay_still_importable_from_experimental():
    from django_iranian_payment.core.experimental import IDPayGateway

    assert IDPayGateway.slug == "idpay"


# ============== رگرسیون: ملت پس از تست واقعی به registry عمومی منتقل شد ==============


def test_mellat_in_public_registry():
    # ملت با تراکنش واقعی روی محیط عملیاتی تست شد و طبق قانون طلایی عمومی شد.
    # این تست مانع بازگشت ناآگاهانه به experimental می‌شود.
    from django_iranian_payment.core.gateways import available_slugs, get_gateway_class

    assert "mellat" in available_slugs()
    assert get_gateway_class("mellat").slug == "mellat"


def test_mellat_no_longer_in_experimental():
    # دیگر نباید از experimental قابل import باشد (به gateways منتقل شد)
    from django_iranian_payment.core import experimental

    assert not hasattr(experimental, "MellatGateway")


# ============== رگرسیون: سامان پس از تست واقعی به registry عمومی منتقل شد ==============


def test_saman_in_public_registry():
    # سامان با تراکنش واقعی روی ترمینال واقعی تست شد و طبق قانون طلایی عمومی شد.
    # این تست مانع بازگشت ناآگاهانه به experimental می‌شود.
    from django_iranian_payment.core.gateways import available_slugs, get_gateway_class

    assert "saman" in available_slugs()
    assert get_gateway_class("saman").slug == "saman"


def test_saman_no_longer_in_experimental():
    # دیگر نباید از experimental قابل import باشد (به gateways منتقل شد)
    from django_iranian_payment.core import experimental

    assert not hasattr(experimental, "SamanGateway")
