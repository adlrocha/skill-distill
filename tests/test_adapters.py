"""Exercise harness adapters with fake commands rather than real model runs."""

import json
import os
import subprocess
from pathlib import Path

import pytest

ADAPTERS = Path(__file__).resolve().parents[1] / "skills/skill-distill/adapters"


@pytest.mark.parametrize("harness", ["claude", "codex", "omp", "opencode", "pi"])
@pytest.mark.parametrize("status", [0, 7])
@pytest.mark.parametrize("student_args", ["--extra *", ""])
def test_adapter_passes_arguments_and_preserves_exit(
    tmp_path: Path, harness: str, status: int, student_args: str
) -> None:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake = bindir / harness
    fake.write_text("""#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
pathlib.Path(os.environ["ARGS_FILE"]).write_text(json.dumps(args))
if "--session-dir" in args:
    d = pathlib.Path(args[args.index("--session-dir") + 1])
    d.mkdir(parents=True, exist_ok=True)
    (d / "session.jsonl").write_text('{"type":"session"}\\n')
print('{"message":{"content":[]},"item":{}}')
sys.exit(int(os.environ["FAKE_STATUS"]))
""")
    fake.chmod(0o755)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "not-a-flag").touch()
    trace = tmp_path / "trace"
    trace.mkdir()
    prompt = tmp_path / "prompt"
    prompt.write_text("a prompt with spaces")
    args_file = tmp_path / "args.json"
    env = os.environ | {
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "WORKSPACE": str(workspace),
        "TRACE_DIR": str(trace),
        "PROMPT_FILE": str(prompt),
        "MODEL": "example/model",
        "STUDENT_ARGS": student_args,
        "ARGS_FILE": str(args_file),
        "FAKE_STATUS": str(status),
    }
    result = subprocess.run(
        ["bash", str(ADAPTERS / f"{harness}.sh")],
        cwd=workspace,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == status, result.stderr
    args = json.loads(args_file.read_text())
    assert args[-1] == "a prompt with spaces"
    if student_args:
        assert args[-3:-1] == ["--extra", "*"]
    assert (trace / "session.jsonl").is_file()
