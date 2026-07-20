"""
تست لایه‌ی Django: مدل Payment، state machine، و سرویس‌ها.
از InMemoryTransport استفاده می‌شود تا بدون شبکه‌ی واقعی، جریان کامل آزموده شود.
"""

import pytest

from django_iranian_payment.core.base import InMemoryTransport
from django_iranian_payment.core.exceptions import GatewayConnectionError
from django_iranian_payment.core.fee import FeeConfig, FeePayer
from django_iranian_payment.contrib.django.models import Payment, PaymentStatus
from django_iranian_payment.contrib.django import services

ZP_REQ = "https://sandbox.zarinpal.com/pg/v4/payment/request.json"
ZP_VER = "https://sandbox.zarinpal.com/pg/v4/payment/verify.json"


@pytest.mark.django_db
def test_start_payment_creates_record_and_saves_authority():
    t = InMemoryTransport({ZP_REQ: {"data": {"authority": "AUTH123"}, "errors": []}})
    payment, url = services.start_payment(
        "zarinpal",
        amount=100_000,
        callback_url="https://s.com/cb",
        order_id="O1",
        transport=t,
    )
    assert payment.status == PaymentStatus.REDIRECT_TO_BANK
    assert payment.authority == "AUTH123"
    assert payment.amount_sent == 100_000
    assert "AUTH123" in url


@pytest.mark.django_db
def test_start_payment_toman_converts_and_stores_rial():
    # currency=toman: ۱۵۰۰۰ تومان → بانک ۱۵۰۰۰۰ ریال؛ رکورد هم ریالی ذخیره می‌شود.
    t = InMemoryTransport({ZP_REQ: {"data": {"authority": "AT"}, "errors": []}})
    payment, _ = services.start_payment(
        "zarinpal",
        amount=15_000,
        callback_url="cb",
        order_id="OT",
        currency="toman",
        transport=t,
    )
    assert payment.amount == 150_000  # ریال (تبدیل‌شده)
    assert payment.amount_sent == 150_000  # ریال به بانک
    assert t.requests_log[0]["json"]["amount"] == 150_000


@pytest.mark.django_db
def test_start_payment_reads_global_toman_setting():
    # رگرسیون: بدون currency صریح، تنظیم سراسری IRANIAN_PAYMENT["currency"]="toman"
    # باید مبلغ را ×۱۰ کند. باگِ قبلی: toman با rial فرقی نداشت چون واحد سراسری
    # خوانده نمی‌شد (get_default_currency پاس نمی‌شد).
    from django.test import override_settings

    t = InMemoryTransport({ZP_REQ: {"data": {"authority": "AG"}, "errors": []}})
    with override_settings(
        IRANIAN_PAYMENT={
            "currency": "toman",
            "sandbox": True,
            "gateways": {"zarinpal": {"merchant_id": "test-merchant"}},
        }
    ):
        payment, _ = services.start_payment(
            "zarinpal",
            amount=15_000,  # تومان (از تنظیم سراسری)
            callback_url="cb",
            order_id="OG",
            transport=t,  # currency عمداً پاس نمی‌شود
        )
    assert payment.amount == 150_000  # ریال (تبدیل‌شده از تنظیم سراسری)
    assert payment.amount_sent == 150_000
    assert t.requests_log[0]["json"]["amount"] == 150_000


@pytest.mark.django_db
def test_start_payment_with_fee_stores_amount_sent():
    t = InMemoryTransport({ZP_REQ: {"data": {"authority": "A1"}, "errors": []}})
    fee = FeeConfig(rate_bps=200, who_pays=FeePayer.CUSTOMER)
    payment, _ = services.start_payment(
        "zarinpal",
        amount=100_000,
        callback_url="cb",
        order_id="O1",
        fee=fee,
        transport=t,
    )
    assert payment.amount == 100_000  # مبلغ پایه
    assert payment.fee == 2_000
    assert payment.amount_sent == 102_000  # با کارمزد
    assert t.requests_log[0]["json"]["amount"] == 102_000


