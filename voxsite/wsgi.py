"""WSGI config for the VoxScore project. Uses production settings unless told otherwise."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voxsite.settings.production')

application = get_wsgi_application()
