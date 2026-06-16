"""
مسیرهای داخلی پکیج.

در urls.py پروژه:
    from django.urls import path, include
    urlpatterns = [
        path("payment/", include("django_iranian_payment.contrib.django.urls")),
    ]

سپس callback هر درگاه روی این آدرس می‌نشیند:
    https://yoursite.com/payment/callback/zarinpal/
"""

from django.urls import path

from . import views

app_name = "iranian_payment"

urlpatterns = [
    path("callback/<str:slug>/", views.callback, name="callback"),
    path("go/<int:payment_id>/", views.go_to_gateway, name="go-to-gateway"),
]