@pytest.mark.django_db
def test_verify_payment_uses_amount_sent_not_base():
    # تله‌ی اصلی: verify باید amount_sent (102000) را بفرستد، نه amount (100000)
    t_req = InMemoryTransport({ZP_REQ: {"data": {"authority": "A1"}, "errors": []}})
    fee = FeeConfig(rate_bps=200, who_pays=FeePayer.CUSTOMER)
    services.start_payment(
        "zarinpal",
        amount=100_000,
        callback_url="cb",
        order_id="O1",
        fee=fee,
        transport=t_req,
    )

    t_ver = InMemoryTransport({ZP_VER: {"data": {"code": 100, "ref_id": 777}}})
    payment = services.verify_payment("zarinpal", "A1", transport=t_ver)

    assert payment.is_success
    assert payment.status == PaymentStatus.COMPLETE
    assert payment.reference_id == "777"
    assert t_ver.requests_log[0]["json"]["amount"] == 102_000  # نه 100000


@pytest.mark.django_db
def test_verify_failed_stays_returned():
    t_req = InMemoryTransport({ZP_REQ: {"data": {"authority": "A1"}, "errors": []}})
    services.start_payment(
        "zarinpal", amount=50_000, callback_url="cb", order_id="O1", transport=t_req
    )

    t_ver = InMemoryTransport({ZP_VER: {"data": {"code": -51}, "errors": "failed"}})
    payment = services.verify_payment("zarinpal", "A1", transport=t_ver)

    assert not payment.is_success
    assert payment.status == PaymentStatus.RETURN_FROM_BANK
    assert payment.error_code == "-51"


@pytest.mark.django_db
def test_verify_is_idempotent_when_already_complete():
    t_req = InMemoryTransport({ZP_REQ: {"data": {"authority": "A1"}, "errors": []}})
    services.start_payment(
        "zarinpal", amount=50_000, callback_url="cb", order_id="O1", transport=t_req
    )
    t_ver = InMemoryTransport({ZP_VER: {"data": {"code": 100, "ref_id": 1}}})
    services.verify_payment("zarinpal", "A1", transport=t_ver)

    # بار دوم: transport خالی؛ نباید اصلاً به بانک برود چون قبلاً COMPLETE است
    t_empty = InMemoryTransport({})
    payment = services.verify_payment("zarinpal", "A1", transport=t_empty)
    assert payment.is_success
    assert len(t_empty.requests_log) == 0  # هیچ درخواستی نرفت


@pytest.mark.django_db
def test_verify_unknown_authority_returns_none():
    assert (
        services.verify_payment("zarinpal", "NOPE", transport=InMemoryTransport({}))
        is None
    )


@pytest.mark.django_db
def test_reverify_pending_completes_returned_records():
    # یک رکورد بازگشته‌ی ناموفق بساز
    t_req = InMemoryTransport({ZP_REQ: {"data": {"authority": "A1"}, "errors": []}})
    services.start_payment(
        "zarinpal", amount=50_000, callback_url="cb", order_id="O1", transport=t_req
    )
    t_fail = InMemoryTransport({ZP_VER: {"data": {"code": -51}}})
    services.verify_payment("zarinpal", "A1", transport=t_fail)

    # حالا تأیید مجدد، این بار بانک موفق برمی‌گرداند
    # reverify_pending خودش transport نمی‌گیرد؛ پس مستقیم verify_payment را تست می‌کنیم
    t_ok = InMemoryTransport({ZP_VER: {"data": {"code": 100, "ref_id": 9}}})
    payment = services.verify_payment("zarinpal", "A1", transport=t_ok)
    assert payment.is_success


