"""
درگاه ایران کیش (irankish) — REST/JSON با احراز هویت رمزنگاری‌شده (AES+RSA).
پیاده‌سازی بر اساس کد مرجع رسمی ایران کیش (tokenization v3).

⚠️ تجربی: منطق با InMemoryTransport تست شده، ولی با ترمینال واقعی تست نشده.
تا تست واقعی در registry عمومی قرار نمی‌گیرد. فقط با import صریح:
    from django_iranian_payment.core.experimental.irankish import IrankishGateway

تفاوت‌های امنیتی عمدی با کد مرجع (کد مرجع برای production امن نیست):
  - کد مرجع verify=False می‌زند (SSL خاموش) → اینجا هرگز. transport ما همیشه
    گواهی SSL را اعتبارسنجی می‌کند. خاموش‌کردن SSL در جابه‌جایی پول = آسیب MITM.
  - کد مرجع DEFAULT_CIPHERS را در سطح ماژول دستکاری می‌کند (side-effect سراسری
    روی کل پروسه‌ی پایتون کاربر) → اینجا حذف شد.

روند کامل:
1. initiate → tokenization/make: یک authenticationEnvelope رمزنگاری‌شده می‌سازیم
   (AES-CBC روی terminalId+passPhrase+amount، سپس SHA256، سپس RSA روی کلید
   عمومی بانک) و توکن می‌گیریم. خروجی موفق responseCode == "00".
2. هدایت: کاربر با POST فرم (فیلد tokenIdentity) به صفحه‌ی پرداخت می‌رود.
   redirect_url مقصد است؛ لایه‌ی Django فرم auto-submit می‌سازد.
3. بازگشت (callback POST): بانک resultCode/token/referenceId/InvoiceNumber/... را
   POST می‌کند. resultCode == "100" یعنی پرداخت موفق سمت کاربر.
4. verify → confirmation/purchase: با token و referenceId. status==true یعنی
   تأیید نهایی موفق.

وابستگی‌های اختیاری (مثل zeep برای ملت):
    uv add pycryptodome rsa
"""

from ..base import BaseGateway
from ..exceptions import (
    GatewayConfigurationError,
    GatewayPaymentError,
)
from ..models import (
    InitiateResult,
    PaymentRequest,
    PaymentResult,
    PaymentStatus,
)

_TOKEN_URL = "https://ikc.shaparak.ir/api/v3/tokenization/make"
_REDIRECT_URL = "https://ikc.shaparak.ir/iuiv3/IPG/Index/"
_CONFIRM_URL = "https://ikc.shaparak.ir/api/v3/confirmation/purchase"

_TOKEN_KEY = "tokenIdentity"  # نام فیلد توکن در فرم هدایت

# کدهای پاسخ
_RC_TOKEN_OK = "00"  # دریافت توکن موفق
_RC_CALLBACK_OK = "100"  # پرداخت موفق سمت کاربر (در callback)


