"""
Production settings: used on the live server (e.g. PythonAnywhere).

Run locally to test production mode:
    python manage.py runserver --settings=voxsite.settings.production
(wsgi.py and asgi.py use this module by default.)
"""

from .base import *  # noqa: F401,F403
from voxsite.secrets_environment import env

DEBUG = False

# The deployed domain must be in ALLOWED_HOSTS in the server's .env, or Django answers every
# request with DisallowedHost.
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

# PythonAnywhere terminates HTTPS at its proxy and forwards plain HTTP with this header.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Log in, sign up and the AI forms are POSTs; Django checks their Origin on HTTPS.
CSRF_TRUSTED_ORIGINS = [
    f"https://{host}" for host in ALLOWED_HOSTS if not host.startswith(("*", "."))
]

# HTTPS-only cookies. Set HTTPS_ONLY=False only to try production mode on a laptop.
HTTPS_ONLY = env.bool('HTTPS_ONLY', default=True)
SESSION_COOKIE_SECURE = HTTPS_ONLY
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = HTTPS_ONLY
SECURE_SSL_REDIRECT = HTTPS_ONLY

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',  # noqa: F405
    }
}

# Hashed, cache-busted static filenames after `collectstatic`.
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'},
}
