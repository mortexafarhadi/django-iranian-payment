import django
from django.conf import settings


def pytest_configure():
    settings.configure(
        DEBUG=True,
        DATABASES={
            "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
        },
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
            "django_iranian_payment.contrib.django",
        ],
        IRANIAN_PAYMENT={
            "sandbox": True,
            "gateways": {
                "zarinpal": {"merchant_id": "test-merchant"},
            },
        },
        USE_TZ=True,
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        ROOT_URLCONF="urls_test",
    )
    django.setup()
