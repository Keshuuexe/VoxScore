"""
Settings shared by every environment (development and production).

Anything that differs between environments (DEBUG, ALLOWED_HOSTS, DATABASES) lives in
development.py or production.py, which start with `from .base import *`.
"""

from pathlib import Path

# The `.env` reader (see voxsite/secrets_environment.py). Secrets never appear in code.
from voxsite.secrets_environment import env

# SECURITY: the signing key comes from .env, never from source control.
# The project refuses to start if SECRET_KEY is missing.
SECRET_KEY = env('SECRET_KEY')

# This file lives at <project>/voxsite/settings/base.py, so three .parent calls reach the
# folder with manage.py.
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # VoxScore's one domain app: practice tools, warmups, studio (scores and parts),
    # theory tutor, profile and progress, and the AI layer in voxscore/ai/.
    'voxscore',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'voxsite.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Project-level templates/ folder (templates/base.html, templates/voxscore/...).
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'voxsite.wsgi.application'


# ---------------------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------------------
# Route NAMES, not paths, so moving a page in voxscore/urls.py never breaks these.
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'home'

# No mail server: anything Django tries to email is printed to the console instead of
# raising mid-request.
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/Chicago'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# One project-level static/ folder, namespaced by type:
#     static/css/voxscore.css    the site stylesheet
#     static/js/audio.js         shared browser audio: pitch detection, metronome, drone, synth
#     static/js/<page>.js        one script per interactive screen
# Templates always use {% static '...' %}, never a hard-coded /static/ path.

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ---------------------------------------------------------------------------------------
# AI features (see README_AI.md and voxscore/ai/)
# ---------------------------------------------------------------------------------------
# External API: Groq's OpenAI-compatible chat API (free tier). Key from console.groq.com/keys.
# Used by the theory tutor, the practice coach and the optional harmony assistant. Without a
# key every feature falls back to a rule-based answer, so the site still works.
GROQ_API_KEY = env('GROQ_API_KEY', default='')
GROQ_MODEL = env('GROQ_MODEL', default='openai/gpt-oss-20b')
GROQ_TIMEOUT_SECONDS = env.int('GROQ_TIMEOUT_SECONDS', default=20)

# Local Hugging Face model, loaded lazily with `transformers` the first time it is needed.
# Off by default: it needs torch (pip install -r requirements-ai.txt) and several GB of RAM.
# When on, the tutor tries the local model if Groq is unavailable.
AI_LOCAL_MODEL = env('AI_LOCAL_MODEL', default='ibm-granite/granite-3.3-2b-instruct')
AI_LOCAL_ENABLED = env.bool('AI_LOCAL_ENABLED', default=False)
AI_LOCAL_MAX_NEW_TOKENS = env.int('AI_LOCAL_MAX_NEW_TOKENS', default=220)
AI_LOCAL_MAX_SECONDS = env.int('AI_LOCAL_MAX_SECONDS', default=60)
AI_LOCAL_CPU_DTYPE = env('AI_LOCAL_CPU_DTYPE', default='bfloat16')

# Guardrail: model runs per signed-in account per minute, across every AI feature.
AI_REQUESTS_PER_MINUTE = env.int('AI_REQUESTS_PER_MINUTE', default=10)
