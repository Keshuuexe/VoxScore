"""
Development settings: used on a developer's own machine.

Run with the default:   python manage.py runserver
(manage.py points at this module unless told otherwise.)
"""

# Start from everything in base.py, then override what differs for development.
from .base import *  # noqa: F401,F403

# SECURITY WARNING: DEBUG=True shows detailed error pages. True ONLY here.
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Local SQLite file in the project root. Like Unopsis, this file IS committed, so a fresh
# clone already has the warmup library and the demo account.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',  # noqa: F405
    }
}
