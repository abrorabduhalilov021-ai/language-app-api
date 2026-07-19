"""
vocabulary/admin.py
===================
Django Admin configuration for the vocabulary app.

Provides an ergonomic interface for:
- Browsing and moderating user-contributed words (approve with one click)
- Managing collections and promoting them to default status
- Inline word editing directly from a collection's detail page
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import Collection, Word


class WordInline(admin.TabularInline):
    """Allows editing words directly from the Collection admin page."""

    model = Word
    extra = 0
    fields = ["word_uz", "word_en", "is_approved", "audio", "image"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ["name_en", "name_uz", "is_default", "word_count", "updated_at"]
    list_filter = ["is_default"]
    search_fields = ["name_en", "name_uz"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [WordInline]

    @admin.display(description="Word Count")
    def word_count(self, obj: Collection) -> int:
        return obj.words.filter(is_approved=True).count()


@admin.register(Word)
class WordAdmin(admin.ModelAdmin):
    list_display = [
        "word_en", "word_uz", "collection",
        "is_approved", "submitted_by", "image_preview", "updated_at",
    ]
    list_filter = ["is_approved", "collection"]
    search_fields = ["word_en", "word_uz"]
    readonly_fields = ["id", "submitted_by", "created_at", "updated_at", "image_preview"]
    list_editable = ["is_approved"]  # ← approve/reject in bulk from list view
    actions = ["approve_words", "reject_words"]

    @admin.display(description="Image")
    def image_preview(self, obj: Word):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height:60px; border-radius:4px;" />',
                obj.image.url,
            )
        return "—"

    @admin.action(description="Approve selected words")
    def approve_words(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f"{updated} word(s) approved.")

    @admin.action(description="Reject / hide selected words")
    def reject_words(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f"{updated} word(s) rejected.")
