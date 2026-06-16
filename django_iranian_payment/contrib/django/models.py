"""
مدل Payment — لایه‌ی اختیاری Django.

این مدل state تراکنش را نگه می‌دارد تا کاربر مجبور نباشد خودش authority را
ذخیره و ردیابی کند. حالت‌ها از تجربه‌ی واقعی درگاه‌های ایرانی گرفته شده‌اند
(الگوگرفته از az-iranian-bank-gateways):

    WAITING              → رکورد ساخته شد، هنوز به بانک نرفته
    REDIRECT_TO_BANK     → کاربر به درگاه هدایت شد
    RETURN_FROM_BANK     → از بانک برگشت ولی verify هنوز کامل/موفق نشده
    COMPLETE             → پرداخت تأیید و نهایی شد
    CANCEL_BY_USER       → کاربر بدون پرداخت برگشت
    EXPIRE_GATEWAY_TOKEN → به درگاه نرفت و توکن منقضی شد
    EXPIRE_VERIFY        → در بازه‌ی مجاز پس از بازگشت، verify موفق نشد

مبلغ‌ها همه به ریال‌اند. amount = مبلغ پایه، amount_sent = مبلغی که واقعاً به
بانک رفت (با کارمزد). همان amount_sent باید در verify استفاده شود.
"""

from django.db import models
from django.utils import timezone


class PaymentStatus(models.TextChoices):
    WAITING = "waiting", "در انتظار"
    REDIRECT_TO_BANK = "redirect", "هدایت به بانک"
    RETURN_FROM_BANK = "returned", "بازگشت از بانک"
    COMPLETE = "complete", "تکمیل‌شده"
    CANCEL_BY_USER = "cancelled", "لغو توسط کاربر"
    EXPIRE_GATEWAY_TOKEN = "expire_token", "انقضای توکن درگاه"
    EXPIRE_VERIFY = "expire_verify", "انقضای تأیید"


class PaymentQuerySet(models.QuerySet):
    def returned_unverified(self):
        """رکوردهایی که از بانک برگشته‌اند ولی هنوز تأیید نشده‌اند."""
        return self.filter(status=PaymentStatus.RETURN_FROM_BANK)

    def stale_redirects(self, older_than_minutes=15):
        """رکوردهایی که به درگاه رفته‌اند ولی خیلی وقت است برنگشته‌اند."""
        cutoff = timezone.now() - timezone.timedelta(minutes=older_than_minutes)
        return self.filter(
            status__in=[PaymentStatus.WAITING, PaymentStatus.REDIRECT_TO_BANK],
            created_at__lt=cutoff,
        )


class Payment(models.Model):
    gateway_slug = models.CharField(max_length=32, db_index=True)
    order_id = models.CharField(max_length=128, db_index=True)

    amount = models.BigIntegerField(help_text="مبلغ پایه‌ی سفارش (ریال)")
    fee = models.BigIntegerField(default=0, help_text="کارمزد محاسبه‌شده (ریال)")
    amount_sent = models.BigIntegerField(
        default=0, help_text="مبلغ واقعی ارسالی به بانک با کارمزد (ریال)"
    )

    status = models.CharField(
        max_length=16,
        choices=PaymentStatus.choices,
        default=PaymentStatus.WAITING,
        db_index=True,
    )

    authority = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="توکن بازگشتی از بانک در initiate",
    )
    redirect_url = models.URLField(
        max_length=1000,
        blank=True,
        help_text="آدرس درگاه برای هدایت کاربر (پس از initiate)",
    )
    reference_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="شماره‌ی پیگیری بانک پس از verify",
    )
    card_number = models.CharField(max_length=32, blank=True)

    callback_url = models.URLField(max_length=500)
    description = models.CharField(max_length=255, blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    error_code = models.CharField(max_length=64, blank=True)
    error_message = models.TextField(blank=True)
    raw = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PaymentQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["gateway_slug", "authority"]),
        ]

    def __str__(self):
        return f"Payment[{self.gateway_slug}] {self.order_id} = {self.get_status_display()}"

    @property
    def is_success(self):
        return self.status == PaymentStatus.COMPLETE

    def mark(self, status, **fields):
        """تغییر حالت + ذخیره‌ی اتمیک فیلدهای همراه."""
        self.status = status
        for key, value in fields.items():
            setattr(self, key, value)
        update_fields = ["status", "updated_at", *fields.keys()]
        self.save(update_fields=update_fields)
