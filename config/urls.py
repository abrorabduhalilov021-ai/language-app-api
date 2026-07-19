"""
config/urls.py
==============
Root URL configuration for the Language Learning API.

API versioning is baked into the URL prefix (/api/v1/) so future
versions can be added without breaking existing mobile clients.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    # Django admin site
    path("admin/", admin.site.urls),

    # -----------------------------------------------------------------------
    # JWT Authentication endpoints
    # POST /api/v1/auth/token/         → obtain access + refresh tokens
    # POST /api/v1/auth/token/refresh/ → exchange refresh token for new access token
    # -----------------------------------------------------------------------
    path(
        "api/v1/auth/token/",
        TokenObtainPairView.as_view(),
        name="token_obtain_pair",
    ),
    path(
        "api/v1/auth/token/refresh/",
        TokenRefreshView.as_view(),
        name="token_refresh",
    ),

    # -----------------------------------------------------------------------
    # Vocabulary app endpoints (collections, words, sync, contributions)
    # -----------------------------------------------------------------------
    path("api/v1/", include("vocabulary.urls")),
]

# ---------------------------------------------------------------------------
# Serve uploaded media files in development
# (In production, delegate to Nginx / CDN)
# ---------------------------------------------------------------------------
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
