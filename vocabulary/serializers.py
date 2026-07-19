"""
vocabulary/serializers.py
=========================
DRF serializers covering four use-cases:

1. CollectionSerializer      — full collection representation
2. WordSerializer            — full word representation with absolute media URLs
3. WordContributionSerializer — write-only serializer for user submissions
4. SyncResponseSerializer    — envelope returned by the /sync/ endpoint;
                               combines collections + words + server_time
"""

from django.utils import timezone
from rest_framework import serializers

from .models import Collection, Word


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------
class CollectionSerializer(serializers.ModelSerializer):
    """Read-only serializer for Collection objects."""

    class Meta:
        model = Collection
        fields = [
            "id",
            "name_uz",
            "name_en",
            "is_default",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields  # All fields are read-only for public consumers


# ---------------------------------------------------------------------------
# Word
# ---------------------------------------------------------------------------
class WordSerializer(serializers.ModelSerializer):
    """
    Read serializer for Word objects.

    `image_url` and `audio_url` are computed fields that return absolute
    URLs so Flutter clients can download assets without knowing
    MEDIA_ROOT.  They return None when no file is attached.
    """

    image_url = serializers.SerializerMethodField(
        help_text="Absolute URL to the word's image, or null if not set."
    )
    audio_url = serializers.SerializerMethodField(
        help_text="Absolute URL to the pronunciation audio file, or null."
    )

    class Meta:
        model = Word
        fields = [
            "id",
            "collection",       # UUID of the parent collection
            "word_uz",
            "word_en",
            "image_url",
            "audio_url",
            "is_approved",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def _build_absolute_url(self, file_field) -> str | None:
        """Return an absolute URL for a FileField, or None if empty."""
        if not file_field:
            return None
        request = self.context.get("request")
        if request is not None:
            return request.build_absolute_uri(file_field.url)
        return file_field.url  # fallback: relative URL

    def get_image_url(self, obj: Word) -> str | None:
        return self._build_absolute_url(obj.image)

    def get_audio_url(self, obj: Word) -> str | None:
        return self._build_absolute_url(obj.audio)


# ---------------------------------------------------------------------------
# User contribution (write path)
# ---------------------------------------------------------------------------
class WordContributionSerializer(serializers.ModelSerializer):
    """
    Write serializer for authenticated users submitting new words.

    - `submitted_by` is injected by the view from `request.user`.
    - `is_approved` defaults to False so an admin must review the entry.
    - `collection` must be an existing Collection UUID.
    """

    class Meta:
        model = Word
        fields = [
            "id",
            "collection",
            "word_uz",
            "word_en",
            "image",
            "audio",
        ]
        read_only_fields = ["id"]

    def validate_collection(self, value: Collection) -> Collection:
        """Ensure users can only contribute to existing collections."""
        if not Collection.objects.filter(pk=value.pk).exists():
            raise serializers.ValidationError("Collection not found.")
        return value

    def create(self, validated_data: dict) -> Word:
        """Force `is_approved=False` for all user contributions."""
        validated_data["is_approved"] = False
        validated_data["submitted_by"] = self.context["request"].user
        return super().create(validated_data)


class CollectionContributionSerializer(serializers.ModelSerializer):
    """
    Write serializer for authenticated users creating new collections.

    `is_default` cannot be set by regular users — only admins can promote
    a collection to the default set via the Django admin.
    """

    class Meta:
        model = Collection
        fields = ["id", "name_uz", "name_en"]
        read_only_fields = ["id"]

    def create(self, validated_data: dict) -> Collection:
        """Force `is_default=False` so only admins can mark defaults."""
        validated_data["is_default"] = False
        return super().create(validated_data)


# ---------------------------------------------------------------------------
# Sync envelope
# ---------------------------------------------------------------------------
class SyncResponseSerializer(serializers.Serializer):
    """
    Serializer for the /sync/ endpoint response envelope.

    This is used purely for documentation / schema generation (e.g. drf-spectacular).
    The SyncView constructs the payload dict directly for performance;
    using this here keeps the contract explicit.

    Shape:
        {
            "server_time": "2024-01-15T10:30:00Z",   // ISO 8601 UTC timestamp
            "collections": [ CollectionSerializer ],
            "words":       [ WordSerializer ],
        }
    """

    server_time = serializers.DateTimeField(
        help_text="UTC timestamp of this response. Clients must store this "
                  "value and send it as `last_synced_at` in the next sync."
    )
    collections = CollectionSerializer(many=True)
    words = WordSerializer(many=True)
