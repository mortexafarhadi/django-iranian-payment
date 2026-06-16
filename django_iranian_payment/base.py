"""
کلاس پایه‌ی هر درگاه.

هر درگاه دقیقاً دو متد دارد: initiate و verify.
هیچ state ای روی self ذخیره نمی‌شود (برخلاف کد قدیمی تو با متغیرهای کلاسی).
config یک dict ساده است که از settings یا factory می‌آید.

نکته‌ی امنیتی: timeout روی هر درخواست HTTP اجباری است. بدون آن، یک بانک کند
می‌تواند worker جنگوی تو را بی‌نهایت بلاک کند.
"""

from abc import ABC, abstractmethod

import requests

from .exceptions import GatewayConnectionError
from .models import InitiateResult, PaymentRequest, PaymentResult


class BaseGateway(ABC):
    slug: str = None                 # شناسه‌ی متنی یکتا، مثل "zarinpal"
    requires: tuple = ()             # کلیدهای اجباری config، برای اعتبارسنجی

    def __init__(self, config: dict, sandbox: bool = False, timeout: int = 15):
        self.config = config
        self.sandbox = sandbox
        self.timeout = timeout
        self._validate_config()

    def _validate_config(self):
        from .exceptions import GatewayConfigurationError
        missing = [k for k in self.requires if not self.config.get(k)]
        if missing:
            raise GatewayConfigurationError(
                f"درگاه {self.slug}: کلیدهای الزامی وجود ندارند: {missing}",
                gateway=self.slug,
            )

    def _post(self, url, json=None, headers=None):
        """یک wrapper امن دور requests.post با مدیریت خطای شبکه."""
        try:
            response = requests.post(
                url, json=json, headers=headers, timeout=self.timeout
            )
            return response
        except requests.RequestException as e:
            raise GatewayConnectionError(
                f"خطای ارتباط با درگاه {self.slug}: {e}",
                gateway=self.slug,
            ) from e

    @abstractmethod
    def initiate(self, request: PaymentRequest) -> InitiateResult:
        """شروع پرداخت. خروجی redirect_url و authority است."""
        raise NotImplementedError

    @abstractmethod
    def verify(self, *, authority: str, amount: int, order_id: str) -> PaymentResult:
        """
        تأیید پرداخت پس از بازگشت از بانک.
        amount و order_id را تو از دیتابیس خودت می‌خوانی و پاس می‌دهی،
        چون بعضی درگاه‌ها (مثل زرین‌پال) این‌ها را در callback برنمی‌گردانند.
        """
        raise NotImplementedError
