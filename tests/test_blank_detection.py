"""Tier-2 deterministic blank detection on real firm conventions (FR-5.1)."""
from app.blank_detection import normalize
from app.templates import detect_fields, fill_text, prepare_template


def test_underscore_run_becomes_named_blank():
    canonical, fields, cands = normalize("Affiant residing at ____________ states:")
    assert len(fields) == 1
    assert "{{" in canonical and "}}" in canonical
    assert cands[0].source == "underscore"
    # The key is derived from preceding context, not a generic field_N.
    assert "resid" in fields[0].key


def test_label_colon_pair():
    canonical, fields, _ = normalize("Case No. :")
    assert [f.key for f in fields] == ["case_no"]
    assert canonical.strip() == "Case No. : {{case_no}}"


def test_checkbox_becomes_enum_blank():
    _canon, fields, cands = normalize("[ ] U.S. Mail   [ ] Personal")
    assert len(fields) == 2
    assert cands[0].source == "checkbox"
    assert "yes or no" in (fields[0].instruction or "") or fields[0].instruction == "select yes/no"


def test_sentinel_name_keys_itself():
    _canon, fields, _ = normalize("NAME, Affiant")
    assert fields[0].key == "name"


def test_real_firm_template_no_longer_detects_zero():
    # A snippet using none of the mustache markup — the exact gap from
    # docs/blank-detection.md where real templates scored 0 blanks.
    firm = (
        "Case No. :\n"
        "STATE OF ____________\n"
        "NAME, being duly sworn, states he is ____ years old.\n"
        "[ ] U.S. Mail   [ ] Personal\n"
    )
    assert detect_fields(firm) == []          # old detector: zero
    canonical, fields = prepare_template(firm)
    assert len(fields) >= 5                    # new detector: several
    # And the canonical text is fillable by the existing engine.
    filled = fill_text(canonical, {f.key: "X" for f in fields})
    assert "{{" not in filled


def test_keys_are_unique():
    _canon, fields, _ = normalize("____ and ____ and ____")
    keys = [f.key for f in fields]
    assert len(keys) == len(set(keys))
