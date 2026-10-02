"""The catalogue, SPEC.md and action.yml must not drift apart."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from ai_mark_lint.catalogo import REGLAS
from ai_mark_lint.hallazgos import Severidad

RAIZ = Path(__file__).parent.parent
SPEC = (RAIZ / "SPEC.md").read_text(encoding="utf-8")


def _secciones() -> dict[str, str]:
    partes = re.split(r"^### ", SPEC, flags=re.M)[1:]
    return {p.split()[0]: p for p in partes}


def test_spec_and_catalogue_have_the_same_rules() -> None:
    assert set(_secciones()) == set(REGLAS)


def test_every_spec_rule_has_literal_source_date_and_severity() -> None:
    for rid, texto in _secciones().items():
        regla = REGLAS[rid]
        assert f"**Severity:** {regla.severidad.value}" in texto, rid
        assert (
            texto.split("\n")[0]
            .split(" — ", 1)[1]
            .strip()
            .startswith(regla.titulo.replace(" [unverified]", ""))
        ), rid
        if rid.startswith(("FMT", "XMP")):
            continue
        assert "**Literal:**" in texto, rid
        assert "**Source:**" in texto and "accessed 2026-10-02" in texto, rid
        assert "**How it is checked:**" in texto, rid


def test_unverified_in_spec_matches_the_catalogue() -> None:
    for rid, texto in _secciones().items():
        primera = texto.splitlines()[0]
        assert ("[unverified]" in primera) is (not REGLAS[rid].verificada), rid


def test_no_unverified_rule_is_an_error() -> None:
    for r in REGLAS.values():
        assert r.verificada or r.severidad is not Severidad.ERROR


def test_no_private_key_in_the_repository() -> None:
    """La CA de prueba se crea en tiempo de test (tests/fabrica.py): en el árbol no puede
    quedar ninguna clave, ni siquiera de prueba, que dispare el escaneo de secretos."""
    fuera = {".venv", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"}
    marca = b"PRIVATE" + b" KEY-----"  # partida para que este fichero no se delate a sí mismo
    for p in RAIZ.rglob("*"):
        if not p.is_file() or fuera & set(p.relative_to(RAIZ).parts):
            continue
        assert p.suffix not in (".key", ".pem", ".p8", ".p12"), f"key/cert file: {p}"
        assert marca not in p.read_bytes(), p


FIJADA = re.compile(r"uses: ([\w./-]+)@([0-9a-f]{40})  # v\d+\.\d+\.\d+$", re.M)


def test_action_installs_from_its_own_code() -> None:
    accion = yaml.safe_load((RAIZ / "action.yml").read_text(encoding="utf-8"))
    assert accion["runs"]["using"] == "composite"
    instalar = [p for p in accion["runs"]["steps"] if "pip install" in p.get("run", "")]
    assert len(instalar) == 1 and "github.action_path" in instalar[0]["run"]
    assert "ai-mark-lint==" not in (RAIZ / "action.yml").read_text(encoding="utf-8")
    assert {
        "files",
        "before",
        "after",
        "jurisdiction",
        "format",
        "strict",
        "fail",
        "trust-anchors",
        "output",
        "python-version",
    } == set(accion["inputs"])


def test_every_third_party_action_is_pinned_by_sha_with_its_exact_version() -> None:
    for fichero in ("action.yml", ".github/workflows/ci.yml", ".github/workflows/release.yml"):
        texto = (RAIZ / fichero).read_text(encoding="utf-8")
        usos = [u for u in re.findall(r"uses: (\S+)", texto) if not u.startswith("./")]
        assert usos, fichero
        assert len(FIJADA.findall(texto)) == len(usos), fichero


def test_ci_action_job_skips_fork_pull_requests() -> None:
    ci = yaml.safe_load((RAIZ / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    assert ci["jobs"]["action"]["if"] == (
        "github.event_name == 'push' || "
        "github.event.pull_request.head.repo.full_name == github.repository"
    )


def test_release_gates_pypi_on_the_repository_variable() -> None:
    rel = yaml.safe_load((RAIZ / ".github/workflows/release.yml").read_text(encoding="utf-8"))
    pasos = rel["jobs"]["publish"]["steps"]
    pypi = [p for p in pasos if "pypa/gh-action-pypi-publish" in p.get("uses", "")]
    aviso = [p for p in pasos if "GITHUB_STEP_SUMMARY" in p.get("run", "")]
    assert pypi[0]["if"] == "vars.PYPI_TRUSTED_PUBLISHER == 'listo'"
    assert aviso[0]["if"] == "vars.PYPI_TRUSTED_PUBLISHER != 'listo'"
    assert rel["jobs"]["publish"]["environment"] == "release"
    assert rel["permissions"] == {"contents": "read"}


def test_pyproject_classifiers() -> None:
    texto = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    assert "License ::" not in texto  # PEP 639: la licencia va en `license`
    assert "Programming Language :: Python :: 3.14" in texto
    assert "Operating System :: OS Independent" in texto
