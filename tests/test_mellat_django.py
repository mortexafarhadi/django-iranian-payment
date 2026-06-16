"""
تست جریان ملت در لایه‌ی Django: start → verify با sale_reference_id (extra).
چون ملت SOAP است، از InMemoryTransport با soap_call استفاده می‌شود و config
ملت را به‌صورت موقت به settings اضافه می‌کنیم.
"""

import pytest
from django.conf import settings

from django_iranian_payment.core.base import InMemoryTransport
from django_iranian_payment.contrib.django import services
from django_iranian_payment.contrib.django.models import Payment, PaymentStatus


@pytest.fixture
def mellat_config():
    """config ملت را موقتاً به IRANIAN_PAYMENT اضافه می‌کند."""
    conf = settings.IRANIAN_PAYMENT
    original = conf.get("gateways", {}).copy()
    conf["gateways"]["mellat"] = {
        "terminal_id": "1234",
        "username": "u",
        "password": "p",
    }
    yield
    conf["gateways"] = original


@pytest.mark.django_db
def test_mellat_start_creates_record(mellat_config):
    t = InMemoryTransport({"bpPayRequest": "0,REF99"})
    payment, url = services.start_payment(
        "mellat",
        amount=10_000,
        callback_url="https://shop.com/cb",
        order_id="200",
        transport=t,
    )
    assert payment.status == PaymentStatus.REDIRECT_TO_BANK
    assert payment.authority == "REF99"
    assert payment.amount_sent == 10_000
    assert "REF99" in url


@pytest.mark.django_db
def test_mellat_verify_with_extra_completes(mellat_config):
    # ساخت رکورد
    t_req = InMemoryTransport({"bpPayRequest": "0,REF1"})
    services.start_payment(
        "mellat", amount=10_000, callback_url="cb", order_id="200", transport=t_req
    )
    # verify با sale_reference_id (که در callback از بانک می‌آید)
    t_ver = InMemoryTransport({"bpVerifySettleRequest": "0"})
    payment = services.verify_payment(
        "mellat",
        "REF1",
        transport=t_ver,
        extra={"sale_reference_id": "127926981246", "sale_order_id": "200"},
    )
    assert payment.is_success
    assert payment.status == PaymentStatus.COMPLETE
    assert payment.reference_id == "127926981246"
    # مبلغ amount_sent به verify رفت (هرچند ملت در verify مبلغ نمی‌فرستد،
    # amount در PaymentResult ثبت می‌شود)
    assert t_ver.requests_log[0]["params"]["saleReferenceId"] == 127926981246


@pytest.mark.django_db
def test_mellat_verify_without_extra_stays_returned(mellat_config):
    # بدون sale_reference_id، ملت GatewayPaymentError می‌دهد که در verify_payment
    # نباید کرش کند بلکه باید مدیریت شود؛ اینجا بررسی می‌کنیم که خطا بالا می‌آید
    t_req = InMemoryTransport({"bpPayRequest": "0,REF1"})
    services.start_payment(
        "mellat", amount=10_000, callback_url="cb", order_id="200", transport=t_req
    )
    from django_iranian_payment.core.exceptions import GatewayPaymentError

    t_ver = InMemoryTransport({"bpVerifySettleRequest": "0"})
    with pytest.raises(GatewayPaymentError):
        services.verify_payment("mellat", "REF1", transport=t_ver)  # بدون extra