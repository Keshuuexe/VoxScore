"""
URL configuration for the VoxScore project.

Every VoxScore route lives in voxscore/urls.py; this file only mounts it next to the admin.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('voxscore.urls')),
]
