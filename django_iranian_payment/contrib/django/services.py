"""
لایه‌ی سرویس — هسته‌ی بدون state را به مدل Payment وصل می‌کند.

این همان جایی است که «کاربر درگیر مدیریت state نشود» واقعی می‌شود:
start_payment رکورد می‌سازد و authority را خودش ذخیره می‌کند؛
verify_payment با amount_sent درست (نه مبلغ پایه) تأیید می‌کند.
"""

from django.db import transaction

from ...core.django_integration import get_default_currency, get_gateway
from ...core.exceptions import GatewayConnectionError
from ...core.fee import FeeConfig
from ...core.models import PaymentRequest, PaymentStatus as CoreStatus
from .models import Payment, PaymentStatus


def start_payment(
    slug,
    *,
    amount,
    callback_url,
    order_id,
    description="",
    mobile="",
    email="",
    fee: FeeConfig = None,
    currency=None,
    timeout=15,
    transport=None,
):
    """
    یک پرداخت را شروع می‌کند: رکورد Payment می‌سازد، به بانک می‌رود،
    authority و amount_sent را ذخیره می‌کند، و redirect_url را برمی‌گرداند.

    currency واحد ورودی amount/fee است (rial یا toman). اگر None باشد از
    IRANIAN_PAYMENT["currency"] (پیش‌فرض rial) خوانده می‌شود. بانک همیشه ریال
    می‌گیرد؛ پکیج تبدیل را خودکار انجام می‌دهد و رکورد Payment مبالغ را به ریال
    (واحد بانک) ذخیره می‌کند — amount و amount_sent همیشه ریال‌اند.

    transport اختیاری است و فقط برای تست استفاده می‌شود (InMemoryTransport).
    خروجی: (payment_record, redirect_url)
    """
    gw = get_gateway(slug, timeout=timeout, transport=transport)

    if currency is None:
        currency = get_default_currency()

    req = PaymentRequest(
        amount=amount,
        callback_url=callback_url,
        order_id=order_id,
        description=description,
        mobile=mobile or None,
        email=email or None,
        fee=fee,
        currency=currency,
    )

    # مبلغ پایه به ریال (پس از تبدیل واحد) — رکورد همیشه ریالی ذخیره می‌شود.
    base_rial = req.resolve_amount().base_amount

    payment = Payment.objects.create(
        gateway_slug=slug,
        order_id=str(order_id),
        amount=base_rial,
        callback_url=callback_url,
        description=description,
        mobile=mobile or "",
        email=email or "",
        status=PaymentStatus.WAITING,
    )

    result = gw.initiate(req)

    raw = dict(result.raw or {})
    if result.redirect_method != "GET":
        raw["redirect_method"] = result.redirect_method
    if result.redirect_fields:
        raw["redirect_fields"] = result.redirect_fields

    payment.mark(
        PaymentStatus.REDIRECT_TO_BANK,
        authority=result.authority or "",
        redirect_url=result.redirect_url or "",
        amount_sent=result.amount_to_send,
        fee=result.fee,
        raw=raw,
    )
    return payment, result.redirect_url


def _find_payment(slug, authority):
    return (
        Payment.objects.filter(gateway_slug=slug, authority=authority)
        .order_by("-created_at")
        .first()
    )


