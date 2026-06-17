"""
تست درگاه سامان (SEP) با InMemoryTransport — بدون شبکه.
منطق کامل initiate/verify/reverse اجرا می‌شود.

اثبات می‌کند با پاسخ فرضیِ مطابق مستند درست رفتار می‌کنیم؛ اثبات شکل پاسخ
واقعی بانک نیست (آن نیاز به ترمینال واقعی دارد).
"""

import pytest

from django_iranian_payment.core.base import InMemoryTransport
from django_iranian_payment.core.fee import FeeConfig, FeePayer
from django_iranian_payment.core.models import PaymentRequest, PaymentStatus
from django_iranian_payment.core.experimental.saman import (
    SamanGateway,
    _TOKEN_URL,
    _VERIFY_URL,
    _REVERSE_URL,
)
from django_iranian_payment.core.exceptions import GatewayPaymentError

CONF = {"terminal_id": "2015"}


def _gw(transport, **extra_conf):
    return SamanGateway({**CONF, **extra_conf}, sandbox=True, transport=transport)


# ---------- initiate ----------


def test_saman_initiate_success():
    t = InMemoryTransport({_TOKEN_URL: {"status": 1, "token": "TOK123"}})
    res = _gw(t).initiate(
        PaymentRequest(amount=12_000, callback_url="https://s.com/cb", order_id="1qaz")
    )
    assert res.authority == "TOK123"
    assert res.amount_to_send == 12_000
    assert "TOK123" in res.redirect_url
    # مبلغ ریالی و ResNum درست رفت
    sent = t.requests_log[0]["json"]
    assert sent["Amount"] == 12_000
    assert sent["ResNum"] == "1qaz"
    assert sent["action"] == "token"
    assert sent["TerminalId"] == "2015"


def test_saman_initiate_with_fee():
    t = InMemoryTransport({_TOKEN_URL: {"status": 1, "token": "T"}})
    fee = FeeConfig(rate_bps=200, who_pays=FeePayer.CUSTOMER)  # ۲٪
    res = _gw(t).initiate(
        PaymentRequest(amount=100_000, callback_url="cb", order_id="1", fee=fee)
    )
    assert res.amount_to_send == 102_000
    assert res.fee == 2_000
    # کارمزد در Amount تجمیع شد (نه پارامتر Wage جدا)
    assert t.requests_log[0]["json"]["Amount"] == 102_000


def test_saman_initiate_includes_mobile_when_given():
    t = InMemoryTransport({_TOKEN_URL: {"status": 1, "token": "T"}})
    _gw(t).initiate(
        PaymentRequest(
            amount=1000, callback_url="cb", order_id="1", mobile="9120000000"
        )
    )
    assert t.requests_log[0]["json"]["CellNumber"] == "9120000000"


def test_saman_initiate_rejected():
    t = InMemoryTransport(
        {_TOKEN_URL: {"status": -1, "errorCode": "5", "errorDesc": "نامعتبر"}}
    )
    with pytest.raises(GatewayPaymentError) as exc:
        _gw(t).initiate(PaymentRequest(amount=1000, callback_url="cb", order_id="1"))
    assert exc.value.code == "5"


def test_saman_initiate_neo_pg_reads_ipg_url_header():
    # neo-pg: آدرس مرحله‌ی بعد از هدر X-IPG-Url خوانده می‌شود
    t = InMemoryTransport(
        {_TOKEN_URL: {"status": 1, "token": "TOK"}},
        response_headers={_TOKEN_URL: {"X-IPG-Url": "https://neo-pg.sep.ir/transaction/init"}},
    )
    res = _gw(t).initiate(
        PaymentRequest(amount=1000, callback_url="cb", order_id="1")
    )
    assert res.raw["ipg_url"] == "https://neo-pg.sep.ir/transaction/init"
    assert "neo-pg.sep.ir" in res.redirect_url


# ---------- verify ----------


