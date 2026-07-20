"""
app سبک «فقط گارد پیکربندی» — بدون model و migration.

برای حالت مدیریت دستی DB (که اپ کامل contrib.django را به INSTALLED_APPS اضافه
نمی‌کنی): این اپ فقط system check درگاه‌های بدون sandbox را ثبت می‌کند تا اگر
سامان/ملت در حالت sandbox باشند، manage.py/runserver در startup با خطا متوقف شود.

    INSTALLED_APPS = [
        ...
        "django_iranian_payment.contrib.guard",
    ]

اگر اپ کامل contrib.django را داری، همان چک را دارد و به این اپ نیازی نیست (ثبت
دوباره‌ی همان تابع بی‌اثر است چون رجیستری چک‌ها مجموعه است).

AppConfig در apps.py است و Django (3.2+) خودکار کشفش می‌کند؛ default_app_config لازم
نیست (منسوخ).
"""
