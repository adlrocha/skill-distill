"""Tests for the distillation run manager's subprocess handling."""

import argparse
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "skills/skill-distill/scripts/distill.py"
SPEC = importlib.util.spec_from_file_location("distill", SCRIPT)
assert SPEC and SPEC.loader
distill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(distill)


def test_sh_returns_nonzero_results_for_caller_to_handle() -> None:
    result = distill.sh(["bash", "-c", "printf error >&2; exit 7"])
    assert result.returncode == 7
    assert result.stderr == "error"
    with pytest.raises(subprocess.CalledProcessError):
        distill.sh(["bash", "-c", "exit 7"], check=True)


def test_template_is_not_discovered_as_an_installed_skill() -> None:
    skill_dir = SCRIPT.parent.parent
    assert distill.TEMPLATE.name == "SKILL.md.tmpl"
    assert distill.TEMPLATE.is_file()
    assert sorted(skill_dir.rglob("SKILL.md")) == [skill_dir / "SKILL.md"]


def test_init_builds_a_student_skill_from_the_template(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("build the thing")
    run = tmp_path / "run"
    args = argparse.Namespace(
        run=str(run),
        force=False,
        student="pi:example-model",
        base="empty",
        name="student-task",
        student_args="",
        env=[],
        setup="",
        tmux="",
        timeout_min=10,
        reference="",
        reference_workspace="",
        prompt=str(prompt),
    )
    distill.cmd_init(args)
    generated = (run / "skill/SKILL.md").read_text()
    assert "name: student-task" in generated
    assert "example-model" in generated
    assert "{{name}}" not in generated
    assert "{{model}}" not in generated
    assert "{{harness}}" not in generated
    assert (run / "prompt.md").read_text() == "build the thing"


def test_collect_records_check_exit_and_output(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    ws.mkdir()
    distill.sh(["git", "init", "-q"], cwd=ws)
    (ws / "file.txt").write_text("hello")
    checks = tmp_path / "checks.sh"
    checks.write_text("echo checked; echo failure >&2; exit 3\n")
    out = tmp_path / "evidence"
    assert distill.collect(ws, out, checks) == 3
    assert "checked" in (out / "checks.log").read_text()
    assert "failure" in (out / "checks.log").read_text()
    assert json.loads((out / "summary.json").read_text())["checks_exit"] == 3
