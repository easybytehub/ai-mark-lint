"""Los pares antes/después del estudio S3 de EasyxLab.

Ficheros copiados, sin modificar, de
`easyxlab/studies/s3-ai-marks-survival/fixtures/` (ver `fixtures/s3/README-S3.md`).
Los firmó S3 con el certificado de *prueba* de c2patool 0.27.22, y las salidas las
produjeron herramientas reales —sharp, ImageMagick, Pillow, ffmpeg, exiftool, el
optimizador de next/image—, no este repositorio. Por eso son la mejor prueba de que
`--antes/--despues` dice lo que de verdad pasa en un pipeline. Lo esperado sale de la
tabla `derived/` de ese README y de `data/matrix.csv` del estudio.
"""

from __future__ import annotations

import pytest

from ai_mark_lint.comparacion import compara
from ai_mark_lint.marcas import inventaria
from ai_mark_lint.reglas import audita
from tests.conftest import FIX

S3 = FIX / "s3"
TODO = {"DIFF-001", "DIFF-003", "DIFF-004"}  # se pierde C2PA, IPTC y AIGC

PARES = {
    "jpg-all-remote__exiftool_edit_title.jpg": {"DIFF-002"},
    "jpg-all-remote__sharp_resize.jpg": TODO,
    "jpg-all-remote__sharp_resize_keepMetadata.jpg": {"DIFF-001"},
    "jpg-all-remote__sharp_resize_keepMetadata_then_c2pa_resign.jpg": set(),
    "jpg-all-remote__nextimage_webp.webp": TODO,
    "jpg-all-remote__magick_resize.jpg": {"DIFF-001"},
    "jpg-all-remote__exiftool_restore_all.jpg": {"DIFF-001"},
    "png-all-remote__pil_resave_keep.png": TODO,
    "png-all-remote__pil_resave_png_itxt.png": {"DIFF-001"},
    "webp-all-remote__pil_to_avif_keep.avif": {"DIFF-001"},
    "mp4-all__ffmpeg_remux.mp4": TODO,
    "mp4-all__ffmpeg_remux_exportxmp.mp4": TODO,
    "mp4-all__exiftool_edit_title.mp4": {"DIFF-002"},
}


def _original(derivado: str) -> str:
    base, ext = derivado.split("__")[0], derivado.split("__")[0].split("-")[0]
    return f"{base}.{ext}"


@pytest.mark.parametrize("derivado", sorted(PARES))
def test_pares_de_s3(derivado: str) -> None:
    antes = inventaria(S3 / "originales" / _original(derivado))
    despues = inventaria(S3 / "derivados" / derivado)
    assert {h.regla for h in compara(antes, despues, ("eu", "ca", "cn"))} == PARES[derivado]


@pytest.mark.parametrize(
    "original", ["jpg-all-remote.jpg", "png-all-remote.png", "webp-all-remote.webp", "mp4-all.mp4"]
)
def test_los_originales_de_s3_llevan_las_tres_marcas(original: str) -> None:
    m = inventaria(S3 / "originales" / original)
    assert m.c2pa.estado == "valido" and m.ia_en_c2pa and m.ia_en_xmp and m.ia_en_aigc
    # Firmados con el certificado de prueba de c2patool: firma íntegra, no confiable.
    # Y c2patool, por defecto, no pone «when» en la acción ni sella la firma: el
    # manifiesto no dice cuándo se creó el contenido, que es lo que pide § 22757.3(b)(1)(C).
    assert {h.regla for h in audita(m, ("eu", "ca", "cn"))} == {
        "C2PA-003",
        "EU-COP-002",
        "CA-942-004",
    }


def test_presente_pero_invalido_no_pasa_por_bueno() -> None:
    """El fallo silencioso que midió S3 (6 de 6): editar un campo tras firmar deja el
    manifiesto en el fichero con la firma rota. Mirar sólo si hay manifiesto lo daría
    por bueno."""
    m = inventaria(S3 / "derivados" / "jpg-all-remote__exiftool_edit_title.jpg")
    assert m.c2pa.estado == "invalido" and "assertion.dataHash.mismatch" in m.c2pa.fallos
    hallazgos = {h.regla for h in audita(m, ("eu",))}
    assert {"C2PA-002", "EU-COP-001"} <= hallazgos


@pytest.mark.parametrize(
    "derivado",
    ["jpg-all-remote__magick_resize.jpg", "png-all-remote__pil_resave_png_itxt.png"],
)
def test_una_referencia_remota_superviviente_es_solo_referencia(derivado: str) -> None:
    m = inventaria(S3 / "derivados" / derivado)
    assert m.c2pa.estado == "solo_referencia" and not m.ia_en_c2pa
    assert "C2PA-008" in {h.regla for h in audita(m, ())}


def test_el_xmp_de_un_avif_se_encuentra() -> None:
    m = inventaria(S3 / "derivados" / "webp-all-remote__pil_to_avif_keep.avif")
    assert m.formato == "heif" and m.ia_en_xmp and m.ia_en_aigc


def test_editar_con_ingrediente_conserva_la_declaracion_de_ia() -> None:
    m = inventaria(
        S3 / "derivados" / "jpg-all-remote__sharp_resize_keepMetadata_then_c2pa_resign.jpg"
    )
    assert m.c2pa.estado == "valido" and m.ia_en_c2pa
    assert m.c2pa.tipos_fuente_ingredientes
