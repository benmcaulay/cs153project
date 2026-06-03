"""Retrieval fallback (FR-3), export (FR-10), and reporting (FR-14)."""
from app.export import export_docx
from app.ingest import Chunk
from app.models import FilledField, FillResult, ModelStyleStats
from app.reporting import model_style_report
from app.retrieval import Retriever
from app.store import RUNS_DIR


def test_lexical_retrieval_finds_relevant_chunk():
    chunks = [
        Chunk(document="a.txt", text="The decedent died on January 28, 2024.", index=0),
        Chunk(document="b.txt", text="The weather was sunny and mild all week.", index=1),
    ]
    r = Retriever(chunks)  # no embed model => lexical TF-IDF
    assert r.mode == "lexical"
    top = r.retrieve("date of death of the decedent", k=1)
    assert top and top[0].document == "a.txt"


def test_export_docx_produces_a_valid_file_with_notice():
    fields = [
        FilledField(key="a", label="A", value="X", found=True, source_quote="X here", source_document="d.txt"),
        FilledField(key="b", label="B", value="NEEDS_REVIEW", found=False),
    ]
    data = export_docx("Test", "X and [[NEEDS REVIEW: B]]", fields)
    assert data[:2] == b"PK"          # .docx is a zip
    assert len(data) > 500


def test_model_style_report_aggregates_flags(tmp_path, monkeypatch):
    import app.store as store

    monkeypatch.setattr(store, "RUNS_DIR", str(tmp_path))
    monkeypatch.setattr("app.reporting.list_runs", store.list_runs)

    run = FillResult(
        run_id="r1", matter_id="m", matter_name="M", template_id="t", template_name="T",
        style="litigation", model="llama3.1:8b", inference_seconds=2.0,
        fields=[
            FilledField(key="a", label="A", value="X", found=True, admin_flag="correct"),
            FilledField(key="b", label="B", value="Y", found=True, admin_flag="incorrect"),
            FilledField(key="c", label="C", value="NEEDS_REVIEW", found=False),
        ],
    ).recount()
    store.save_run(run)

    report = model_style_report()
    row = next(r for r in report if r.model == "llama3.1:8b" and r.style == "litigation")
    assert row.fields_flagged == 2
    assert row.fields_correct == 1
    assert row.accuracy == 0.5
    assert row.needs_review_fields == 1
    assert row.avg_inference_seconds == 2.0