def _verify_ok_response(amount=12_000):
    return {
        _VERIFY_URL: {
            "TransactionDetail": {
                "RRN": "14226761817",
                "RefNum": "REF50",
                "MaskedPan": "621986****8080",
                "OrginalAmount": amount,
                "AffectiveAmount": amount,
            },
            "ResultCode": 0,
            "ResultDescription": "موفق",
            "Success": True,
        }
    }


def test_saman_verify_success():
    t = InMemoryTransport(_verify_ok_response(amount=12_000))
    res = _gw(t).verify(
        authority="TOK",
        amount=12_000,
        order_id="1qaz",
        extra={"ref_num": "REF50", "state": "OK"},
    )
    assert res.is_success
    assert res.status == PaymentStatus.SUCCESS
    assert res.reference_id == "14226761817"
    assert res.card_number == "621986****8080"
    # verify با RefNum و TerminalNumber صحیح رفت
    sent = t.requests_log[0]["json"]
    assert sent["RefNum"] == "REF50"
    assert sent["TerminalNumber"] == 2015


def test_saman_verify_duplicate_resultcode_2():
    resp = _verify_ok_response()
    resp[_VERIFY_URL]["ResultCode"] = 2  # درخواست تکراری
    t = InMemoryTransport(resp)
    res = _gw(t).verify(
        authority="TOK", amount=12_000, order_id="1", extra={"ref_num": "REF50"}
    )
    assert res.is_success
    assert res.status == PaymentStatus.DUPLICATE


def test_saman_verify_amount_mismatch_is_failed():
    # مبلغ تأییدشده با مبلغ ارسالی فرق دارد → باید FAILED شود (نکته ۲ مستند)
    t = InMemoryTransport(_verify_ok_response(amount=5_000))
    res = _gw(t).verify(
        authority="TOK", amount=12_000, order_id="1", extra={"ref_num": "REF50"}
    )
    assert not res.is_success
    assert res.error_code == "amount_mismatch"


def test_saman_verify_failed_when_success_false():
    t = InMemoryTransport(
        {_VERIFY_URL: {"ResultCode": -2, "ResultDescription": "یافت نشد", "Success": False}}
    )
    res = _gw(t).verify(
        authority="TOK", amount=1000, order_id="1", extra={"ref_num": "R"}
    )
    assert not res.is_success
    assert res.error_code == "-2"


def test_saman_verify_state_not_ok_short_circuits():
    # اگر State در callback OK نبود، اصلاً verify زده نمی‌شود
    t = InMemoryTransport({})  # هیچ پاسخی لازم نیست
    res = _gw(t).verify(
        authority="TOK",
        amount=1000,
        order_id="1",
        extra={"ref_num": "R", "state": "CanceledByUser"},
    )
    assert not res.is_success
    assert res.error_code == "CanceledByUser"
    assert len(t.requests_log) == 0  # هیچ فراخوانی شبکه‌ای نشد


def test_saman_verify_missing_ref_num_raises():
    t = InMemoryTransport(_verify_ok_response())
    with pytest.raises(GatewayPaymentError) as exc:
        _gw(t).verify(authority="TOK", amount=1000, order_id="1")  # بدون extra
    assert exc.value.code == "missing_ref_num"


# ---------- reverse ----------


def test_saman_reverse_success():
    t = InMemoryTransport(
        {
            _REVERSE_URL: {
                "TransactionDetail": {"RRN": "142", "RefNum": "REF50"},
                "ResultCode": 0,
                "Success": True,
            }
        }
    )
    res = _gw(t).reverse(ref_num="REF50")
    assert res.status == PaymentStatus.CANCELLED
    assert t.requests_log[0]["json"]["RefNum"] == "REF50"


def test_saman_reverse_failed():
    t = InMemoryTransport(
        {_REVERSE_URL: {"ResultCode": -105, "ResultDescription": "ترمینال یافت نشد", "Success": False}}
    )
    res = _gw(t).reverse(ref_num="REF50")
    assert not res.is_success
    assert res.error_code == "-105"


# ---------- registry: نباید عمومی باشد (قانون طلایی) ----------


def test_saman_importable_from_experimental():
    from django_iranian_payment.core.experimental.saman import SamanGateway as S
    assert S is SamanGateway