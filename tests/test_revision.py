"""Regresiones de la revisión adversarial de la v0.1.0: un test por hallazgo.

Los ficheros públicos de c2pa-rs están en `fixtures/c2pa-rs/` (ver su README); el resto
se construye aquí, en bytes, para que cada caso quede a la vista.
"""

from __future__ import annotations

import builtins
import json
import struct
from dataclasses import replace
from pathlib import Path

import c2pa
import pytest

from ai_mark_lint import cli, contenedores, lector_c2pa
from ai_mark_lint.catalogo import REGLAS
from ai_mark_lint.comparacion import compara
from ai_mark_lint.hallazgos import Severidad
from ai_mark_lint.lector_c2pa import C2paInfo
from ai_mark_lint.marcas import Marcas, inventaria
from ai_mark_lint.reglas import audita
from tests import fabrica
from tests.conftest import FIX, ejecuta

RS = FIX / "c2pa-rs"
TODAS = ("eu", "ca", "cn")
IPTC = "http://cv.iptc.org/newscodes/digitalsourcetype/"


def _reglas(m: Marcas, js: tuple[str, ...] = TODAS) -> dict[str, Severidad]:
    return {h.regla: h.severidad for h in audita(m, js)}


# --- 1. Excepciones sin capturar ---------------------------------------------------------


