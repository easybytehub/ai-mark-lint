"""The CLI: exit codes, output formats and usage errors."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

import pytest

from ai_mark_lint import __version__
from ai_mark_lint.catalogo import REGLAS
from tests.conftest import CA, FIX, ejecuta

SIN = str(FIX / "jpeg/sin-marcas.jpg")
COMPLETO = str(FIX / "jpeg/completo.jpg")


def test_warnings_do_not_fail_unless_strict(capsys: pytest.CaptureFixture[str]) -> None:
    assert ejecuta(capsys, SIN)[0] == 0
    assert ejecuta(capsys, SIN, "--strict")[0] == 1


def test_china_turns_absence_into_an_error(capsys: pytest.CaptureFixture[str]) -> None:
    codigo, out, _ = ejecuta(capsys, SIN, "--jurisdiction", "cn")
    assert codigo == 1 and "CN-45438-001" in out


def test_a_technical_error_fails_without_jurisdiction(capsys: pytest.CaptureFixture[str]) -> None:
    codigo, out, _ = ejecuta(capsys, str(FIX / "jpeg/c2pa-roto.jpg"), "--jurisdiction", "none")
    assert codigo == 1 and "C2PA-001" in out


def test_complete_and_trusted_is_clean_everywhere(capsys: pytest.CaptureFixture[str]) -> None:
    codigo, out, _ = ejecuta(
        capsys, COMPLETO, "--jurisdiction", "eu,ca,cn", "--trust-anchors", str(CA)
    )
    # Queda el aviso del sello de tiempo: sin una TSA real no se puede fabricar uno.
    assert codigo == 0 and "EU-COP-002" in out and "ERROR" not in out
    assert "WARNING" in out and "does not certify compliance" in out


@pytest.mark.parametrize(
    "argv",
    [
        ["--jurisdiction", "us"],
        [],
        ["--before", COMPLETO],
        ["--before", COMPLETO, "--after", SIN, SIN],
        ["does-not-exist.jpg"],
        [SIN, "--trust-anchors", "does-not-exist.pem"],
        [str(FIX / "otros/no-soportado.txt")],
        ["--before", str(FIX / "otros/no-soportado.txt"), "--after", SIN],
    ],
)
def test_usage_errors_exit_2(capsys: pytest.CaptureFixture[str], argv: list[str]) -> None:
    codigo, _, err = ejecuta(capsys, *argv)
    assert codigo == 2 and "ai-mark-lint: " in err


def test_unsupported_among_others_is_undetermined(capsys: pytest.CaptureFixture[str]) -> None:
    codigo, out, _ = ejecuta(capsys, SIN, str(FIX / "otros/no-soportado.txt"))
    assert codigo == 0 and "UNDETERMINED FMT-001" in out


def test_json(capsys: pytest.CaptureFixture[str]) -> None:
    codigo, out, _ = ejecuta(capsys, SIN, COMPLETO, "--format", "json", "--jurisdiction", "cn")
    datos = json.loads(out)
    assert codigo == 1
    assert datos["mode"] == "audit"
    assert datos["summary"] == {"errors": 1, "warnings": 0, "undetermined": 1}
    assert datos["jurisdictions"] == ["cn"]
    assert datos["marks"][COMPLETO] == {
        "c2pa": "valid",
        "c2pa_ai": True,
        "iptc-dst": ["http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"],
        "aigc": ["JPEG APP1 XMP TC260:AIGC"],
    }
    for h in datos["findings"]:
        assert set(h) == {"rule", "severity", "title", "detail", "citation", "url", "file"}
        assert h["severity"] in ("error", "warning", "undetermined")


def test_sarif_is_ingestible(capsys: pytest.CaptureFixture[str]) -> None:
    ficheros = [str(p) for p in sorted((FIX / "jpeg").glob("*.jpg"))]
    codigo, out, _ = ejecuta(capsys, *ficheros, "--format", "sarif", "--jurisdiction", "eu,ca,cn")
    sarif = json.loads(out)
    assert codigo == 1 and sarif["version"] == "2.1.0"
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["version"] == __version__
    ids = {r["id"] for r in run["tool"]["driver"]["rules"]}
    assert len(ids) == len(run["tool"]["driver"]["rules"])
    for r in run["results"]:
        assert r["ruleId"] in ids and r["ruleId"] in REGLAS
        assert r["level"] in ("error", "warning", "note")
        assert "Citation: " in r["message"]["text"]
        loc = r["locations"][0]["physicalLocation"]
        uri = loc["artifactLocation"]["uri"]
        # Las fixtures viven fuera del cwd: URI file:// absoluta.
        assert uri.startswith("file://") and Path(url2pathname(urlparse(uri).path)).exists()
        assert loc["region"]["startLine"] == 1


def test_before_after_from_the_cli(capsys: pytest.CaptureFixture[str]) -> None:
    codigo, out, _ = ejecuta(
        capsys, "--before", COMPLETO, "--after", str(FIX / "jpeg/procesado-recodificado.jpg")
    )
    assert codigo == 1 and "DIFF-001" in out and "before/after mode" in out
    assert "After: none." in out


def test_help_is_english(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as salida:
        ejecuta(capsys, "--help")
    assert salida.value.code == 0
    ayuda = capsys.readouterr().out
    for opcion in (
        "--jurisdiction",
        "--format",
        "--strict",
        "--before",
        "--after",
        "--trust-anchors",
        "--no-color",
        "Exit codes",
    ):
        assert opcion in ayuda


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as salida:
        ejecuta(capsys, "--version")
    assert salida.value.code == 0
    assert __version__ in capsys.readouterr().out
