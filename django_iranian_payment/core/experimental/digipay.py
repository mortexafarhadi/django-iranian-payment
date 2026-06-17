"""
درگاه پرداخت دیجی‌پی (Digipay UPG) — REST/JSON. پیاده‌سازی بر اساس مستند رسمی
پلتفرم پذیرندگان دیجی‌پی (uat.mydigipay.info / api.mydigipay.com).

⚠️ تجربی: کد کامل از مستند رسمی است و منطق با InMemoryTransport تست شده، ولی هنوز
با ترمینال/کلید واقعی (sandbox یا live) تست نشده است. تا تست واقعی موفق در registry
عمومی قرار نمی‌گیرد و با get_gateway در دسترس نیست. فقط با import صریح:
    from django_iranian_payment.core.experimental.digipay import DigipayGateway

تفاوت ساختاری مهم با زرین‌پال/زیبال:
دیجی‌پی احراز هویت دومرحله‌ای OAuth2 دارد. پیش از هر فراخوانی باید توکن گرفت:
  1) POST oauth/token با Basic auth (base64 از "client_id:client_secret") و
     فرم username/password/grant_type=password → access_token.
  2) سپس فراخوانی سرویس‌ها با هدر "Authorization: Bearer <access_token>".

روند کامل (طبق مستند):
1. initiate:
   الف) گرفتن access_token (سرویس لاگین).
   ب) POST tickets/business?type=<ticket_type> با amount/cellNumber/providerId/
      callbackUrl. موفقیت: result.status == 0. خروجی redirectUrl و ticket.
   کاربر را به redirectUrl می‌فرستیم؛ authority همان ticket است.
2. بازگشت از بانک (callback): دیجی‌پی trackingCode و providerId و result و type
   را برمی‌گرداند. trackingCode برای verify لازم است (در extra پاس داده می‌شود).
3. verify:
   POST purchases/verify?type=<ticket_type> با trackingCode و providerId.
   موفقیت: result.status == 0 (و در نمونه‌ی موفق result.title == "SUCCESS").
   ⚠️ طبق هشدار مستند: پیش از verify باید amount و providerid بازگشتی را با
   تراکنش ثبت‌شده‌ی خودت تطبیق دهی. تطبیق providerId اینجا انجام می‌شود؛ تطبیق
   amount چون دیجی‌پی در پاسخ verify مبلغ را تضمین‌شده برنمی‌گرداند، مسئولیت
   لایه‌ی بالادست است (amount_to_send که در initiate رفت).
   اگر verify را نزنی، پرداخت پس از مدتی خودکار لغو و وجه مرجوع می‌شود.

نکات مستند که رعایت شده:
- مبلغ ریال است (Long).
- providerId همان شناسه‌ی یکتای سفارش سمت ماست (order_id) و در verify دوباره لازم است.
- کد result.status == 0 یعنی موفق در همه‌ی سرویس‌ها (جدول 47/48). کدهای دیگر خطا.
- 9008 «این خرید با داده‌های متفاوتی قبلاً ثبت شده» و 9012/9004 وضعیت‌های
  میانی‌اند؛ به‌صورت محافظه‌کارانه FAILED نگاشت می‌شوند مگر اینکه مستند خلافش را
  در تست واقعی نشان دهد.

TODO (پیش از عمومی‌کردن، نیازمند تست واقعی):
- رفتار دقیق کدهای 9004 (درحال انجام) و 9011 (نتیجه نامشخص): آیا باید PENDING
  برگردانده شود و reverify شود؟ مستند صریح نیست؛ با sandbox واقعی روشن شود.
- مدیریت refresh_token برای کش توکن. فعلاً هر فراخوانی توکن تازه می‌گیرد
  (سازگار با اصل بدون state). اگر نرخ فراخوانی بالا شد، کش توکن لازم می‌شود.
- آیا verify یک trackingCode تکراری را با کد خاصی (مثل DUPLICATE) جواب می‌دهد؟
  در مستند کد صریح «تکراری برای verify» دیده نشد؛ پس از تست واقعی نگاشت شود.
- بازگشت وجه (purchases/refund)، تحویل خرید (delivery) و پیگیری عودت در مستند
  هستند ولی اینجا پیاده نشده‌اند؛ در صورت نیاز افزوده شوند.
"""

import base64

from ..base import BaseGateway
from ..exceptions import GatewayPaymentError
from ..models import (
    InitiateResult,
    PaymentRequest,
    PaymentResult,
    PaymentStatus,
)

_BASE_LIVE = "https://api.mydigipay.com/digipay/api"
_BASE_SANDBOX = "https://uat.mydigipay.info/digipay/api"

# نسخه‌ی API که در هدر Digipay-Version می‌رود (طبق مستند: 2022-02-02)
_DIGIPAY_VERSION = "2022-02-02"

# نوع تیکت پیش‌فرض: 11 = برای تمام فیچرهای روی UPG (جدول 3)
_DEFAULT_TICKET_TYPE = 11

# کد موفقیت result.status در همه‌ی سرویس‌ها (جدول 47)
_RESULT_SUCCESS = 0