class IrankishGateway(BaseGateway):
    slug = "irankish"
    requires = ("terminal_id", "acceptor_id", "pass_phrase", "public_key")

    @property
    def _token_url(self):
        return self.config.get("token_url", _TOKEN_URL)

    @property
    def _confirm_url(self):
        return self.config.get("confirm_url", _CONFIRM_URL)

    @property
    def _redirect_base(self):
        return self.config.get("redirect_url", _REDIRECT_URL)

    # ---------- رمزنگاری احراز هویت ----------

    def _build_auth_envelope(self, amount: int) -> dict:
        """
        authenticationEnvelope را طبق الگوریتم ایران کیش می‌سازد:
          1. کلید و IV تصادفی AES (هرکدام ۱۶ بایت).
          2. رشته‌ی hex از terminalId + passPhrase + amount(۱۲ رقم) + "00".
          3. این رشته را AES-CBC رمز و سپس SHA256 می‌کنیم.
          4. ۴۸ بایت = [aes_key(16) | sha256(32)] را با کلید عمومی RSA رمز می‌کنیم.
        خروجی: {"iv": hex, "data": hex}.

        public_key در config یا مسیر فایل .pem است یا محتوای PEM (رشته/بایت).
        """
        import os

        try:
            import rsa
            from Crypto.Cipher import AES
            from Crypto.Hash import SHA256
            from Crypto.Util.Padding import pad
        except ImportError as e:
            raise GatewayConfigurationError(
                "درگاه ایران کیش به pycryptodome و rsa نیاز دارد: "
                "uv add pycryptodome rsa",
                gateway=self.slug,
            ) from e

        public_key = self._load_public_key(rsa)

        terminal_id = str(self.config["terminal_id"])
        pass_phrase = str(self.config["pass_phrase"])
        hex_string = terminal_id + pass_phrase + str(amount).zfill(12) + "00"
        try:
            raw = bytes(bytearray.fromhex(hex_string))
        except ValueError as e:
            raise GatewayConfigurationError(
                "terminal_id و pass_phrase ایران کیش باید رشته‌ی hex معتبر "
                "(طول زوج، فقط 0-9a-f) باشند تا با amount به بایت تبدیل شوند.",
                gateway=self.slug,
            ) from e

        aes_key, aes_iv = os.urandom(16), os.urandom(16)
        aes = AES.new(aes_key, AES.MODE_CBC, aes_iv)
        encrypted = aes.encrypt(pad(raw, 16))
        digest = SHA256.new(encrypted).digest()

        payload_48 = bytearray(48)
        payload_48[0:16] = aes_key
        payload_48[16:48] = bytearray(digest)

        return {
            "iv": aes_iv.hex(),
            "data": rsa.encrypt(bytes(payload_48), public_key).hex(),
        }

    def _load_public_key(self, rsa):
        """کلید عمومی RSA را از config می‌خواند: مسیر فایل .pem یا محتوای PEM."""
        pk = self.config["public_key"]
        if isinstance(pk, (bytes, bytearray)):
            data = bytes(pk)
        elif isinstance(pk, str) and "BEGIN" in pk:
            data = pk.encode()
        else:
            # فرض: مسیر فایل
            try:
                with open(pk, "rb") as fh:
                    data = fh.read()
            except OSError as e:
                raise GatewayConfigurationError(
                    f"کلید عمومی ایران کیش خوانده نشد: {pk}",
                    gateway=self.slug,
                ) from e
        try:
            return rsa.PublicKey.load_pkcs1_openssl_pem(data)
        except Exception as e:
            raise GatewayConfigurationError(
                f"کلید عمومی ایران کیش معتبر نیست: {e}",
                gateway=self.slug,
            ) from e

    # ---------- initiate ----------

    def initiate(self, request: PaymentRequest) -> InitiateResult:
        import datetime

        fee_result = request.resolve_amount()
        amount_to_send = fee_result.amount_to_send

        envelope = self._build_auth_envelope(amount_to_send)
        payload = {
            "authenticationEnvelope": envelope,
            "request": {
                "transactionType": "Purchase",
                "terminalId": str(self.config["terminal_id"]),
                "acceptorId": str(self.config["acceptor_id"]),
                "amount": amount_to_send,  # ریال، با کارمزد در صورت وجود
                "revertUri": request.callback_url,
                "requestId": str(request.order_id),
                "requestTimestamp": int(
                    datetime.datetime.now(datetime.timezone.utc).timestamp()
                ),
            },
        }
        headers = {"Content-Type": "application/json"}
        result = self._post(self._token_url, json=payload, headers=headers)

        if result.get("responseCode") != _RC_TOKEN_OK:
            raise GatewayPaymentError(
                f"ایران کیش توکن نداد. کد: {result.get('responseCode')} — "
                f"{result.get('description')}",
                gateway=self.slug,
                code=str(result.get("responseCode")),
                raw=result,
            )

        token = (result.get("result") or {}).get("token")
        if not token:
            raise GatewayPaymentError(
                "ایران کیش با کد موفق ولی بدون توکن پاسخ داد.",
                gateway=self.slug,
                code=_RC_TOKEN_OK,
                raw=result,
            )

        return InitiateResult(
            # هدایت با POST فرم: فیلد tokenIdentity به redirect base.
            redirect_url=f"{self._redirect_base}{token}",
            authority=token,
            amount_to_send=amount_to_send,
            fee=fee_result.fee,
            raw={
                "result": result,
                "token": token,
                "post_to": self._redirect_base,
                "token_field": _TOKEN_KEY,
            },
        )

    # ---------- verify ----------

    def _resolve_verify_params(self, authority, extra):
        """
        token و referenceId را از extra/authority می‌گیرد. ایران کیش در callback
        token و referenceId را POST می‌کند؛ verify به هر دو نیاز دارد.
        """
        extra = extra or {}
        token = extra.get("token") or authority
        reference_id = extra.get("reference_id") or extra.get("referenceId")
        if not reference_id:
            raise GatewayPaymentError(
                "درگاه ایران کیش برای verify به reference_id نیاز دارد "
                "(از callbackِ POST بانک می‌آید). آن را در extra بده: "
                "verify(..., extra={'reference_id': ..., 'token': ...}).",
                gateway=self.slug,
                code="missing_reference_id",
            )
        return str(token), str(reference_id)

    def verify(
        self, *, authority: str, amount: int, order_id: str, extra: dict = None
    ) -> PaymentResult:
        extra = extra or {}

        # اگر resultCode در callback آمد و 100 نبود، پرداخت ناموفق بوده — verify نزن.
        result_code = extra.get("result_code") or extra.get("resultCode")
        if result_code is not None and str(result_code) != _RC_CALLBACK_OK:
            return PaymentResult(
                status=PaymentStatus.FAILED,
                gateway_slug=self.slug,
                order_id=order_id,
                error_code=str(result_code),
                error_message=f"پرداخت ایران کیش ناموفق بود (resultCode={result_code})",
                raw={"result_code": result_code},
            )

        token, reference_id = self._resolve_verify_params(authority, extra)

        payload = {
            "terminalId": str(self.config["terminal_id"]),
            "referenceId": reference_id,
            "token": token,
        }
        headers = {"Content-Type": "application/json"}
        result = self._post(self._confirm_url, json=payload, headers=headers)

        # status==true یعنی تأیید موفق (طبق کد مرجع verify.py)
        if result.get("status") is True:
            detail = result.get("result") or {}
            return PaymentResult(
                status=PaymentStatus.SUCCESS,
                gateway_slug=self.slug,
                order_id=order_id,
                reference_id=str(detail.get("retrievalReferenceNumber") or reference_id),
                amount=amount,
                card_number=detail.get("maskedPan") or detail.get("pan"),
                raw=result,
            )

        return PaymentResult(
            status=PaymentStatus.FAILED,
            gateway_slug=self.slug,
            order_id=order_id,
            error_code=str(result.get("responseCode") or result.get("status")),
            error_message=str(result.get("description") or "verify ناموفق"),
            raw=result,
        )