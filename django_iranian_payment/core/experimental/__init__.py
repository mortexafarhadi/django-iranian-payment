"""
درگاه‌های تجربی/معلق — تست‌نشده یا موقتاً خارج از registry عمومی.

⚠️ اغلب این درگاه‌ها با اطلاعات واقعی بانکی تست نشده‌اند و متدهایشان
NotImplementedError می‌دهند. استثنا: pay_ir و idpay که کد کاملشان سالم است ولی
به‌دلیل بی‌ثباتی/از کار افتادن سرویس موقتاً اینجایند. در پروداکشن با احتیاط.

دسترسی فقط با import صریح:
    from django_iranian_payment.core.experimental import MellatGateway
    from django_iranian_payment.core.experimental import PayIrGateway  # معلق
    from django_iranian_payment.core.experimental import IDPayGateway  # معلق
"""
from .eghtesad_novin import EghtesadNovinGateway
from .idpay import IDPayGateway
from .irankish import IrankishGateway
from .melli import MelliGateway
from .nextpay import NextPayGateway
from .parsian import ParsianGateway
from .pasargad import PasargadGateway
from .pay_ir import PayIrGateway
from .payping import PayPingGateway
from .saderat import SaderatGateway
from .saman import SamanGateway
from .sepah import SepahGateway
from .tejarat import TejaratGateway
from .vandar import VandarGateway

__all__ = [
    "EghtesadNovinGateway",
    "IDPayGateway",
    "IrankishGateway",
    "MelliGateway",
    "NextPayGateway",
    "ParsianGateway",
    "PasargadGateway",
    "PayIrGateway",
    "PayPingGateway",
    "SaderatGateway",
    "SamanGateway",
    "SepahGateway",
    "TejaratGateway",
    "VandarGateway",
]