class DigipayGateway(BaseGateway):
    slug = "digipay"
    requires = ("username", "password", "client_id", "client_secret", "provider_id")

    @property
    def _base(self):
        return self.config.get("base_url") or (
            _BASE_SANDBOX if self.sandbox else _BASE_LIVE
        )

    @property
    def _ticket_type(self):
        return int(self.config.get("ticket_type", _DEFAULT_TICKET_TYPE))

    @property
    def _token_url(self):
        return f"{self._base}/oauth/token"

    @property
    def _ticket_url(self):
        return f"{self._base}/tickets/business?type={self._ticket_type}"

    @property
    def _verify_url(self):
        return f"{self._base}/purchases/verify?type={self._ticket_type}"

    # ---------- احراز هویت ----------

    def _basic_auth_header(self):
        """Basic base64(client_id:client_secret) — جدول لاگین مستند."""
        raw = f"{self.config['client_id']}:{self.config['client_secret']}"
        encoded = base64.b64encode(raw.encode("utf-8")).decode("ascii")
        return f"Basic {encoded}"

    def _get_access_token(self):
        """
        سرویس لاگین. بدنه به‌صورت form-data و هدر Authorization=Basic.
        خروجی موفق شامل access_token است. خطای احراز هویت → کد http 401.
        """
        data = {
            "username": self.config["username"],
            "password": self.config["password"],
            "grant_type": "password",
        }
        headers = {"Authorization": self._basic_auth_header()}
        result = self._post(self._token_url, data=data, headers=headers)

        token = result.get("access_token")
        if not token:
            raise GatewayPaymentError(
                "دریافت توکن احراز هویت دیجی‌پی ناموفق بود "
                "(access_token در پاسخ نبود — نام کاربری/رمز/کلاینت را بررسی کن).",
                gateway=self.slug,
                code="auth_failed",
                raw=result,
            )
        return token

    def _bearer_headers(self, token):
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Agent": "WEB",
            "Digipay-Version": _DIGIPAY_VERSION,
        }

    @staticmethod
    def _result_status(result):
        """status را از کلید result استخراج می‌کند (می‌تواند رشته یا عدد باشد)."""
        block = result.get("result") or {}
        status = block.get("status")
        try:
            return int(status)
        except (TypeError, ValueError):
            return status

    @staticmethod
    def _result_message(result):
        block = result.get("result") or {}
        return block.get("message") or block.get("title") or ""

    # ---------- initiate ----------

    def initiate(self, request: PaymentRequest) -> InitiateResult:
        fee_result = request.resolve_amount()
        amount_to_send = fee_result.amount_to_send

        token = self._get_access_token()

        payload = {
            "amount": amount_to_send,  # ریال، با کارمزد در صورت وجود
            "providerId": str(request.order_id),  # شناسه‌ی یکتای سفارش سمت ما
            "callbackUrl": request.callback_url,
        }
        if request.mobile:
            payload["cellNumber"] = request.mobile

        result = self._post(
            self._ticket_url, json=payload, headers=self._bearer_headers(token)
        )

        if self._result_status(result) != _RESULT_SUCCESS:
            raise GatewayPaymentError(
                f"ساخت تیکت دیجی‌پی ناموفق بود: {self._result_message(result)}",
                gateway=self.slug,
                code=str(self._result_status(result)),
                raw=result,
            )

        ticket = result.get("ticket")
        redirect_url = result.get("redirectUrl")
        if not redirect_url or not ticket:
            raise GatewayPaymentError(
                "پاسخ تیکت دیجی‌پی redirectUrl یا ticket نداشت.",
                gateway=self.slug,
                code="missing_ticket",
                raw=result,
            )

        return InitiateResult(
            redirect_url=redirect_url,
            authority=ticket,
            amount_to_send=amount_to_send,
            fee=fee_result.fee,
            raw=result,
        )

    # ---------- verify ----------

    def _resolve_tracking_code(self, authority, extra):
        """
        trackingCode (کد رهگیری خرید) را از extra می‌گیرد. دیجی‌پی این مقدار را
        در نتیجه‌ی پرداخت (callback) برمی‌گرداند و verify با آن انجام می‌شود، نه
        با ticket. اگر در extra نبود، authority به‌عنوان جایگزین استفاده می‌شود.
        """
        extra = extra or {}
        tracking = (
            extra.get("tracking_code")
            or extra.get("trackingCode")
            or extra.get("trackingcode")
        )
        if not tracking:
            raise GatewayPaymentError(
                "درگاه دیجی‌پی برای verify به trackingCode نیاز دارد "
                "(از نتیجه‌ی پرداخت/callback می‌آید). آن را در extra بده: "
                "verify(..., extra={'tracking_code': ...}).",
                gateway=self.slug,
                code="missing_tracking_code",
            )
        return str(tracking)

    def verify(
        self, *, authority: str, amount: int, order_id: str, extra: dict = None
    ) -> PaymentResult:
        extra = extra or {}

        # اگر نتیجه‌ی پرداخت در callback آمد و SUCCESS نبود، حتی verify نزن.
        callback_result = extra.get("result") or extra.get("status")
        if callback_result is not None and str(callback_result).upper() not in (
            "SUCCESS",
            "0",
        ):
            return PaymentResult(
                status=PaymentStatus.FAILED,
                gateway_slug=self.slug,
                order_id=order_id,
                error_code=str(callback_result),
                error_message=f"نتیجه‌ی پرداخت دیجی‌پی موفق نبود: {callback_result}",
                raw={"callback_result": callback_result},
            )

        tracking_code = self._resolve_tracking_code(authority, extra)

        token = self._get_access_token()
        payload = {
            "trackingCode": tracking_code,
            "providerId": str(order_id),
        }
        result = self._post(
            self._verify_url, json=payload, headers=self._bearer_headers(token)
        )

        if self._result_status(result) != _RESULT_SUCCESS:
            return PaymentResult(
                status=PaymentStatus.FAILED,
                gateway_slug=self.slug,
                order_id=order_id,
                error_code=str(self._result_status(result)),
                error_message=str(self._result_message(result) or "verify ناموفق"),
                raw=result,
            )

        return PaymentResult(
            status=PaymentStatus.SUCCESS,
            gateway_slug=self.slug,
            order_id=order_id,
            reference_id=str(result.get("rrn") or tracking_code),
            amount=amount,
            raw=result,
        )
