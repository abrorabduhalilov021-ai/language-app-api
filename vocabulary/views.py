"""
vocabulary/views.py
===================
API views for the Language Learning backend.

Endpoints exposed:
    GET  /api/v1/sync/                 — Timestamp-based delta sync (public)
    GET  /api/v1/collections/          — List all collections (public)
    GET  /api/v1/collections/<id>/     — Retrieve a single collection (public)
    GET  /api/v1/collections/<id>/words/ — Words in a collection (public)
    GET  /api/v1/words/                — List all approved words (public)
    GET  /api/v1/words/<id>/           — Retrieve a single word (public)
    POST /api/v1/contribute/words/     — Submit a new word (authenticated)
    POST /api/v1/contribute/collections/ — Submit a new collection (authenticated)
"""

import logging
from datetime import datetime, timezone as dt_timezone

from django.utils import timezone
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Collection, Word
from .serializers import (
    CollectionContributionSerializer,
    CollectionSerializer,
    WordContributionSerializer,
    WordSerializer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _parse_timestamp(raw: str | None) -> datetime | None:
    """
    Parse an ISO 8601 timestamp string into a timezone-aware datetime.

    Accepts both:
      - "2024-01-15T10:30:00Z"         (UTC 'Z' suffix)
      - "2024-01-15T10:30:00+00:00"    (explicit offset)
      - Unix epoch seconds as a string

    Returns None if the value is absent, empty, or unparseable.
    """
    if not raw:
        return None

    # Attempt ISO 8601 parse (handles Z and offset variants)
    try:
        ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        # Ensure the datetime is timezone-aware (UTC)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=dt_timezone.utc)
        return ts
    except ValueError:
        pass

    # Fallback: treat as Unix epoch seconds
    try:
        ts = datetime.fromtimestamp(float(raw), tz=dt_timezone.utc)
        return ts
    except (ValueError, OSError):
        pass

    logger.warning("Could not parse last_synced_at value: %r", raw)
    return None


# ---------------------------------------------------------------------------
# Sync endpoint (core of the offline-first architecture)
# ---------------------------------------------------------------------------

class SyncView(APIView):
    """
    GET /api/v1/sync/?last_synced_at=<ISO8601_timestamp>

    Delta synchronisation endpoint for offline-first Flutter clients.

    ── Behaviour ──────────────────────────────────────────────────────────────
    • No  `last_synced_at`  → Full sync: returns ALL default collections and
      their approved words.  Intended for brand-new installs.

    • With `last_synced_at` → Delta sync: returns only collections and words
      where `updated_at > last_synced_at`.  This means the client only
      downloads records that changed since its last successful sync.

    ── Response shape ─────────────────────────────────────────────────────────
    {
        "server_time":   "2024-01-15T10:30:00.123456Z",  // store as next cursor
        "collections":   [ { ...CollectionSerializer... } ],
        "words":         [ { ...WordSerializer... } ],
    }

    ── Client instructions ────────────────────────────────────────────────────
    1. On first launch, call /sync/ with no parameter.
    2. Persist `server_time` from the response locally.
    3. On subsequent syncs, pass the stored `server_time` as `last_synced_at`.
    4. UPSERT all returned collections and words into local SQLite.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request: Request) -> Response:

        # ------------------------------------------------------------------
        # 1. Capture server time BEFORE querying to avoid a TOCTOU race where
        #    a record is written between the query and the timestamp capture.
        # ------------------------------------------------------------------
        server_time: datetime = timezone.now()

        # ------------------------------------------------------------------
        # 2. Parse the sync cursor
        # ------------------------------------------------------------------
        raw_ts: str | None = request.query_params.get("last_synced_at")
        last_synced_at: datetime | None = _parse_timestamp(raw_ts)

        # ------------------------------------------------------------------
        # 3. Build optimised querysets
        # ------------------------------------------------------------------
        if last_synced_at is None:
            # ── Full sync ─────────────────────────────────────────────────
            # Return only is_default=True collections (system-curated data).
            # This keeps the initial download small while still giving a new
            # client everything it needs to be useful offline.
            logger.info("Full sync requested (no last_synced_at)")
            collections_qs = Collection.objects.filter(is_default=True)
            words_qs = Word.objects.filter(
                collection__is_default=True,
                is_approved=True,
            ).select_related("collection")
        else:
            # ── Delta sync ────────────────────────────────────────────────
            logger.info("Delta sync requested — cursor: %s", last_synced_at.isoformat())

            # Any collection touched after the cursor (regardless of is_default)
            # so user-contributed collections are also synced once approved.
            collections_qs = Collection.objects.filter(
                updated_at__gt=last_synced_at
            )

            # Any approved word touched after the cursor
            words_qs = Word.objects.filter(
                updated_at__gt=last_synced_at,
                is_approved=True,
            ).select_related("collection")

        # ------------------------------------------------------------------
        # 4. Serialise
        # ------------------------------------------------------------------
        collection_data = CollectionSerializer(
            collections_qs, many=True, context={"request": request}
        ).data

        word_data = WordSerializer(
            words_qs, many=True, context={"request": request}
        ).data

        # ------------------------------------------------------------------
        # 5. Return the envelope
        # ------------------------------------------------------------------
        payload = {
            "server_time": server_time.isoformat(),
            "collections": collection_data,
            "words": word_data,
        }

        logger.info(
            "Sync response — collections: %d, words: %d",
            len(collection_data),
            len(word_data),
        )
        return Response(payload, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Collection ViewSet (read-only public access)
# ---------------------------------------------------------------------------

class CollectionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    list   → GET  /api/v1/collections/
    retrieve → GET /api/v1/collections/<id>/
    words  → GET  /api/v1/collections/<id>/words/
    """

    serializer_class = CollectionSerializer
    permission_classes = [permissions.AllowAny]
    queryset = Collection.objects.all()

    @action(detail=True, methods=["get"], url_path="words")
    def words(self, request: Request, pk: str | None = None) -> Response:
        """Return all approved words for a specific collection."""
        collection = self.get_object()
        words_qs = collection.words.filter(is_approved=True)
        serializer = WordSerializer(words_qs, many=True, context={"request": request})
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Word ViewSet (read-only public access)
# ---------------------------------------------------------------------------

class WordViewSet(viewsets.ReadOnlyModelViewSet):
    """
    list   → GET /api/v1/words/
    retrieve → GET /api/v1/words/<id>/

    Only approved words are surfaced via the public API.
    """

    serializer_class = WordSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = Word.objects.filter(is_approved=True).select_related("collection")
        # Optional ?collection=<uuid> filter for client-side browsing
        collection_id = self.request.query_params.get("collection")
        if collection_id:
            qs = qs.filter(collection_id=collection_id)
        return qs


# ---------------------------------------------------------------------------
# User contribution endpoints (authenticated write access)
# ---------------------------------------------------------------------------

class ContributeWordView(generics.CreateAPIView):
    """
    POST /api/v1/contribute/words/

    Authenticated users can submit a new word for admin review.
    The word is created with `is_approved=False` by default.

    Request body (multipart/form-data for file uploads):
        collection  — UUID of existing collection
        word_uz     — Uzbek word / phrase
        word_en     — English translation
        image       — (optional) image file
        audio       — (optional) audio file
    """

    serializer_class = WordContributionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(submitted_by=self.request.user, is_approved=False)


class ContributeCollectionView(generics.CreateAPIView):
    """
    POST /api/v1/contribute/collections/

    Authenticated users can propose a new collection.
    Created with `is_default=False`; admin promotes via Django admin.

    Request body (application/json):
        name_uz — Collection name in Uzbek
        name_en — Collection name in English
    """

    serializer_class = CollectionContributionSerializer
    permission_classes = [permissions.IsAuthenticated]