def test_riff_bomb_does_not_exhaust_the_stack(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dentro = b""
    for _ in range(1000):
        dentro = b"LIST" + struct.pack("<I", 4 + len(dentro)) + b"INFO" + dentro
    wav = b"RIFF" + struct.pack("<I", 4 + len(dentro)) + b"WAVE" + dentro
    ex = contenedores.extrae(wav)
    assert ex is not None and any("nested LIST" in a for a in ex.anomalias)
    (tmp_path / "bomba.wav").write_bytes(wav)
    codigo, out, err = ejecuta(capsys, str(tmp_path / "bomba.wav"))
    assert codigo == 0 and "Traceback" not in err and "FMT-002" in out


def test_short_id3_extended_header() -> None:
    ex = contenedores.extrae(b"ID3\x03\x00\x40\x00\x00\x00\x00x")
    assert ex is not None and "extended header" in ex.anomalias[0]


def test_unreadable_file_is_reported_and_the_rest_is_checked(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from ai_mark_lint.marcas import inventaria as real

    def falla(ruta: Path, anclas: str | None = None) -> Marcas:
        if ruta.name == "c2pa-ia.jpg":
            raise PermissionError(13, "Permission denied")
        return real(ruta, anclas)

    monkeypatch.setattr(cli, "inventaria", falla)
    codigo, out, err = ejecuta(
        capsys, str(FIX / "jpeg/c2pa-ia.jpg"), str(FIX / "jpeg/sin-marcas.jpg"), "--format", "json"
    )
    datos = json.loads(out)
    assert codigo == 2 and "could not be read" in err
    reglas = {(h["rule"], Path(h["file"]).name) for h in datos["findings"]}
    assert ("FMT-003", "c2pa-ia.jpg") in reglas and ("EU-50-2-001", "sin-marcas.jpg") in reglas


def test_missing_file_in_a_list_does_not_abort(capsys: pytest.CaptureFixture[str]) -> None:
    codigo, out, _ = ejecuta(capsys, "no-such.jpg", str(FIX / "jpeg/sin-marcas.jpg"))
    assert codigo == 2 and "FMT-003" in out and "EU-50-2-001" in out


@pytest.mark.parametrize(
    "contenido", ["not a pem\n", "-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----\n"]
)
def test_invalid_trust_anchors_exit_2(
    tmp_path: Path, contenido: str, capsys: pytest.CaptureFixture[str]
) -> None:
    pem = tmp_path / "bad.pem"
    pem.write_text(contenido)
    codigo, _, err = ejecuta(capsys, str(FIX / "jpeg/c2pa-ia.jpg"), "--trust-anchors", str(pem))
    assert codigo == 2 and "invalid trust anchors" in err and "Traceback" not in err


def test_safety_net_turns_any_crash_into_exit_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def revienta(*_: object) -> list[object]:
        raise RuntimeError("boom\nsecond line")

    monkeypatch.setattr(cli, "audita", revienta)
    codigo, _, err = ejecuta(capsys, str(FIX / "jpeg/sin-marcas.jpg"))
    assert codigo == 2
    assert err.strip() == "ai-mark-lint: internal error: RuntimeError: boom"


# --- 2. C2PA-001 en ficheros sin C2PA ------------------------------------------------------


def test_library_error_without_c2pa_signature_is_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    def lector(*_: object, **__: object) -> object:
        raise c2pa.C2paError.Other("asset could not be parsed: Boxes are too deply nested")

    monkeypatch.setattr(c2pa, "Reader", lector)
    m = inventaria(FIX / "jpeg/sin-marcas.jpg")
    assert m.c2pa.estado == "ausente"
    reglas = _reglas(m)
    assert "C2PA-001" not in reglas and reglas["FMT-002"] is Severidad.AVISO


def test_raw_scan_needs_the_jumbf_c2pa_signature() -> None:
    suelto = b"\xff\xd8\xff" + b"jumb ... c2pa ... self#jumbf=/c2pa/urn:uuid:x"
    assert not contenedores.extrae(suelto).rastro_c2pa  # type: ignore[union-attr]
    firma = b"\xff\xd8\xff" + contenedores.FIRMA_C2PA
    assert contenedores.extrae(firma).rastro_c2pa  # type: ignore[union-attr]


def test_orphan_xmp_provenance_is_not_a_manifest() -> None:
    m = inventaria(RS / "no_manifest.jpg")
    assert m.c2pa.estado == "ausente" and "C2PA-001" not in _reglas(m)
    hallazgos = compara(inventaria(RS / "C.jpg"), m, TODAS)
    assert {h.regla for h in hallazgos} == {"DIFF-001"}


# --- 3. Códigos *.untrusted y cawg.* -------------------------------------------------------


@pytest.mark.parametrize(
    ("codigos", "estado", "confiable", "cawg"),
    [
        (["signingCredential.untrusted", "cawg.x509.credential.untrusted"], "valido", False, ()),
        (["timeStamp.untrusted"], "valido", False, ()),
        (
            ["cawg.identity.signature.mismatch"],
            "valido",
            True,
            ("cawg.identity.signature.mismatch",),
        ),
        (["assertion.dataHash.mismatch", "cawg.x"], "invalido", True, ("cawg.x",)),
    ],
)
def test_trust_and_cawg_codes(
    codigos: list[str], estado: str, confiable: bool, cawg: tuple[str, ...]
) -> None:
    datos = {
        "active_manifest": "m",
        "manifests": {"m": {"claim_version": 2, "assertions": []}},
        "validation_status": [{"code": c} for c in codigos],
    }
    info = lector_c2pa.interpreta(datos, "Invalid")
    assert info.estado == estado and info.no_confiable is not confiable
    assert info.fallos_cawg == cawg
    reglas = _reglas(Marcas("x.jpg", "jpeg", info), ())
    assert ("C2PA-002" in reglas) is (estado == "invalido")
    assert ("C2PA-009" in reglas) is bool(cawg)


def test_cawg_untrusted_file_is_not_invalid() -> None:
    reglas = _reglas(inventaria(RS / "C_with_CAWG_data.jpg"), ())
    assert "C2PA-002" not in reglas and reglas["C2PA-003"] is Severidad.INCOMPLETO


# --- 4. UserComment libre ------------------------------------------------------------------


@pytest.mark.parametrize(
    "comentario", ["Shot on film, no AIGC used", '{"AIGC" broken', '{"note": "AIGC not used"}']
)
def test_free_text_user_comment_is_not_an_aigc_label(tmp_path: Path, comentario: str) -> None:
    jpeg = (FIX / "jpeg/sin-marcas.jpg").read_bytes()
    f = tmp_path / "c.jpg"
    f.write_bytes(fabrica.jpeg_app1(jpeg, b"Exif\x00\x00" + fabrica.exif_user_comment(comentario)))
    m = inventaria(f)
    assert m.aigc == [] and "CN-45438-002" not in _reglas(m)


# --- 5. DIFF-003 / DIFF-007 ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("antes", "despues", "esperado"),
    [
        (["trainedAlgorithmicMedia"], [], {"DIFF-003"}),
        (["trainedAlgorithmicMedia"], ["digitalCapture"], {"DIFF-003"}),
        (["trainedAlgorithmicMedia"], ["compositeWithTrainedAlgorithmicMedia"], {"DIFF-007"}),
        (["trainedAlgorithmicMedia"], ["trainedAlgorithmicMedia", "compositeSynthetic"], set()),
        (["digitalCapture"], ["screenCapture"], {"DIFF-007"}),
    ],
)
def test_iptc_change_severity(antes: list[str], despues: list[str], esperado: set[str]) -> None:
    def m(tipos: list[str]) -> Marcas:
        return Marcas(
            "x.jpg",
            "jpeg",
            C2paInfo("ausente"),
            tipos_fuente_xmp=[("xmp", IPTC + t) for t in tipos],
        )

    hallazgos = compara(m(antes), m(despues), TODAS)
    assert {h.regla for h in hallazgos} == esperado
    sev = {h.regla: h.severidad for h in hallazgos}
    assert sev.get("DIFF-003", Severidad.ERROR) is Severidad.ERROR
    assert sev.get("DIFF-007", Severidad.AVISO) is Severidad.AVISO


# --- 6. Regla de oro -----------------------------------------------------------------------


def test_only_unverified_rules_cite_annex_e() -> None:
    for r in REGLAS.values():
        if "Annex E" in r.norma:
            assert not r.verificada and r.severidad is not Severidad.ERROR, r.id
    assert REGLAS["CN-45438-003"].severidad is Severidad.AVISO
    assert not REGLAS["CN-45438-003"].verificada


# --- 7. Update Manifests -------------------------------------------------------------------


def test_update_manifest_is_exempt_from_18_14_2() -> None:
    datos = {
        "active_manifest": "m",
        "manifests": {
            "m": {
                "claim_version": 2,
                "assertions": [
                    {"label": "c2pa.actions.v2", "data": {"actions": [{"action": "c2pa.edited"}]}}
                ],
            }
        },
    }
    actualizacion = {
        "active_manifest": "m",
        "manifests": {"m": {"assertion_store": {"c2pa.ingredient.v3": {}, "c2pa.actions": {}}}},
    }
    normal = {
        "active_manifest": "m",
        "manifests": {"m": {"assertion_store": {"c2pa.hash.data": {}, "c2pa.actions": {}}}},
    }
    info = lector_c2pa.interpreta(datos, "Valid", actualizacion)
    assert info.actualizacion and "C2PA-004" not in _reglas(Marcas("x", "jpeg", info), ())
    info = lector_c2pa.interpreta(datos, "Valid", normal)
    assert "C2PA-004" in _reglas(Marcas("x", "jpeg", info), ())
    assert inventaria(RS / "update_manifest.jpg").c2pa.actualizacion


# --- 8. La librería nativa no carga --------------------------------------------------------


def test_native_library_failing_to_load(monkeypatch: pytest.MonkeyPatch) -> None:
    original = builtins.__import__

    def falla(nombre: str, *a: object, **kw: object) -> object:
        if nombre == "c2pa":
            raise OSError("dlopen failed")
        return original(nombre, *a, **kw)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", falla)
    info = lector_c2pa.lee(FIX / "jpeg/c2pa-ia.jpg", rastro=True)
    assert info.estado == "sin_libreria"
    m = Marcas("x.jpg", "jpeg", info)
    detalle = next(h.detalle for h in audita(m, ("ca",)) if h.regla == "CA-942-001")
    assert "could not be checked" in detalle and "No readable C2PA manifest" in detalle


# --- Menores -------------------------------------------------------------------------------


def test_sarif_uri_relative_to_cwd(monkeypatch: pytest.MonkeyPatch) -> None:
    from ai_mark_lint.salida import _uri

    monkeypatch.chdir(FIX)
    assert _uri(str(FIX / "jpeg" / "a b.jpg")) == "jpeg/a b.jpg"
    assert _uri("rel/x.jpg") == "rel/x.jpg"
    assert _uri("/elsewhere/x y.jpg").endswith("/elsewhere/x%20y.jpg")
    assert _uri("/elsewhere/x y.jpg").startswith("file:///")


def test_new_rules_keep_their_severity() -> None:
    assert REGLAS["FMT-003"].severidad is Severidad.INCOMPLETO
    assert REGLAS["C2PA-009"].severidad is Severidad.AVISO and not REGLAS["C2PA-009"].verificada
    assert replace(REGLAS["DIFF-007"]).severidad is Severidad.AVISO
