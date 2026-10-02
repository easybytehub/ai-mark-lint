"""El modo `--antes/--despues`."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from ai_mark_lint.comparacion import compara
from ai_mark_lint.marcas import inventaria
from ai_mark_lint.metadatos import interpreta_aigc
from tests.conftest import FIX

TODAS = ("eu", "ca", "cn")

PARES = {
    ("jpeg/completo.jpg", "jpeg/procesado-recodificado.jpg"): {"DIFF-001", "DIFF-003", "DIFF-004"},
    ("jpeg/completo.jpg", "jpeg/procesado-sin-app11.jpg"): {"DIFF-001"},
    ("jpeg/completo.jpg", "jpeg/procesado-sin-aigc.jpg"): {"DIFF-004"},
    ("jpeg/c2pa-ia.jpg", "jpeg/c2pa-manipulado.jpg"): {"DIFF-002"},
    ("jpeg/c2pa-ia.jpg", "jpeg/c2pa-roto.jpg"): {"DIFF-002"},
    ("jpeg/c2pa-ia.jpg", "jpeg/c2pa-captura.jpg"): {"DIFF-006"},
    ("jpeg/completo.jpg", "jpeg/completo.jpg"): set(),
    ("jpeg/sin-marcas.jpg", "jpeg/completo.jpg"): set(),  # ganar marcas no es un hallazgo
    ("png/aigc.png", "png/aigc-incompleto.png"): {"DIFF-005"},
}


@pytest.mark.parametrize(("antes", "despues"), sorted(PARES))
def test_pares(antes: str, despues: str) -> None:
    hallazgos = compara(inventaria(FIX / antes), inventaria(FIX / despues), TODAS)
    assert {h.regla for h in hallazgos} == PARES[(antes, despues)]
    assert all(Path(h.fichero).as_posix().endswith(despues) for h in hallazgos)


def test_una_plataforma_que_anade_propagador_no_es_hallazgo() -> None:
    antes = inventaria(FIX / "png/aigc.png")
    campos = dict(antes.aigc[0].campos or {})
    campos.update(ContentPropagator="Plataforma", PropagateID="p-1")
    despues = replace(antes, aigc=[interpreta_aigc("PNG tEXt AIGC", json.dumps(campos))])
    assert compara(antes, despues, TODAS) == []


@pytest.mark.parametrize(
    ("js", "dentro", "fuera"),
    [
        (("eu",), "Art. 50(2)", "22757"),
        (("ca",), "22757.3.1(b)", "50(2)"),
        (("cn",), "Art. 10", "50(2)"),
    ],
)
def test_la_cita_depende_de_la_jurisdiccion(js: tuple[str, ...], dentro: str, fuera: str) -> None:
    a = inventaria(FIX / "jpeg/completo.jpg")
    d = inventaria(FIX / "jpeg/procesado-recodificado.jpg")
    for h in compara(a, d, js):
        assert dentro in h.norma and fuera not in h.norma
