"""
درگاه‌های تجربی — تست‌نشده، فقط برای توسعه‌دهنده.

⚠️ هیچ‌کدام از این درگاه‌ها با اطلاعات واقعی بانکی تست نشده‌اند و اغلب
متدهایشان NotImplementedError می‌دهند یا TODO دارند. در پروداکشن استفاده نکن.

این ماژول عمداً از registry عمومی (django_iranian_payment.gateways) جداست،
پس get_gateway("mellat") خطا می‌دهد. دسترسی فقط با import صریح:

    from django_iranian_payment.experimental import MellatGateway

روند نهایی‌سازی هر درگاه:
    ۱. TODOها را با مستندات رسمی همان بانک پر کن.
    ۲. با sandbox/ترمینال واقعی تست کن.
    ۳. فایل را از experimental/ به gateways/ منتقل کن.
    ۴. در gateways/__init__.py به _REGISTRY اضافه کن.
"""

from .eghtesad_novin import EghtesadNovinGateway
from .irankish import IrankishGateway
from .mellat import MellatGateway
from .melli import MelliGateway
from .nextpay import NextPayGateway
from .parsian import ParsianGateway
from .pasargad import PasargadGateway
from .payping import PayPingGateway
from .saderat import SaderatGateway
from .saman import SamanGateway
from .sepah import SepahGateway
from .tejarat import TejaratGateway
from .vandar import VandarGateway

__all__ = [
    "EghtesadNovinGateway",
    "IrankishGateway",
    "MellatGateway",
    "MelliGateway",
    "NextPayGateway",
    "ParsianGateway",
    "PasargadGateway",
    "PayPingGateway",
    "SaderatGateway",
    "SamanGateway",
    "SepahGateway",
    "TejaratGateway",
    "VandarGateway",
]
