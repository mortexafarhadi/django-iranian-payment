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
def test_callback_gateway_down_redirects_pending_not_500(client, monkeypatch):
    # رگرسیون: اگر درگاه هنگام verify بی‌پاسخ/۵۰۰ دهد، callback نباید ۵۰۰ بدهد یا
    # رکورد را گم کند. باید pending برگرداند و رکورد RETURN_FROM_BANK بماند تا
    # reverify_pending بعداً تمامش کند.
    _make_redirected_payment()

    from django_iranian_payment.core.base import RequestsTransport
    from django_iranian_payment.core.exceptions import GatewayConnectionError

    def boom(self, url, *, json=None, data=None, headers=None, timeout=15):
        raise GatewayConnectionError("درگاه بی‌پاسخ")

    monkeypatch.setattr(RequestsTransport, "post", boom)

    resp = client.get("/payment/callback/zarinpal/", {"Authority": "AUTH1"})
    assert resp.status_code == 302
    assert "payment_status=pending" in resp.url

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


# ─────────────────────────────────────────────────────────────
#  تست پیدا کردن رکورد در callback برای همه‌ی درگاه‌ها (_locate_payment)
#  رگرسیون باگ: قبلاً _extract_authority برای nextpay/sadad/saman/digipay
#  رکورد را پیدا نمی‌کرد و callback آن‌ها در حالت پکیج ۴۰۴ می‌داد.
# ─────────────────────────────────────────────────────────────

from django.test import RequestFactory  # noqa: E402

from django_iranian_payment.contrib.django.views import (  # noqa: E402
    _locate_payment,
    _extract_extra,
)


def _mk_payment(slug, *, order_id, authority):
    return Payment.objects.create(
        gateway_slug=slug,
        order_id=order_id,
        authority=authority,
        amount=1000,
        amount_sent=1000,
        callback_url="https://shop.com/result",
        status=PaymentStatus.REDIRECT_TO_BANK,
    )


@pytest.mark.django_db
def test_locate_zarinpal_by_authority():
    rf = RequestFactory()
    p = _mk_payment("zarinpal", order_id="10", authority="AUTHZP")
    req = rf.get("/cb/", {"Authority": "AUTHZP", "Status": "OK"})
    assert _locate_payment(req, "zarinpal").pk == p.pk


@pytest.mark.django_db
def test_locate_mellat_by_refid_authority():
    rf = RequestFactory()
    p = _mk_payment("mellat", order_id="20", authority="REF123")
    req = rf.post("/cb/", {"RefId": "REF123", "ResCode": "0", "SaleOrderId": "20"})
    assert _locate_payment(req, "mellat").pk == p.pk
    extra = _extract_extra(req, "mellat")
    assert extra["res_code"] == "0"
    assert extra["sale_order_id"] == "20"


@pytest.mark.django_db
def test_locate_nextpay_by_trans_id():
    rf = RequestFactory()
    p = _mk_payment("nextpay", order_id="30", authority="TRANS9")
    req = rf.get("/cb/", {"trans_id": "TRANS9", "order_id": "30"})
    assert _locate_payment(req, "nextpay").pk == p.pk


@pytest.mark.django_db
def test_locate_sadad_by_capital_token():
    rf = RequestFactory()
    p = _mk_payment("sadad", order_id="40", authority="TOK40")
    # سداد فیلد را با حرف بزرگ Token می‌فرستد (POST)
    req = rf.post("/cb/", {"Token": "TOK40", "ResCode": "0"})
    assert _locate_payment(req, "sadad").pk == p.pk


@pytest.mark.django_db
def test_locate_saman_by_order_id_resnum():
    # سامان توکن را در callback برنمی‌گرداند → باید با ResNum(==order_id) پیدا شود
    rf = RequestFactory()
    p = _mk_payment("saman", order_id="50", authority="SAMTOKEN")
    req = rf.post("/cb/", {"ResNum": "50", "RefNum": "RN50", "State": "OK"})
    found = _locate_payment(req, "saman")
    assert found.pk == p.pk
    extra = _extract_extra(req, "saman")
    assert extra["ref_num"] == "RN50"
    assert extra["state"] == "OK"


@pytest.mark.django_db
def test_locate_digipay_by_order_id_provider():
    # دیجی‌پی ticket را برنمی‌گرداند → باید با providerId(==order_id) پیدا شود
    rf = RequestFactory()
    p = _mk_payment("digipay", order_id="60", authority="TICKET60")
    req = rf.get("/cb/", {"providerId": "60", "trackingCode": "TC60", "result": "0"})
    found = _locate_payment(req, "digipay")
    assert found.pk == p.pk
    extra = _extract_extra(req, "digipay")
    assert extra["tracking_code"] == "TC60"


@pytest.mark.django_db
def test_locate_irankish_by_token():
    rf = RequestFactory()
    p = _mk_payment("irankish", order_id="70", authority="IKTOKEN")
    req = rf.post(
        "/cb/", {"token": "IKTOKEN", "referenceId": "RID70", "resultCode": "true"}
    )
    assert _locate_payment(req, "irankish").pk == p.pk
    extra = _extract_extra(req, "irankish")
    assert extra["reference_id"] == "RID70"


@pytest.mark.django_db
def test_locate_returns_none_when_no_match():
    rf = RequestFactory()
    req = rf.get("/cb/", {"Authority": "GHOST"})
    assert _locate_payment(req, "zarinpal") is None


@pytest.mark.django_db
def test_unknown_gateway_falls_back_to_generic_authority():
    rf = RequestFactory()
    p = _mk_payment("somecustom", order_id="80", authority="CUSTOMAUTH")
    req = rf.get("/cb/", {"Authority": "CUSTOMAUTH"})
    assert _locate_payment(req, "somecustom").pk == p.pk
    assert _extract_extra(req, "somecustom") is None
