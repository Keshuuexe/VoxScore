"""
Loads secret configuration (SECRET_KEY, API keys, allowed hosts...) from the `.env` file.

`django-environ` reads key=value pairs from `.env` and exposes them as environment variables,
so secrets stay out of GitHub (`.env` is git-ignored), development and production can use
different values, and the same code runs everywhere.

If a required variable is missing, environ raises ImproperlyConfigured, so the project fails
loudly instead of running with a missing or default secret.
"""

from pathlib import Path

import environ

# The reader object. Settings files call env('NAME') to fetch values.
env = environ.Env()

# Project root = the folder that contains manage.py and .env.
# This file is at <project>/voxsite/secrets_environment.py, so two .parent calls reach it.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load <project>/.env into the environment.
environ.Env.read_env(BASE_DIR / ".env")
