"""Mustache template detection and filling (FR-4, FR-5, FR-8)."""
from app.templates import detect_fields, fill_text, humanize, prepare_template


def test_detects_both_markups_and_instruction():
    text = "Dear {{client_name}}, re {{ caption | title case }} and [[case_number]]."
    fields = detect_fields(text)
    keys = [f.key for f in fields]
    assert keys == ["client_name", "caption", "case_number"]
    caption = next(f for f in fields if f.key == "caption")
    assert caption.instruction == "title case"


def test_dedupes_repeated_keys_in_first_seen_order():
    fields = detect_fields("{{a}} {{b}} {{a}}")
    assert [f.key for f in fields] == ["a", "b"]


def test_humanize():
    assert humanize("client_name") == "Client Name"
    assert humanize("dateOfDeath") == "Date Of Death"


def test_fill_text_marks_missing_as_needs_review():
    out = fill_text("{{a}} and {{b}}", {"a": "X"})
    assert "X and" in out
    assert "[[NEEDS REVIEW: B]]" in out


def test_prepare_template_prefers_mustache_when_present():
    text = "{{client_name}} pays ____."
    canonical, fields = prepare_template(text)
    # Mustache markup wins; the underscore is NOT additionally normalized.
    assert canonical == text
    assert [f.key for f in fields] == ["client_name"]
