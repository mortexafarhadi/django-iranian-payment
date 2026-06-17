"""
کلاس پایه‌ی هر درگاه.

هر درگاه دقیقاً دو متد دارد: initiate و verify.
هیچ state ای روی self ذخیره نمی‌شود.

نوآوری: لایه‌ی HTTP (transport) قابل تزریق است. در تولید از RequestsTransport
استفاده می‌شود؛ در تست از InMemoryTransport. این یعنی منطق کامل initiate/verify
بدون mock و بدون شبکه‌ی واقعی تست می‌شود — همان «مدرک با اجرای کد».

نکته‌ی امنیتی: timeout روی هر درخواست HTTP اجباری است.
"""

from abc import ABC, abstractmethod

from .exceptions import GatewayConnectionError, GatewayConfigurationError
from .models import InitiateResult, PaymentRequest, PaymentResult


class BaseTransport(ABC):
    """رابط لایه‌ی HTTP. هر چیزی که post بدهد می‌تواند جای requests بنشیند."""

    @abstractmethod
    def post(self, url, *, json=None, data=None, headers=None, timeout=15) -> dict:
        """یک POST می‌زند و پاسخ را به‌صورت dict (JSON دیکد شده) برمی‌گرداند."""
        raise NotImplementedError


class RequestsTransport(BaseTransport):
    """لایه‌ی واقعی تولید، روی کتابخانه‌ی requests."""

    def post(self, url, *, json=None, data=None, headers=None, timeout=15) -> dict:
        import requests

        try:
            response = requests.post(
                url, json=json, data=data, headers=headers, timeout=timeout
            )
        except requests.RequestException as e:
            raise GatewayConnectionError(f"خطای ارتباط با درگاه: {e}") from e
        try:
            return response.json()
        except ValueError as e:
            raise GatewayConnectionError(
                f"پاسخ درگاه JSON معتبر نبود: {e}", raw={"text": response.text}
            ) from e

    def post_with_headers(
        self, url, *, json=None, data=None, headers=None, timeout=15
    ) -> tuple:
        """
        مثل post ولی (body_dict, response_headers_dict) برمی‌گرداند.
        برای درگاه‌هایی که به هدر پاسخ نیاز دارند (مثل سامان neo-pg که آدرس
        مرحله‌ی بعد را در هدر X-IPG-Url می‌فرستد).
        """
        import requests

        try:
            response = requests.post(
                url, json=json, data=data, headers=headers, timeout=timeout
            )
        except requests.RequestException as e:
            raise GatewayConnectionError(f"خطای ارتباط با درگاه: {e}") from e
        resp_headers = dict(response.headers)
        try:
            return response.json(), resp_headers
        except ValueError as e:
            raise GatewayConnectionError(
                f"پاسخ درگاه JSON معتبر نبود: {e}", raw={"text": response.text}
            ) from e


class InMemoryTransport(BaseTransport):
    """
    لایه‌ی تست. پاسخ‌های از پیش‌تعیین‌شده را بر اساس URL برمی‌گرداند.
    بدون شبکه، بدون mock. requests_log همه‌ی فراخوانی‌ها را برای assert نگه می‌دارد.
    """

    def __init__(self, responses: dict, response_headers: dict = None):
        self.responses = responses  # نگاشت url → dict پاسخ
        self.response_headers = response_headers or {}  # نگاشت url → dict هدر پاسخ
        self.requests_log = []  # لیست (url, json, data, headers)

    def post(self, url, *, json=None, data=None, headers=None, timeout=15) -> dict:
        self.requests_log.append(
            {"url": url, "json": json, "data": data, "headers": headers}
        )
        if url not in self.responses:
            raise GatewayConnectionError(f"پاسخ تستی برای URL تعریف نشده: {url}")
        return self.responses[url]

    def post_with_headers(
        self, url, *, json=None, data=None, headers=None, timeout=15
    ) -> tuple:
        """
        نسخه‌ی تستی post_with_headers. هدر پاسخ از response_headers خوانده می‌شود
        (نگاشت url → dict هدر) که در سازنده اختیاری داده می‌شود.
        """
        body = self.post(url, json=json, data=data, headers=headers, timeout=timeout)
        resp_headers = self.response_headers.get(url, {})
        return body, resp_headers

    def soap_call(self, method, params):
        """
        شبیه‌سازی یک فراخوانی SOAP برای تست درگاه‌های SOAP (مثل ملت).
        پاسخ بر اساس نام متد از responses خوانده می‌شود. فراخوانی در
        requests_log ثبت می‌شود تا بتوان پارامترها را assert کرد.
        """
        self.requests_log.append({"soap_method": method, "params": params})
        if method not in self.responses:
            raise GatewayConnectionError(
                f"پاسخ تستی SOAP برای متد تعریف نشده: {method}"
            )
        return self.responses[method]


class BaseGateway(ABC):
    slug: str = None  # شناسه‌ی متنی یکتا، مثل "zarinpal"
    requires: tuple = ()  # کلیدهای اجباری config، برای اعتبارسنجی

    def __init__(
        self,
        config: dict,
        *,
        sandbox: bool = False,
        timeout: int = 15,
        transport: BaseTransport = None,
    ):
        self.config = config
        self.sandbox = sandbox
        self.timeout = timeout
        self.transport = transport or RequestsTransport()
        self._validate_config()

    def _validate_config(self):
        missing = [k for k in self.requires if not self.config.get(k)]
        if missing:
            raise GatewayConfigurationError(
                f"درگاه {self.slug}: کلیدهای الزامی وجود ندارند: {missing}",
                gateway=self.slug,
            )

    def _post(self, url, *, json=None, data=None, headers=None) -> dict:
        """POST امن با timeout و تبدیل خطای شبکه به GatewayConnectionError."""
        try:
            return self.transport.post(
                url, json=json, data=data, headers=headers, timeout=self.timeout
            )
        except GatewayConnectionError as e:
            # غنی‌سازی خطا با نام درگاه
            if e.gateway is None:
                e.gateway = self.slug
            raise

    @abstractmethod
    def initiate(self, request: PaymentRequest) -> InitiateResult:
        """شروع پرداخت. خروجی redirect_url و authority است."""
        raise NotImplementedError

    @abstractmethod
    def verify(
        self, *, authority: str, amount: int, order_id: str, extra: dict = None
    ) -> PaymentResult:
        """
        تأیید پرداخت پس از بازگشت از بانک.
        amount را تو از دیتابیس خودت می‌خوانی و پاس می‌دهی — همان amount_to_send
        که در initiate برگشت، نه مبلغ پایه‌ی سفارش.

        extra (اختیاری): دیکشنری برای درگاه‌هایی که در verify به داده‌ی بیشتری
        از یک authority نیاز دارند (مثل ملت که به sale_reference_id و
        sale_order_id نیاز دارد؛ این‌ها در callbackِ POST از بانک برمی‌گردند).
        درگاه‌های ساده (زرین‌پال/زیبال) این پارامتر را نادیده می‌گیرند.
        """
        raise NotImplementedError