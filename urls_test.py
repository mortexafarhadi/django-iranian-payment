# urlconf تستی: مسیرهای پکیج را mount می‌کند
from django.urls import path, include

urlpatterns = [
    path("payment/", include("django_iranian_payment.contrib.django.urls")),
]
