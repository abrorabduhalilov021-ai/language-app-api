"""
vocabulary/migrations/0002_seed_default_data.py
================================================
Data migration that populates the database with the initial seed content:

    1. Alphabet (Alfavit) — Full Uzbek Latin alphabet (A–Z + Uzbek-specific letters)
       with sample image/audio URL patterns for each letter.

    2. Numbers (Raqamlar) — Numbers 1–20 in Uzbek and English.

This migration is idempotent: it uses `get_or_create` so running it
more than once (or after a reset) will not produce duplicates.

Media note:
    The `image_url` and `audio_url` values below are placeholder patterns.
    Replace them with your CDN base URL or leave blank and upload files
    via the Django admin / management command.
"""

from django.db import migrations

# ---------------------------------------------------------------------------
# Seed data constants
# ---------------------------------------------------------------------------

ALPHABET_COLLECTION = {
    "name_uz": "Alfavit",
    "name_en": "Alphabet",
    "is_default": True,
}

NUMBERS_COLLECTION = {
    "name_uz": "Raqamlar",
    "name_en": "Numbers",
    "is_default": True,
}

# Full Uzbek Latin alphabet (29 letters as used in modern Uzbek orthography)
# Each entry: (letter_uz, letter_en, transliteration_note)
ALPHABET_WORDS = [
    ("A a", "A a", "a"),
    ("B b", "B b", "b"),
    ("D d", "D d", "d"),
    ("E e", "E e", "e"),
    ("F f", "F f", "f"),
    ("G g", "G g", "g"),
    ("H h", "H h", "h"),
    ("I i", "I i", "i"),
    ("J j", "J j", "j"),
    ("K k", "K k", "k"),
    ("L l", "L l", "l"),
    ("M m", "M m", "m"),
    ("N n", "N n", "n"),
    ("O o", "O o", "o"),
    ("P p", "P p", "p"),
    ("Q q", "Q q", "q"),
    ("R r", "R r", "r"),
    ("S s", "S s", "s"),
    ("T t", "T t", "t"),
    ("U u", "U u", "u"),
    ("V v", "V v", "v"),
    ("X x", "X x", "kh"),
    ("Y y", "Y y", "y"),
    ("Z z", "Z z", "z"),
    ("O' o'", "O' o'", "o (rounded)"),
    ("G' g'", "G' g'", "gh (voiced velar fricative)"),
    ("Sh sh", "Sh sh", "sh"),
    ("Ch ch", "Ch ch", "ch"),
    ("Ng ng", "Ng ng", "ng (nasal)"),
]

# Numbers 1–20 in Uzbek
NUMBERS_WORDS = [
    ("Bir", "One", 1),
    ("Ikki", "Two", 2),
    ("Uch", "Three", 3),
    ("To'rt", "Four", 4),
    ("Besh", "Five", 5),
    ("Olti", "Six", 6),
    ("Yetti", "Seven", 7),
    ("Sakkiz", "Eight", 8),
    ("To'qqiz", "Nine", 9),
    ("O'n", "Ten", 10),
    ("O'n bir", "Eleven", 11),
    ("O'n ikki", "Twelve", 12),
    ("O'n uch", "Thirteen", 13),
    ("O'n to'rt", "Fourteen", 14),
    ("O'n besh", "Fifteen", 15),
    ("O'n olti", "Sixteen", 16),
    ("O'n yetti", "Seventeen", 17),
    ("O'n sakkiz", "Eighteen", 18),
    ("O'n to'qqiz", "Nineteen", 19),
    ("Yigirma", "Twenty", 20),
]


# ---------------------------------------------------------------------------
# Migration functions
# ---------------------------------------------------------------------------

def seed_default_data(apps, schema_editor):
    """Create default collections and seed words."""
    Collection = apps.get_model("vocabulary", "Collection")
    Word = apps.get_model("vocabulary", "Word")

    # ------------------------------------------------------------------
    # 1. Alphabet collection
    # ------------------------------------------------------------------
    alphabet_col, _ = Collection.objects.get_or_create(
        name_en=ALPHABET_COLLECTION["name_en"],
        defaults={
            "name_uz": ALPHABET_COLLECTION["name_uz"],
            "is_default": True,
        },
    )

    for letter_uz, letter_en, _ in ALPHABET_WORDS:
        Word.objects.get_or_create(
            collection=alphabet_col,
            word_uz=letter_uz,
            defaults={
                "word_en": letter_en,
                "is_approved": True,
                # Placeholder URL pattern — swap for real CDN paths
                # e.g. "https://cdn.yourapp.com/alphabet/a.png"
                "image": "",
                "audio": "",
            },
        )

    # ------------------------------------------------------------------
    # 2. Numbers collection
    # ------------------------------------------------------------------
    numbers_col, _ = Collection.objects.get_or_create(
        name_en=NUMBERS_COLLECTION["name_en"],
        defaults={
            "name_uz": NUMBERS_COLLECTION["name_uz"],
            "is_default": True,
        },
    )

    for word_uz, word_en, _ in NUMBERS_WORDS:
        Word.objects.get_or_create(
            collection=numbers_col,
            word_uz=word_uz,
            defaults={
                "word_en": word_en,
                "is_approved": True,
                "image": "",
                "audio": "",
            },
        )


def unseed_default_data(apps, schema_editor):
    """Remove seed data (allows reversing the migration cleanly)."""
    Collection = apps.get_model("vocabulary", "Collection")
    Collection.objects.filter(
        name_en__in=[
            ALPHABET_COLLECTION["name_en"],
            NUMBERS_COLLECTION["name_en"],
        ]
    ).delete()  # CASCADE removes associated words


class Migration(migrations.Migration):
    """Data migration: seed default Alphabet and Numbers collections."""

    dependencies = [
        # This migration depends on the initial schema migration
        ("vocabulary", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            seed_default_data,
            reverse_code=unseed_default_data,
        ),
    ]
