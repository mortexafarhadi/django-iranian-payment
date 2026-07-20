from django.apps import AppConfig
from django.core.checks import Error, register


class IranianPaymentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_iranian_payment.contrib.django"
    label = "iranian_payment"
    verbose_name = "درگاه پرداخت ایرانی"

    def ready(self):
        # system check را ثبت می‌کنیم تا هنگام startup (runserver/هر manage.py)
        # اگر درگاهی که sandbox ندارد در حالت sandbox باشد، پروژه اجرا نشود.
        register(check_no_sandbox_gateways)


def check_no_sandbox_gateways(app_configs, **kwargs):
    """
    system check سطح Error: درگاه‌هایی که sandbox واقعی ندارند (سامان، ملت:
    supports_sandbox=False) اگر sandbox برایشان True باشد (مستقیم در config درگاه یا
    از ارث `sandbox` سراسری) خطای startup می‌دهند و manage.py/runserver اجرا نمی‌شود.

    چرا system check و نه فقط چک سازنده: سازنده lazy است (فقط هنگام
    get_gateway(...) در زمان پرداخت اجرا می‌شود)، پس runserver بدون خطا بالا می‌آمد.
    این چک پیکربندی را در startup می‌خواند و پروژه را قبل از هر درخواستی متوقف می‌کند.

    توجه: این چک فقط وقتی فعال است که اپ «django_iranian_payment.contrib.django» در
    INSTALLED_APPS باشد. در حالت مدیریت دستی DB (بدون این اپ)، چکِ سازنده هنگام
    اولین get_gateway همان خطا را می‌دهد.
    """
    from django.conf import settings

    from ...core.gateways import get_gateway_class

    errors = []
    conf = getattr(settings, "IRANIAN_PAYMENT", None)
    if not isinstance(conf, dict):
        return errors

    global_sandbox = bool(conf.get("sandbox", False))
    gateways = conf.get("gateways", {}) or {}
    for slug, gw_conf in gateways.items():
        gw_conf = gw_conf or {}
        resolved_sandbox = bool(gw_conf.get("sandbox", global_sandbox))
        if not resolved_sandbox:
            continue
        try:
            cls = get_gateway_class(slug)
        except Exception:
            # درگاه ثبت‌نشده/ناشناخته: get_gateway در زمان استفاده خودش خطا می‌دهد.
            continue
        if not getattr(cls, "supports_sandbox", True):
            errors.append(
                Error(
                    f"درگاه «{slug}» محیط sandbox ندارد و sandbox=True برایش مجاز نیست.",
                    hint=(
                        f'در IRANIAN_PAYMENT["gateways"]["{slug}"] مقدار "sandbox" را '
                        f"False کن (یا کلید را حذف کن). اگر sandbox سراسری True است، "
                        f'برای این درگاه صریحاً "sandbox": False بگذار. این درگاه فقط '
                        f"live است."
                    ),
                    id="iranian_payment.E001",
                )
            )
    return errors
