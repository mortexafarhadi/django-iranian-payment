"""
لایه‌ی اتصال سبک به Django (بدون مدل، بدون state).

کاربر در settings.py می‌نویسد:

    IRANIAN_PAYMENT = {
        "sandbox": True,            # پیش‌فرض سراسری (اختیاری)
        "gateways": {
            "zarinpal": {"merchant_id": "xxxx-...."},          # از sandbox سراسری پیروی می‌کند
            "zibal": {"merchant": "zibal", "sandbox": False},  # این درگاه live است
        },
    }

sandbox هر درگاه مجزاست: اگر داخل config همان درگاه کلید "sandbox" بدهی، بر مقدار
سراسری اولویت دارد. این یعنی می‌توانی یک درگاه را live و درگاه دیگری را sandbox
داشته باشی هم‌زمان. اگر هیچ‌کدام را ندهی، پیش‌فرض False است (یعنی live).

سپس:
    from django_iranian_payment import get_gateway
    gw = get_gateway("zarinpal")
    # یا override صریح در کد (بر settings اولویت دارد):
    gw = get_gateway("zarinpal", sandbox=True)

این تابع state نگه نمی‌دارد. اگر مدل و ردیابی خودکار می‌خواهی، از لایه‌ی
اختیاری django_iranian_payment.contrib.django استفاده کن.
"""

from .exceptions import GatewayConfigurationError
from .gateways import get_gateway_class
from .models import Currency


def _get_settings():
    # import داخل تابع تا هسته بدون راه‌اندازی Django هم قابل import باشد
    from django.conf import settings

    conf = getattr(settings, "IRANIAN_PAYMENT", None)
    if conf is None:
        raise GatewayConfigurationError(
            "تنظیمات IRANIAN_PAYMENT در settings.py یافت نشد."
        )
    return conf


def get_default_currency() -> Currency:
    """
    واحد پیش‌فرض مبلغ را از IRANIAN_PAYMENT["currency"] می‌خواند (پیش‌فرض rial).
    این همان «مدیریت سراسری واحد پول» است: کاربر یک‌بار در settings تعیین می‌کند که
    مبلغ‌ها را به ریال می‌دهد یا تومان. لایه‌ی Django (start_payment) این را به
    PaymentRequest پاس می‌دهد. بانک همیشه ریال می‌گیرد؛ تبدیل خودکار انجام می‌شود.
    """
    conf = _get_settings()
    raw = conf.get("currency", Currency.RIAL.value)
    try:
        return Currency(raw)
    except ValueError:
        raise GatewayConfigurationError(
            f'currency نامعتبر در IRANIAN_PAYMENT: {raw!r} (فقط "rial" یا "toman").'
        )


def get_gateway(slug, *, timeout=15, transport=None, sandbox=None):
    """
    یک نمونه‌ی آماده از درگاه می‌سازد، با config خوانده‌شده از settings.
    transport اختیاری است؛ برای تست می‌توانی InMemoryTransport بدهی.

    sandbox هر درگاه مجزا تعیین می‌شود (اولویت از بالا به پایین):
      ۱. آرگومان صریح sandbox=... در همین فراخوانی (اگر None نباشد)
      ۲. کلید "sandbox" داخل config همان درگاه در settings
      ۳. کلید "sandbox" سراسری IRANIAN_PAYMENT (پیش‌فرض)
      ۴. در نبود همه: False (live)

    ⛔ درگاه‌هایی که sandbox واقعی ندارند (سامان، ملت: supports_sandbox=False) اگر
    sandbox برایشان True شود (مستقیم یا از ارث سراسری) در سازنده
    GatewayConfigurationError می‌دهند. راه‌حل: برای این درگاه‌ها "sandbox": False
    صریح بگذار وقتی sandbox سراسری True است.
    """
    conf = _get_settings()
    global_sandbox = bool(conf.get("sandbox", False))
    gateways_conf = conf.get("gateways", {})

    gw_config = gateways_conf.get(slug)
    if gw_config is None:
        raise GatewayConfigurationError(
            f'تنظیمات درگاه «{slug}» در IRANIAN_PAYMENT["gateways"] نیست.',
            gateway=slug,
        )

    # sandbox مجزای هر درگاه: config درگاه بر مقدار سراسری اولویت دارد؛
    # آرگومان صریح بر هر دو اولویت دارد.
    if sandbox is None:
        sandbox = bool(gw_config.get("sandbox", global_sandbox))

    # "sandbox" یک کلید کنترلی است، نه config خود درگاه؛ از config جدا می‌شود تا
    # به سازنده‌ی درگاه نشت نکند (بدون تغییر دادن دیکشنری settings کاربر).
    gw_config = {k: v for k, v in gw_config.items() if k != "sandbox"}

    gateway_cls = get_gateway_class(slug)
    gw = gateway_cls(
        config=gw_config, sandbox=sandbox, timeout=timeout, transport=transport
    )

    # واحد پیش‌فرض سراسری را به درخواست‌هایی که currency مشخص نکرده‌اند تزریق کن.
    # علت: تبدیل تومان→ریال داخل PaymentRequest.resolve_amount() و بر پایه‌ی
    # request.currency انجام می‌شود؛ ولی هسته Django-free است و نمی‌تواند
    # IRANIAN_PAYMENT["currency"] را بخواند. بدون این تزریق، فقط start_payment واحد
    # سراسری را اعمال می‌کرد و مسیر toolkit (get_gateway().initiate(PaymentRequest(...)))
    # آن را نادیده می‌گرفت (باگ: toman با rial فرقی نداشت). حالا هر دو مسیر یکسان‌اند.
    # اگر کاربر currency را صریح روی PaymentRequest بدهد، دست‌نخورده می‌ماند.
    default_currency = get_default_currency()
    _initiate = gw.initiate

    def initiate_with_default_currency(request):
        if getattr(request, "currency", None) is None:
            request.currency = default_currency
        return _initiate(request)

    gw.initiate = initiate_with_default_currency
    return gw
