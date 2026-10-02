"""Las reglas, fixture a fixture y con inventarios construidos a mano.

La tabla `ESPERADO` es la especificación ejecutable: para cada fichero, el conjunto
EXACTO de reglas que debe disparar con las tres jurisdicciones. Una regla que deja de
disparar, o una que empieza a disparar donde no debe, rompe aquí.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from ai_mark_lint import lector_c2pa
from ai_mark_lint.hallazgos import Severidad
from ai_mark_lint.lector_c2pa import C2paInfo
from ai_mark_lint.marcas import Marcas, inventaria
from ai_mark_lint.metadatos import interpreta_aigc
from ai_mark_lint.reglas import audita
from tests.conftest import CA, FIX

TODAS = ("eu", "ca", "cn")
CA_SIN_SISTEMA = {"CA-942-003", "CA-942-004"}

ESPERADO: dict[str, set[str]] = {
    "jpeg/sin-marcas.jpg": {"EU-50-2-001", "CA-942-001", "CN-45438-001"},
    "jpeg/c2pa-ia.jpg": {"C2PA-003", "EU-COP-002", "CN-45438-001"},
    "jpeg/c2pa-ia-eku-c2pa.jpg": {"C2PA-003", "EU-COP-002", "CN-45438-001"},
    "jpeg/completo.jpg": {"C2PA-003", "EU-COP-002"},
    "jpeg/c2pa-captura.jpg": {"C2PA-003", "EU-50-2-001", "CN-45438-001"},
    "jpeg/c2pa-dst-raro.jpg": {"C2PA-003", "C2PA-006", "EU-50-2-001", "CN-45438-001"},
    "jpeg/c2pa-sin-dst.jpg": {"C2PA-002", "C2PA-005", "EU-50-2-001", "CN-45438-001"},
    "jpeg/c2pa-manipulado.jpg": {"C2PA-002", "EU-COP-001", "CN-45438-001"},
    "jpeg/c2pa-roto.jpg": {"C2PA-001", "EU-50-2-001", "CA-942-001", "CN-45438-001"},
    "jpeg/contradiccion.jpg": {"C2PA-003", "MARK-001", "EU-COP-001", "CN-45438-001"},
    "jpeg/iptc-ia.jpg": {"EU-COP-001", "CA-942-002", *CA_SIN_SISTEMA, "CN-45438-001"},
    "jpeg/iptc-codigo-suelto.jpg": {
        "IPTC-001",
        "EU-50-2-001",
        "CA-942-002",
        *CA_SIN_SISTEMA,
        "CN-45438-001",
    },
    "jpeg/aigc-exif.jpg": {"EU-COP-001", *CA_SIN_SISTEMA},
    "jpeg/xmp-roto.jpg": {"XMP-001", "EU-50-2-001", "CA-942-001", "CN-45438-001"},
    "png/aigc.png": {"EU-COP-001", *CA_SIN_SISTEMA},
    "png/c2pa-ia.png": {"C2PA-003", "EU-COP-002", "CN-45438-001"},
    "png/iptc-ia.png": {"EU-COP-001", "CA-942-002", *CA_SIN_SISTEMA, "CN-45438-001"},
    "png/aigc-doble.png": {"EU-COP-001", *CA_SIN_SISTEMA, "CN-45438-006"},
    "png/aigc-json-roto.png": {
        "EU-50-2-001",
        "CA-942-002",
        *CA_SIN_SISTEMA,
        "CA-942-005",
        "CN-45438-002",
    },
    "png/aigc-incompleto.png": {"EU-COP-001", *CA_SIN_SISTEMA, "CA-942-005", "CN-45438-003"},
    "png/aigc-label-raro.png": {"EU-COP-001", *CA_SIN_SISTEMA, "CN-45438-004"},
    "png/aigc-dos-distintas.png": {"EU-COP-001", *CA_SIN_SISTEMA, "CN-45438-005"},
    "webp/c2pa-ia.webp": {"C2PA-003", "EU-COP-002", "CN-45438-001"},
    "webp/iptc-aigc.webp": {"EU-COP-001", *CA_SIN_SISTEMA},
    "wav/aigc.wav": {"EU-COP-001", *CA_SIN_SISTEMA},
    "wav/aigc-list-info.wav": {"EU-COP-001", *CA_SIN_SISTEMA},
    "wav/c2pa-ia.wav": {"C2PA-003", "EU-COP-002", "CN-45438-001"},
    "mp3/aigc.mp3": {"EU-COP-001", *CA_SIN_SISTEMA},
    "mp3/c2pa-ia.mp3": {"C2PA-003", "EU-COP-002", "CN-45438-001"},
    "mp4/aigc.mp4": {"EU-COP-001", *CA_SIN_SISTEMA},
    "mp4/c2pa-ia.mp4": {"C2PA-003", "EU-COP-002", "CN-45438-001"},
}


@pytest.mark.parametrize("nombre", sorted(ESPERADO))
def test_cada_fixture_dispara_exactamente_sus_reglas(nombre: str) -> None:
    hallazgos = audita(inventaria(FIX / nombre), TODAS)
    assert {h.regla for h in hallazgos} == ESPERADO[nombre]
    for h in hallazgos:
        assert h.norma and h.detalle and Path(h.fichero).as_posix().endswith(nombre)


@pytest.mark.parametrize("nombre", ["jpeg/c2pa-ia.jpg", "mp4/c2pa-ia.mp4", "wav/c2pa-ia.wav"])
def test_con_la_ca_de_prueba_como_ancla_el_firmante_es_de_confianza(nombre: str) -> None:
    m = inventaria(FIX / nombre, anclas=CA.read_text())
    assert m.c2pa.estado == "confiable"
    assert "C2PA-003" not in {h.regla for h in audita(m, TODAS)}


def test_sin_jurisdiccion_solo_corren_las_tecnicas() -> None:
    reglas = {h.regla for h in audita(inventaria(FIX / "jpeg/sin-marcas.jpg"), ())}
    assert reglas == set()


def test_la_ausencia_de_marca_solo_es_error_en_china() -> None:
    m = inventaria(FIX / "jpeg/sin-marcas.jpg")
    sev = {h.regla: h.severidad for h in audita(m, TODAS)}
    assert sev["EU-50-2-001"] is Severidad.AVISO
    assert sev["CA-942-001"] is Severidad.AVISO
    assert sev["CN-45438-001"] is Severidad.ERROR


# --- Inventarios construidos: lo que no se puede fabricar como fichero ----------------

C2PA_OK = C2paInfo(
    estado="valido",
    etiqueta="urn:c2pa:x",
    version_claim=2,
    hay_acciones=True,
    primera_accion={"action": "c2pa.created", "digitalSourceType": "x"},
    tipos_fuente=("http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",),
    agentes=(("Gen", "1.0"),),
    cuando=("2026-10-02T10:00:00Z",),
    firmante="Proveedor S.A.",
)


def _m(c2pa: C2paInfo, **kw: object) -> Marcas:
    return Marcas(fichero="x.jpg", formato="jpeg", c2pa=c2pa, **kw)  # type: ignore[arg-type]


def _reglas(m: Marcas, js: tuple[str, ...] = TODAS) -> set[str]:
    return {h.regla for h in audita(m, js)}


def test_con_sello_de_tiempo_desaparece_eu_cop_002() -> None:
    assert "EU-COP-002" in _reglas(_m(C2PA_OK), ("eu",))
    assert _reglas(_m(replace(C2PA_OK, hora_firma="2026-10-02T10:00:01Z")), ("eu",)) == set()


def test_la_hora_de_firma_cuenta_como_fecha_de_creacion_en_california() -> None:
    sin_fecha = replace(C2PA_OK, cuando=())
    assert "CA-942-004" in _reglas(_m(sin_fecha), ("ca",))
    assert "CA-942-004" not in _reglas(_m(replace(sin_fecha, hora_firma="t")), ("ca",))


def test_claim_generator_con_version_cuenta_como_sistema_genai() -> None:
    sin_agente = replace(C2PA_OK, agentes=())
    assert "CA-942-003" in _reglas(_m(sin_agente), ("ca",))
    con_gen = replace(sin_agente, generador=(("Gen", "2"),))
    assert "CA-942-003" not in _reglas(_m(con_gen), ("ca",))
    assert "CA-942-003" in _reglas(_m(replace(sin_agente, generador=(("Gen", ""),))), ("ca",))


def test_sin_asercion_de_acciones_es_c2pa_004() -> None:
    assert "C2PA-004" in _reglas(_m(replace(C2PA_OK, hay_acciones=False, primera_accion={})))


@pytest.mark.parametrize("accion", ["c2pa.edited", ""])
def test_primera_accion_que_no_es_created_ni_opened(accion: str) -> None:
    c = replace(C2PA_OK, primera_accion={"action": accion})
    assert "C2PA-004" in _reglas(_m(c))


def test_opened_sin_digital_source_type_es_valido() -> None:
    c = replace(C2PA_OK, primera_accion={"action": "c2pa.opened"})
    assert not {"C2PA-004", "C2PA-005"} & _reglas(_m(c))


def test_a_un_claim_v1_no_se_le_aplica_la_18_14_2() -> None:
    c = replace(C2PA_OK, version_claim=1, hay_acciones=False, primera_accion={})
    assert "C2PA-004" not in _reglas(_m(c))


def test_sin_libreria_c2pa_es_incompleto_y_no_error() -> None:
    hallazgos = audita(_m(C2paInfo(estado="sin_libreria")), ())
    assert [(h.regla, h.severidad) for h in hallazgos] == [("C2PA-007", Severidad.INCOMPLETO)]


def test_lee_sin_c2pa_python(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    original = builtins.__import__

    def falla(nombre: str, *a: object, **kw: object) -> object:
        if nombre == "c2pa":
            raise ImportError(nombre)
        return original(nombre, *a, **kw)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", falla)
    assert lector_c2pa.lee(FIX / "jpeg/c2pa-ia.jpg", rastro=True).estado == "sin_libreria"
    assert lector_c2pa.lee(FIX / "jpeg/sin-marcas.jpg", rastro=False).estado == "ausente"


def test_interpreta_separa_no_confiable_de_los_fallos() -> None:
    datos = {
        "active_manifest": "m",
        "manifests": {"m": {"claim_version": 2, "assertions": []}},
        "validation_status": [{"code": "signingCredential.untrusted"}],
    }
    info = lector_c2pa.interpreta(datos, "Valid")
    assert info.estado == "valido" and info.no_confiable and info.fallos == ()
    datos["validation_results"] = {
        "activeManifest": {"failure": [{"code": "assertion.dataHash.mismatch"}]}
    }
    info = lector_c2pa.interpreta(datos, "Invalid")
    assert info.estado == "invalido" and info.fallos == ("assertion.dataHash.mismatch",)


def test_el_eku_de_firma_c2pa_se_acepta() -> None:
    """Regresión de 0.1.0: con el EKU de C2PA (sin emailProtection) la firma es válida, y
    con la CA de prueba como ancla, de confianza."""
    ruta = FIX / "jpeg/c2pa-ia-eku-c2pa.jpg"
    assert inventaria(ruta).c2pa.estado == "valido"
    anclas = (FIX / "certs-eku-c2pa" / "ca.pem").read_text()
    assert inventaria(ruta, anclas=anclas).c2pa.estado == "confiable"


def _caducado(informativos: list[str]) -> dict[str, object]:
    return {
        "active_manifest": "m",
        "manifests": {"m": {"claim_version": 2, "assertions": [], "signature_info": {}}},
        "validation_results": {
            "activeManifest": {
                "failure": [
                    {"code": "signingCredential.untrusted"},
                    {"code": "signingCredential.expired"},
                ],
                "informational": [{"code": c} for c in informativos],
            }
        },
    }


def test_caducado_con_sello_de_tsa_no_confiable_es_cuestion_de_confianza() -> None:
    info = lector_c2pa.interpreta(_caducado(["timeStamp.untrusted"]), "Invalid")
    assert info.estado == "valido" and info.no_confiable and info.fallos == ()
    assert info.caducidad_por_tsa


def test_caducado_sin_sello_de_tiempo_es_un_fallo() -> None:
    info = lector_c2pa.interpreta(_caducado(["signingCredential.ocsp.skipped"]), "Invalid")
    assert info.estado == "invalido" and info.fallos == ("signingCredential.expired",)


def test_contradiccion_entre_c2pa_e_iptc() -> None:
    c = replace(
        C2PA_OK,
        tipos_fuente=("http://cv.iptc.org/newscodes/digitalsourcetype/digitalCapture",),
    )
    m = _m(c, tipos_fuente_xmp=[("xmp", C2PA_OK.tipos_fuente[0])])
    assert "MARK-001" in _reglas(m, ())


def test_https_en_el_vocabulario_iptc_se_acepta() -> None:
    https = "https://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"
    m = _m(C2paInfo(estado="ausente"), tipos_fuente_xmp=[("xmp", https)])
    assert "IPTC-001" not in _reglas(m, ())
    assert m.ia_en_xmp


def test_label_vacio_no_cuenta_como_marca_ia() -> None:
    m = _m(C2paInfo(estado="ausente"), aigc=[interpreta_aigc("x", '{"Label":""}')])
    assert not m.alguna_marca_ia
    assert {"EU-50-2-001", "CN-45438-003"} <= _reglas(m)
