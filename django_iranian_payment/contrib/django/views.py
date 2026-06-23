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

from . import services
from .models import Payment


def _extract_authority(request, slug):
    """
    authority را از callback می‌خواند. بسته به درگاه ممکن است در GET یا POST،
    و با نام‌های مختلف باشد. نام‌های رایج را پوشش می‌دهیم.
    """
    params = request.POST if request.method == "POST" else request.GET
    for key in ("Authority", "authority", "trackId", "token", "id", "RefId"):
        if key in params:
            return params[key]
    return None


def _extract_extra(request):
    """
    داده‌ی اضافی callback را برای درگاه‌هایی که در verify به آن نیاز دارند
    استخراج می‌کند:
    - ملت: SaleReferenceId و SaleOrderId (POST) برای bpVerifySettleRequest
    - دیجی‌پی: trackingCode (GET/POST) برای purchases/verify
    """
    params = request.POST if request.method == "POST" else request.GET
    extra = {}
    # ملت
    sale_ref = params.get("SaleReferenceId") or params.get("saleReferenceId")
    sale_order = params.get("SaleOrderId") or params.get("saleOrderId")
    if sale_ref:
        extra["sale_reference_id"] = sale_ref
    if sale_order:
        extra["sale_order_id"] = sale_order
    # دیجی‌پی
    tracking_code = params.get("trackingCode") or params.get("tracking_code")
    if tracking_code:
        extra["tracking_code"] = tracking_code
    return extra or None


def callback(request, slug):
    """
    مسیر بازگشت از بانک. authority را می‌خواند، verify می‌زند، و به callback_url
    رکورد با پارامتر وضعیت هدایت می‌کند.
    """
    authority = _extract_authority(request, slug)
    if not authority:
        raise Http404("authority در callback یافت نشد.")

    extra = _extract_extra(request)
    payment = services.verify_payment(slug, authority, extra=extra)
    if payment is None:
        raise Http404("رکورد پرداختی برای این authority یافت نشد.")

    sep = "&" if "?" in payment.callback_url else "?"
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
