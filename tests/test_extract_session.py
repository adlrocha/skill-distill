"""Tests for reading and locating agent session logs."""

import importlib.util
import json
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills/skill-distill/scripts/extract_session.py"
)
SPEC = importlib.util.spec_from_file_location("extract_session", SCRIPT)
assert SPEC and SPEC.loader
extract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(extract)


def test_first_cwd_handles_valid_bad_and_missing_logs(tmp_path: Path) -> None:
    path = tmp_path / "session.jsonl"
    path.write_text(json.dumps({"payload": {"cwd": str(tmp_path)}}) + "\n")
    assert extract._first_cwd(path) == str(tmp_path.resolve())
    path.write_text("not json\n")
    assert extract._first_cwd(path) is None
    path.unlink()
    assert extract._first_cwd(path) is None


def test_jsonl_skips_bad_records_and_summarizes_session(tmp_path: Path) -> None:
    path = tmp_path / "session.jsonl"
    rows = [
        {"type": "user", "message": {"content": "do a task"}},
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "done"}]},
        },
    ]
    path.write_text("bad json\n" + "\n".join(json.dumps(row) for row in rows) + "\n")
    summary = extract.summarize(path)
    assert summary["task"] == "do a task"
    assert summary["final"] == "done"
    assert "do a task" in extract.to_markdown(summary)


def test_finds_written_files_without_matching_reads() -> None:
    assert extract.files_from("Write", {"file_path": "src/main.py"}) == {"src/main.py"}
    assert extract.files_from("Read", {"file_path": "secret.txt"}) == set()
    assert extract.files_from("patch", "*** Add File: src/new.py") == {"src/new.py"}
