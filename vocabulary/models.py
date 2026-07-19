"""
vocabulary/models.py
====================
Core data models for the Language Learning API.

Design decisions:
- Both models use an explicit `updated_at` db_index so the sync query
  (WHERE updated_at > last_synced_at) hits the index instead of doing
  a sequential scan — critical for performance as the dataset grows.
- `is_default` on Collection marks system-curated content (Alphabet,
  Numbers, etc.) that is always included in a full (no-timestamp) sync.
- `is_approved` on Word supports an optional admin-moderation workflow
  for user-contributed content without breaking the public read path.
- UUIDs are used as primary keys to make offline-generated IDs
  collision-safe and to avoid exposing sequential database IDs.
"""

import uuid

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class Collection(models.Model):
    """
    A thematic group of vocabulary words (e.g. Alphabet, Numbers, Colors).

    The `is_default` flag distinguishes system-created collections from
    user-contributed ones so the sync endpoint can return a guaranteed
    base dataset on a fresh client install.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Globally unique identifier — safe to generate offline.",
    )
    name_uz = models.CharField(
        max_length=255,
        verbose_name="Name (Uzbek)",
        help_text="Collection name in Uzbek.",
    )
    name_en = models.CharField(
        max_length=255,
        verbose_name="Name (English)",
        help_text="Collection name in English.",
    )
    is_default = models.BooleanField(
        default=False,
        db_index=True,
        help_text=(
            "True for system-defined collections (Alphabet, Numbers, etc.). "
            "These are included in every full sync for new clients."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(
        auto_now=True,
        db_index=True,  # ← enables fast timestamp-based sync filtering
        help_text="Automatically updated on every save. Used as the sync cursor.",
    )

    class Meta:
        ordering = ["-is_default", "name_en"]
        verbose_name = "Collection"
        verbose_name_plural = "Collections"
        indexes = [
            # Composite index: filters on is_default + updated_at together
            # which is the exact query pattern used by the sync endpoint.
            models.Index(fields=["is_default", "updated_at"], name="coll_default_updated_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name_en} / {self.name_uz}"


class Word(models.Model):
    """
    A single vocabulary entry belonging to a Collection.

    Media fields (image, audio) store files under MEDIA_ROOT.  The
    serializer exposes full URLs so Flutter clients can download assets.

    `is_approved` enables an admin-moderation gate on user contributions
    without affecting the public read API (unapproved words are filtered
    out in the view layer).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    collection = models.ForeignKey(
        Collection,
        on_delete=models.CASCADE,
        related_name="words",
        db_index=True,
    )
    word_uz = models.CharField(
        max_length=255,
        verbose_name="Word (Uzbek)",
    )
    word_en = models.CharField(
        max_length=255,
        verbose_name="Word (English)",
    )
    image = models.ImageField(
        upload_to="words/images/%Y/%m/",
        blank=True,
        null=True,
        help_text="Optional illustration for the word.",
    )
    audio = models.FileField(
        upload_to="words/audio/%Y/%m/",
        blank=True,
        null=True,
        help_text="Pronunciation audio file (mp3 / ogg).",
    )
    # --- Moderation ---
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_words",
        help_text="The user who submitted this word (null for seeded data).",
    )
    is_approved = models.BooleanField(
        default=True,
        db_index=True,
        help_text=(
            "Approved words are visible to all clients. "
            "Set to False to hold a user submission for review."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(
        auto_now=True,
        db_index=True,  # ← sync cursor index
    )

    class Meta:
        ordering = ["word_en"]
        verbose_name = "Word"
        verbose_name_plural = "Words"
        indexes = [
            # Sync query: WHERE is_approved=True AND updated_at > ?
            models.Index(
                fields=["is_approved", "updated_at"],
                name="word_approved_updated_idx",
            ),
            # Collection lookup: WHERE collection_id = ? AND is_approved = True
            models.Index(
                fields=["collection", "is_approved"],
                name="word_collection_approved_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.word_en} / {self.word_uz} ({self.collection.name_en})"
