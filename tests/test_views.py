"""
تست view ها با Django TestClient — جریان کامل HTTP بانک→callback→redirect.

برای شبیه‌سازی پاسخ بانک بدون شبکه، RequestsTransport.post را monkeypatch می‌کنیم.
این یعنی کل زنجیره (view → service → gateway → transport) واقعی اجرا می‌شود،
فقط خود socket شبیه‌سازی شده.
"""

import pytest
from django.test import Client

from django_iranian_payment.core.base import InMemoryTransport
from django_iranian_payment.contrib.django import services
from django_iranian_payment.contrib.django.models import Payment, PaymentStatus

ZP_REQ = "https://sandbox.zarinpal.com/pg/v4/payment/request.json"
ZP_VER = "https://sandbox.zarinpal.com/pg/v4/payment/verify.json"


def _make_redirected_payment():
    """یک رکورد در حالت REDIRECT_TO_BANK با authority می‌سازد."""
    t = InMemoryTransport({ZP_REQ: {"data": {"authority": "AUTH1"}, "errors": []}})
    payment, _ = services.start_payment(
        "zarinpal",
        amount=100_000,
        callback_url="https://shop.com/order/55/result",
        order_id="55",
        transport=t,
    )
    return payment


@pytest.fixture
def patch_verify_transport(monkeypatch):
    """RequestsTransport.post را با یک پاسخ تستی جایگزین می‌کند."""

    def _patch(response):
        from django_iranian_payment.core.base import RequestsTransport

        def fake_post(self, url, *, json=None, data=None, headers=None, timeout=15):
            return response

        monkeypatch.setattr(RequestsTransport, "post", fake_post)

    return _patch


@pytest.mark.django_db
def test_callback_success_redirects_to_order(client, patch_verify_transport):
    _make_redirected_payment()
    patch_verify_transport(
        {"data": {"code": 100, "ref_id": 8899, "card_pan": "6037**1"}}
    )

    resp = client.get(
        "/payment/callback/zarinpal/", {"Authority": "AUTH1", "Status": "OK"}
    )

    assert resp.status_code == 302
    assert "payment_status=success" in resp.url
    assert "order_id=55" in resp.url
    assert resp.url.startswith("https://shop.com/order/55/result")

    payment = Payment.objects.get(authority="AUTH1")
    assert payment.status == PaymentStatus.COMPLETE
    assert payment.reference_id == "8899"


@pytest.mark.django_db
def test_callback_failed_redirects_with_failed_status(client, patch_verify_transport):
    _make_redirected_payment()
    patch_verify_transport({"data": {"code": -51}, "errors": "rejected"})

    resp = client.get(
        "/payment/callback/zarinpal/", {"Authority": "AUTH1", "Status": "NOK"}
    )

    assert resp.status_code == 302
    assert "payment_status=failed" in resp.url

    payment = Payment.objects.get(authority="AUTH1")
    assert payment.status == PaymentStatus.RETURN_FROM_BANK


@pytest.mark.django_db
def test_callback_missing_authority_404(client):
    resp = client.get("/payment/callback/zarinpal/")  # بدون Authority
    assert resp.status_code == 404


@pytest.mark.django_db
def test_callback_unknown_authority_404(client, patch_verify_transport):
    patch_verify_transport({"data": {"code": 100}})
    resp = client.get("/payment/callback/zarinpal/", {"Authority": "GHOST"})
    assert resp.status_code == 404


@pytest.mark.django_db
def test_callback_appends_param_with_existing_query(client, patch_verify_transport):
    # callback_url که خودش ? دارد → باید با & اضافه شود نه ?
    t = InMemoryTransport({ZP_REQ: {"data": {"authority": "AUTH2"}, "errors": []}})
    services.start_payment(
        "zarinpal",
        amount=1000,
        callback_url="https://shop.com/result?ref=abc",
        order_id="77",
        transport=t,
    )
    patch_verify_transport({"data": {"code": 100, "ref_id": 1}})

    resp = client.get("/payment/callback/zarinpal/", {"Authority": "AUTH2"})
    assert resp.status_code == 302
    assert "?ref=abc&payment_status=success" in resp.url


@pytest.mark.django_db
def test_go_to_gateway_redirects(client):
    payment = _make_redirected_payment()
    resp = client.get(f"/payment/go/{payment.pk}/")
    assert resp.status_code == 302
    assert "AUTH1" in resp.url  # redirect_url حاوی authority است


@pytest.mark.django_db
def test_go_to_gateway_missing_redirect_404(client):
    # رکوردی بدون redirect_url
    payment = Payment.objects.create(
        gateway_slug="zarinpal",
        order_id="1",
        amount=1000,
        callback_url="https://x.com",
        status=PaymentStatus.WAITING,
    )
    resp = client.get(f"/payment/go/{payment.pk}/")
    assert resp.status_code == 404
