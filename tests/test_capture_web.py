"""Tests for browser capture without requiring a browser or server."""

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1] / "skills/skill-distill/scripts/capture_web.py"
)
SPEC = importlib.util.spec_from_file_location("capture_web", SCRIPT)
assert SPEC and SPEC.loader
capture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capture)


def test_wait_http_closes_successful_response(monkeypatch: pytest.MonkeyPatch) -> None:
    closed: list[bool] = []

    class Response:
        def __enter__(self) -> "Response":  # noqa: PYI034  # Python 3.10
            return self

        def __exit__(self, *args: object) -> None:
            closed.append(True)

    monkeypatch.setattr(capture.urllib.request, "urlopen", lambda *a, **k: Response())
    assert capture.wait_http("http://example.test", 2)
    assert closed == [True]


def test_wait_http_times_out_after_network_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    times = iter([0, 0, 2])
    monkeypatch.setattr(capture.time, "time", lambda: next(times))
    monkeypatch.setattr(capture.time, "sleep", lambda seconds: None)

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("offline")

    monkeypatch.setattr(capture.urllib.request, "urlopen", fail)
    assert not capture.wait_http("http://example.test", 1)


def test_blank_closes_image(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    closed: list[bool] = []

    class Image:
        def __enter__(self) -> "Image":  # noqa: PYI034  # Python 3.10
            return self

        def __exit__(self, *args: object) -> None:
            closed.append(True)

        def convert(self, mode: str) -> "Image":
            return self

        def resize(self, size: tuple[int, int]) -> "Image":
            return self

    pil = types.ModuleType("PIL")
    pil.Image = types.SimpleNamespace(open=lambda path: Image())
    pil.ImageStat = types.SimpleNamespace(
        Stat=lambda image: types.SimpleNamespace(stddev=[1])
    )
    monkeypatch.setitem(sys.modules, "PIL", pil)
    assert capture.blank(tmp_path / "image.png")
    assert closed == [True]


def test_capture_records_action_errors_and_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BrowserError(Exception):
        pass

    class Page:
        def on(self, *args: object) -> None:
            pass

        def goto(self, *args: object, **kwargs: object) -> None:
            pass

        def screenshot(self, path: str) -> None:
            Path(path).touch()

        def get_by_text(self, text: str) -> object:
            raise BrowserError("not found")

    class Browser:
        def new_page(self, **kwargs: object) -> Page:
            return Page()

        def close(self) -> None:
            pass

    class Playwright:
        chromium = types.SimpleNamespace(launch=lambda **kw: Browser())

        def __enter__(self) -> "Playwright":  # noqa: PYI034  # Python 3.10
            return self

        def __exit__(self, *args: object) -> None:
            pass

    playwright = types.ModuleType("playwright")
    api = types.ModuleType("playwright.sync_api")
    api.Error = BrowserError
    api.sync_playwright = lambda: Playwright()
    monkeypatch.setitem(sys.modules, "playwright", playwright)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", api)
    monkeypatch.setattr(capture, "free_port", lambda: 12345)
    monkeypatch.setattr(capture, "wait_http", lambda url, secs: True)
    monkeypatch.setattr(capture, "blank", lambda path: False)
    monkeypatch.setattr(
        capture.subprocess, "Popen", lambda *a, **k: types.SimpleNamespace(pid=123)
    )
    killed: list[int] = []
    monkeypatch.setattr(capture.os, "killpg", lambda pid, sig: killed.append(pid))
    actions = tmp_path / "actions.json"
    actions.write_text(json.dumps([{"shot": "load"}, {"click_text": "missing"}]))
    out = tmp_path / "out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "capture",
            "--dir",
            str(tmp_path),
            "--out",
            str(out),
            "--actions",
            str(actions),
        ],
    )
    assert capture.main() == 0
    assert killed == [123]
    result = json.loads((out / "capture.json").read_text())
    assert result["ok"] and "not found" in result["errors"][0]