def verify_payment(slug, authority, *, transport=None, extra=None):
    """
    یک پرداخت بازگشته از بانک را تأیید می‌کند. رکورد را از روی authority پیدا
    می‌کند، با amount_sent (نه مبلغ پایه) verify می‌زند، و حالت را به‌روز می‌کند.

    مهم (تله‌ی پول‌گم‌شده): پیش از تماس شبکه‌ای، رکورد به RETURN_FROM_BANK
    «پیش‌علامت» می‌خورد و extra در raw ذخیره می‌شود. اگر verify با خطای شبکه/۵۰۰
    شکست بخورد یا پروسه کرش کند، خطا بالا می‌رود ولی رکورد در RETURN_FROM_BANK
    می‌ماند تا reverify_pending بعداً تمامش کند — نه در REDIRECT_TO_BANK که هم
    reverify نمی‌گیردش و هم expire_stale اشتباه منقضی‌اش می‌کند. تماس شبکه‌ای
    بیرون از قفل DB انجام می‌شود (قفل روی HTTP نگه داشته نمی‌شود).

    transport اختیاری است و فقط برای تست استفاده می‌شود.
    خروجی: payment_record (با status نهایی) یا None اگر رکوردی نبود.
    درگاه در دسترس نبود: GatewayConnectionError raise می‌شود (رکورد returned مانده).
    """
    # مرحله ۱: قفل + idempotency + پیش‌علامت (اتمیک، بدون تماس شبکه‌ای داخل قفل).
    with transaction.atomic():
        payment = (
            Payment.objects.select_for_update()
            .filter(gateway_slug=slug, authority=authority)
            .order_by("-created_at")
            .first()
        )
        if payment is None:
            return None

        # اگر قبلاً نهایی شده، دوباره verify نزن (idempotent)
        if payment.status == PaymentStatus.COMPLETE:
            return payment

        # پیش‌علامت RETURN_FROM_BANK + ذخیره‌ی extra در raw (برای reverify بعدی).
        new_extra = bool(extra) and (payment.raw or {}).get("callback_extra") != extra
        if payment.status != PaymentStatus.RETURN_FROM_BANK or new_extra:
            raw = dict(payment.raw or {})
            if extra:
                raw["callback_extra"] = extra
            payment.mark(PaymentStatus.RETURN_FROM_BANK, raw=raw)

    # مرحله ۲: تماس شبکه‌ای خارج از قفل. خطای شبکه بالا می‌رود؛ رکورد از قبل returned است.
    gw = get_gateway(slug, transport=transport)
    result = gw.verify(
        authority=authority,
        amount=payment.amount_sent,  # مرجع یکتا، نه payment.amount
        order_id=payment.order_id,
        extra=extra,  # برای درگاه‌هایی مثل ملت که sale_reference_id لازم دارند
    )

    # مرحله ۳: نتیجه را اتمیک ذخیره کن (دوباره قفل بگیر، با callbackِ موازی امن).
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        if payment.status == PaymentStatus.COMPLETE:
            return payment
        if result.is_success:
            payment.mark(
                PaymentStatus.COMPLETE,
                reference_id=result.reference_id or "",
                card_number=result.card_number or "",
                raw=result.raw or {},
            )
        else:
            payment.mark(
                PaymentStatus.RETURN_FROM_BANK,
                error_code=result.error_code or "",
                error_message=result.error_message or "",
                raw=result.raw or {},
            )
    return payment


def reverify_pending(slug=None):
    """
    تأیید مجدد رکوردهای بازگشته‌ی تأییدنشده. برای اجرا در یک job دوره‌ای.
    اگر slug بدهی، فقط همان درگاه؛ وگرنه همه.

    خروجی: تعداد رکوردهایی که موفق نهایی شدند.
    """
    qs = Payment.objects.returned_unverified()
    if slug:
        qs = qs.filter(gateway_slug=slug)

    completed = 0
    for payment in qs:
        # extra را از raw بردار (در callback ذخیره شد) تا verify درگاه‌های شاپرکی
        # مثل ملت که به sale_reference_id نیاز دارند در reverify هم کار کند.
        extra = (payment.raw or {}).get("callback_extra")
        try:
            result = verify_payment(
                payment.gateway_slug, payment.authority, extra=extra
            )
        except GatewayConnectionError:
            # درگاه هنوز در دسترس نیست؛ رکورد returned می‌ماند، اجرای بعدی دوباره تلاش می‌کند.
            continue
        if result and result.is_success:
            completed += 1
    return completed


def expire_stale(older_than_minutes=15):
    """
    رکوردهایی که به درگاه رفته‌اند ولی خیلی وقت است برنگشته‌اند را منقضی می‌کند.
    خروجی: تعداد رکوردهای منقضی‌شده.
    """
    stale = Payment.objects.stale_redirects(older_than_minutes)
    return stale.update(status=PaymentStatus.EXPIRE_GATEWAY_TOKEN)