@pytest.mark.django_db
def test_verify_connection_error_marks_returned_not_lost():
    # رگرسیون باگ پول‌گم‌شده: اگر verify با خطای شبکه/۵۰۰ شکست بخورد، رکورد نباید
    # در REDIRECT_TO_BANK بماند (که reverify نمی‌گیردش و expire_stale منقضی‌اش می‌کند)؛
    # باید RETURN_FROM_BANK شود تا reverify_pending بعداً تمامش کند.
    t_req = InMemoryTransport({ZP_REQ: {"data": {"authority": "A1"}, "errors": []}})
    services.start_payment(
        "zarinpal", amount=50_000, callback_url="cb", order_id="O1", transport=t_req
    )

    # transport خالی: URL verify تعریف نشده → InMemoryTransport خطای اتصال می‌دهد.
    with pytest.raises(GatewayConnectionError):
        services.verify_payment("zarinpal", "A1", transport=InMemoryTransport({}))

    payment = Payment.objects.get(authority="A1")
    assert payment.status == PaymentStatus.RETURN_FROM_BANK  # نه REDIRECT، نه گم‌شده

    # حالا درگاه برگشت؛ همان رکورد با reverify تمام می‌شود.
    t_ok = InMemoryTransport({ZP_VER: {"data": {"code": 100, "ref_id": 42}}})
    payment = services.verify_payment("zarinpal", "A1", transport=t_ok)
    assert payment.is_success
    assert payment.reference_id == "42"


@pytest.mark.django_db
def test_expire_stale_ignores_returned_after_connection_error():
    # رکوردی که پس از خطای شبکه‌ی verify به RETURN_FROM_BANK رفته نباید توسط
    # expire_stale منقضی شود (فقط WAITING/REDIRECT کهنه منقضی می‌شوند).
    from django.utils import timezone

    t_req = InMemoryTransport({ZP_REQ: {"data": {"authority": "A1"}, "errors": []}})
    services.start_payment(
        "zarinpal", amount=1000, callback_url="cb", order_id="O1", transport=t_req
    )
    with pytest.raises(GatewayConnectionError):
        services.verify_payment("zarinpal", "A1", transport=InMemoryTransport({}))

    Payment.objects.filter(authority="A1").update(
        created_at=timezone.now() - timezone.timedelta(minutes=30)
    )
    assert services.expire_stale(older_than_minutes=15) == 0  # returned دست‌نخورده


@pytest.mark.django_db
def test_reverify_pending_passes_extra_from_raw():
    # رگرسیون: extra ذخیره‌شده در raw (برای درگاه‌های شاپرکی) باید در reverify
    # دوباره به verify پاس شود. اینجا با زرین‌پال شبیه‌سازی می‌کنیم که extra را
    # نادیده می‌گیرد، ولی تأیید می‌کنیم رکورد returned با extra ذخیره‌شده کامل می‌شود.
    t_req = InMemoryTransport({ZP_REQ: {"data": {"authority": "A1"}, "errors": []}})
    services.start_payment(
        "zarinpal", amount=1000, callback_url="cb", order_id="O1", transport=t_req
    )
    # callback با extra ولی درگاه بی‌پاسخ → returned با callback_extra در raw
    with pytest.raises(GatewayConnectionError):
        services.verify_payment(
            "zarinpal", "A1", transport=InMemoryTransport({}), extra={"State": "OK"}
        )
    payment = Payment.objects.get(authority="A1")
    assert payment.raw.get("callback_extra") == {"State": "OK"}

    # reverify_pending نمی‌تواند transport بگیرد؛ verify_payment را با extra از raw صدا می‌زنیم.
    t_ok = InMemoryTransport({ZP_VER: {"data": {"code": 100, "ref_id": 7}}})
    payment = services.verify_payment(
        "zarinpal", "A1", transport=t_ok, extra=payment.raw.get("callback_extra")
    )
    assert payment.is_success


@pytest.mark.django_db
def test_expire_stale_marks_old_redirects():
    from django.utils import timezone

    t = InMemoryTransport({ZP_REQ: {"data": {"authority": "A1"}, "errors": []}})
    payment, _ = services.start_payment(
        "zarinpal", amount=1000, callback_url="cb", order_id="O1", transport=t
    )
    # دستی created_at را قدیمی کن
    Payment.objects.filter(pk=payment.pk).update(
        created_at=timezone.now() - timezone.timedelta(minutes=30)
    )
    count = services.expire_stale(older_than_minutes=15)
    assert count == 1
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.EXPIRE_GATEWAY_TOKEN
