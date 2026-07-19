"""
vocabulary/apps.py
==================
App configuration for the vocabulary app.
"""

from django.apps import AppConfig


class VocabularyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "vocabulary"
    verbose_name = "Vocabulary"
