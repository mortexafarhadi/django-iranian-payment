"""
view های داخلی — تا کاربر حتی منطق callback را هم ننویسد.

دو مسیر:
- go_to_gateway(request, payment_id): کاربر را به درگاه می‌فرستد.
- callback(request, slug): از بانک برمی‌گردد، verify می‌زند، و به URL سفارش
  هدایت می‌کند (با پارامتر وضعیت).

این view ها اختیاری‌اند. کاربری که کنترل کامل می‌خواهد می‌تواند مستقیم از
services استفاده کند و view خودش را بنویسد.
"""

from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render

from ...core.exceptions import GatewayConnectionError
from . import services
from .models import Payment

# ─────────────────────────────────────────────────────────────
#  مشخصات callback هر درگاه — یک منبع واحد برای پیدا کردن رکورد و ساخت extra
# ─────────────────────────────────────────────────────────────
#
# هر درگاه در callback، پارامترهای متفاوتی برمی‌گرداند. این spec سه چیز را
# کدگذاری می‌کند:
#   lookup = (field, [param_keys]):
#       رکورد را با Payment.objects.filter(gateway_slug=slug, <field>=<param>) پیدا
#       کن. field یکی از "authority" یا "order_id" است. اولین param موجود برداشته
#       می‌شود. نکته‌ی مهم: callback سامان/دیجی‌پی توکن (authority) را برنمی‌گرداند،
#       پس باید با order_id (که خودمان فرستادیم و بانک echo می‌کند) پیدا شوند.
#   extra = {verify_key: [param_keys]}:
#       مقادیری که verify آن درگاه از callback لازم دارد (مثل ملت که به
#       sale_reference_id نیاز دارد). اولین param موجود برداشته می‌شود.
#
# ملت با RefId (authority، یکتا per-transaction) پیدا می‌شود تا رفتار تست‌شده‌ی
# live آن دست‌نخورده بماند (RefId یکتاتر از SaleOrderId است که در retry تکرار می‌شود).
_CALLBACK_SPEC = {
    "zarinpal": {"lookup": ("authority", ["Authority", "authority"]), "extra": {}},
    "zibal": {
        "lookup": ("authority", ["trackId", "trackid", "track_id"]),
        "extra": {},
    },
    "nextpay": {"lookup": ("authority", ["trans_id", "transId"]), "extra": {}},
    "sadad": {
        "lookup": ("authority", ["Token", "token"]),
        "extra": {"res_code": ["ResCode"]},
    },
    "mellat": {
        "lookup": ("authority", ["RefId", "refId"]),
        "extra": {
            "res_code": ["ResCode"],
            "sale_reference_id": ["SaleReferenceId", "saleReferenceId"],
            "sale_order_id": ["SaleOrderId", "saleOrderId"],
            "card_number": ["CardHolderPan"],
            "final_amount": ["FinalAmount"],
        },
    },
    "saman": {
        "lookup": ("order_id", ["ResNum", "resNum"]),
        "extra": {"ref_num": ["RefNum", "refNum"], "state": ["State"]},
    },
    "irankish": {
        "lookup": ("authority", ["token"]),
        "extra": {
            "reference_id": ["referenceId"],
            "token": ["token"],
            "result_code": ["resultCode"],
        },
    },
    "digipay": {
        "lookup": ("order_id", ["providerId", "provider_id"]),
        "extra": {
            "tracking_code": ["trackingCode", "tracking_code"],
            "result": ["result", "status"],
        },
    },
}

# کلیدهای عمومی authority برای درگاه‌های ناشناخته (خارج از spec) — رفتار قدیمی.
_GENERIC_AUTHORITY_KEYS = ("Authority", "authority", "trackId", "token", "id", "RefId")


def _params(request):
    """پارامترهای callback را از POST یا GET برمی‌گرداند."""
    return request.POST if request.method == "POST" else request.GET


