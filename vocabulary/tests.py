"""
vocabulary/tests.py
===================
Unit and integration tests for the Language Learning API.

Run with:
    python manage.py test vocabulary
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from .models import Collection, Word

User = get_user_model()


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def make_collection(name_en="Test Collection", name_uz="Test Uzbek", is_default=True, **kwargs) -> Collection:
    return Collection.objects.create(
        name_en=name_en, name_uz=name_uz, is_default=is_default, **kwargs
    )


def make_word(collection: Collection, word_en="hello", word_uz="salom", **kwargs) -> Word:
    return Word.objects.create(
        collection=collection, word_en=word_en, word_uz=word_uz, is_approved=True, **kwargs
    )


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class CollectionModelTest(TestCase):

    def test_str_representation(self):
        col = make_collection(name_en="Numbers", name_uz="Raqamlar")
        self.assertEqual(str(col), "Numbers / Raqamlar")

    def test_uuid_primary_key(self):
        col = make_collection()
        self.assertIsNotNone(col.id)
        self.assertEqual(len(str(col.id)), 36)  # standard UUID string length

    def test_updated_at_auto_updates(self):
        col = make_collection()
        first_ts = col.updated_at
        col.name_en = "Updated Name"
        col.save()
        self.assertGreater(col.updated_at, first_ts)


class WordModelTest(TestCase):

    def setUp(self):
        self.collection = make_collection()

    def test_str_representation(self):
        word = make_word(self.collection, word_en="Apple", word_uz="Olma")
        self.assertIn("Apple", str(word))

    def test_default_is_approved_true(self):
        word = make_word(self.collection)
        self.assertTrue(word.is_approved)

    def test_cascade_delete_removes_words(self):
        make_word(self.collection)
        collection_id = self.collection.id
        self.collection.delete()
        self.assertEqual(Word.objects.filter(collection_id=collection_id).count(), 0)


# ---------------------------------------------------------------------------
# Sync endpoint tests
# ---------------------------------------------------------------------------

class SyncViewTest(APITestCase):
    """
    Tests for GET /api/v1/sync/ — the core offline-first sync endpoint.
    """

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("sync")

        # Create a default collection with words
        self.col_default = make_collection(name_en="Alphabet", is_default=True)
        self.word_a = make_word(self.col_default, word_en="A a", word_uz="A a")
        self.word_b = make_word(self.col_default, word_en="B b", word_uz="B b")

        # Create a non-default collection (should NOT appear in full sync)
        self.col_user = make_collection(name_en="Colors", is_default=False)
        self.word_c = make_word(self.col_user, word_en="Red", word_uz="Qizil")

    def test_full_sync_returns_envelope_keys(self):
        """Full sync response must contain server_time, collections, and words."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("server_time", response.data)
        self.assertIn("collections", response.data)
        self.assertIn("words", response.data)

    def test_full_sync_returns_only_default_collections(self):
        """Without last_synced_at, only is_default=True collections are returned."""
        response = self.client.get(self.url)
        collection_ids = [c["id"] for c in response.data["collections"]]
        self.assertIn(str(self.col_default.id), collection_ids)
        self.assertNotIn(str(self.col_user.id), collection_ids)

    def test_full_sync_words_belong_to_default_collection(self):
        """Words returned in full sync must belong to default collections."""
        response = self.client.get(self.url)
        word_ids = [w["id"] for w in response.data["words"]]
        self.assertIn(str(self.word_a.id), word_ids)
        self.assertNotIn(str(self.word_c.id), word_ids)  # non-default collection

    def test_delta_sync_returns_empty_when_nothing_changed(self):
        """Delta sync with a future timestamp must return empty lists."""
        future_ts = "2099-01-01T00:00:00Z"
        response = self.client.get(self.url, {"last_synced_at": future_ts})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["collections"], [])
        self.assertEqual(response.data["words"], [])

    def test_delta_sync_returns_only_changed_records(self):
        """Delta sync with a past timestamp must return all records (all are new)."""
        past_ts = "2000-01-01T00:00:00Z"
        response = self.client.get(self.url, {"last_synced_at": past_ts})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Both collections should appear since both are newer than 2000-01-01
        self.assertGreaterEqual(len(response.data["collections"]), 1)
        self.assertGreaterEqual(len(response.data["words"]), 1)

    def test_unapproved_words_excluded_from_sync(self):
        """Words with is_approved=False must never appear in sync responses."""
        unapproved = make_word(self.col_default, word_en="Hidden", word_uz="Yashirin")
        unapproved.is_approved = False
        unapproved.save()

        response = self.client.get(self.url)
        word_ids = [w["id"] for w in response.data["words"]]
        self.assertNotIn(str(unapproved.id), word_ids)

    def test_server_time_is_iso8601(self):
        """server_time in the response must be a parseable ISO 8601 timestamp."""
        from datetime import datetime
        response = self.client.get(self.url)
        ts_str = response.data["server_time"]
        # Should not raise
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        self.assertIsNotNone(dt)

    def test_invalid_timestamp_treated_as_full_sync(self):
        """An unparseable last_synced_at falls back to a full sync."""
        response = self.client.get(self.url, {"last_synced_at": "not-a-date"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should behave like a full sync — returns default collections
        self.assertGreaterEqual(len(response.data["collections"]), 1)


# ---------------------------------------------------------------------------
# Collection & Word ViewSet tests
# ---------------------------------------------------------------------------

class CollectionViewSetTest(APITestCase):

    def setUp(self):
        self.col = make_collection(name_en="Numbers", is_default=True)
        make_word(self.col, word_en="One", word_uz="Bir")

    def test_list_collections(self):
        response = self.client.get(reverse("collection-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_collection(self):
        response = self.client.get(reverse("collection-detail", args=[self.col.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name_en"], "Numbers")

    def test_collection_words_action(self):
        response = self.client.get(reverse("collection-words", args=[self.col.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)


# ---------------------------------------------------------------------------
# Contribution endpoint tests
# ---------------------------------------------------------------------------

class ContributeWordTest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user("testuser", password="pass1234!")
        self.collection = make_collection()
        self.url = reverse("contribute-word")

    def test_anonymous_cannot_contribute(self):
        data = {
            "collection": str(self.collection.id),
            "word_uz": "Olma",
            "word_en": "Apple",
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_submit_word(self):
        self.client.force_authenticate(user=self.user)
        data = {
            "collection": str(self.collection.id),
            "word_uz": "Olma",
            "word_en": "Apple",
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_contributed_word_defaults_to_unapproved(self):
        self.client.force_authenticate(user=self.user)
        data = {
            "collection": str(self.collection.id),
            "word_uz": "Nok",
            "word_en": "Pear",
        }
        self.client.post(self.url, data)
        word = Word.objects.get(word_en="Pear")
        self.assertFalse(word.is_approved)

    def test_contributed_word_links_to_submitter(self):
        self.client.force_authenticate(user=self.user)
        data = {
            "collection": str(self.collection.id),
            "word_uz": "Gilos",
            "word_en": "Cherry",
        }
        self.client.post(self.url, data)
        word = Word.objects.get(word_en="Cherry")
        self.assertEqual(word.submitted_by, self.user)
