"""ASGI config for the VoxScore project. Uses production settings unless told otherwise."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voxsite.settings.production')

application = get_asgi_application()