def _locate_payment(request, slug):
    """
    رکورد Payment مربوط به این callback را پیدا می‌کند. برای درگاه‌های شناخته‌شده
    از _CALLBACK_SPEC، و برای درگاه ناشناخته از کلیدهای عمومی authority.
    """
    params = _params(request)
    spec = _CALLBACK_SPEC.get(slug)
    if spec is not None:
        field, keys = spec["lookup"]
        for key in keys:
            value = params.get(key)
            if value:
                return (
                    Payment.objects.filter(gateway_slug=slug, **{field: value})
                    .order_by("-created_at")
                    .first()
                )
        return None

    # درگاه خارج از spec: تلاش عمومی با authority.
    for key in _GENERIC_AUTHORITY_KEYS:
        value = params.get(key)
        if value:
            return (
                Payment.objects.filter(gateway_slug=slug, authority=value)
                .order_by("-created_at")
                .first()
            )
    return None


def _extract_extra(request, slug):
    """
    داده‌ی اضافی callback را برای درگاه‌هایی که در verify به آن نیاز دارند می‌سازد:
    - ملت: sale_reference_id/sale_order_id/res_code/... (bpVerifySettleRequest)
    - سامان: ref_num (RefNum) و state
    - ایران‌کیش: reference_id/token/result_code
    - سداد: res_code
    - دیجی‌پی: tracking_code و result
    """
    spec = _CALLBACK_SPEC.get(slug)
    if spec is None:
        return None
    params = _params(request)
    extra = {}
    for verify_key, candidates in spec["extra"].items():
        for candidate in candidates:
            if params.get(candidate):
                extra[verify_key] = params[candidate]
                break
    return extra or None


def callback(request, slug):
    """
    مسیر بازگشت از بانک. رکورد را طبق spec درگاه پیدا می‌کند، verify می‌زند، و به
    callback_url رکورد با پارامتر وضعیت هدایت می‌کند.
    """
    payment = _locate_payment(request, slug)
    if payment is None:
        raise Http404("رکورد پرداختی برای این callback یافت نشد.")

    extra = _extract_extra(request, slug)
    sep = "&" if "?" in payment.callback_url else "?"

    try:
        result = services.verify_payment(slug, payment.authority, extra=extra)
    except GatewayConnectionError:
        # درگاه در دسترس نیست (بی‌پاسخ/۵۰۰) هنگام verify. رکورد از قبل
        # RETURN_FROM_BANK است (پیش‌علامت services)، پس reverify_pending بعداً
        # تمامش می‌کند. کاربر را با وضعیت pending برگردان، نه صفحه‌ی خطا.
        target = (
            f"{payment.callback_url}{sep}payment_status=pending"
            f"&order_id={payment.order_id}"
        )
        return HttpResponseRedirect(target)

    if result is None:
        raise Http404("رکورد پرداختی برای این authority یافت نشد.")
    payment = result

    status = "success" if payment.is_success else "failed"
    target = f"{payment.callback_url}{sep}payment_status={status}&order_id={payment.order_id}"
    return HttpResponseRedirect(target)


def go_to_gateway(request, payment_id):
    """
    کاربر را به درگاه بانک می‌فرستد. (برای حالتی که redirect_url را در DB ذخیره
    کرده‌ای و می‌خواهی بعداً هدایت کنی.)
    درگاه‌هایی که POST فرم می‌خواهند (مثل ملت) با template auto-submit مدیریت می‌شوند.
    """
    payment = get_object_or_404(Payment, pk=payment_id)
    if not payment.redirect_url:
        raise Http404("redirect_url برای این پرداخت ذخیره نشده است.")

    if payment.raw.get("redirect_method") == "POST":
        return render(
            request,
            "iranian_payment/post_redirect.html",
            {
                "action": payment.redirect_url,
                "fields": payment.raw.get("redirect_fields", {}),
            },
        )

    return HttpResponseRedirect(payment.redirect_url)
