"""Los parsers de contenedor: que encuentran las marcas donde las guías dicen que van, y
que no revientan con ficheros hostiles."""

from __future__ import annotations

import random
import struct
import zlib
from pathlib import Path

import pytest

from ai_mark_lint import contenedores, metadatos
from ai_mark_lint.marcas import FormatoNoSoportado, inventaria
from tests.conftest import FIX

# fixture -> (formato, nº de paquetes XMP, fragmento de cada ubicación AIGC, rastro C2PA)
ESPERADO = {
    "jpeg/sin-marcas.jpg": ("jpeg", 0, [], False),
    "jpeg/c2pa-ia.jpg": ("jpeg", 0, [], True),  # c2pa-rs, firmando un stream, no toca el XMP
    "jpeg/completo.jpg": ("jpeg", 1, ["JPEG APP1 XMP TC260:AIGC"], True),
    "jpeg/iptc-ia.jpg": ("jpeg", 1, [], False),
    "jpeg/aigc-exif.jpg": ("jpeg", 0, ["JPEG APP1 EXIF UserComment"], False),
    "png/aigc.png": ("png", 0, ["PNG tEXt AIGC"], False),
    "png/iptc-ia.png": ("png", 1, [], False),
    "png/c2pa-ia.png": ("png", 0, [], True),
    "webp/iptc-aigc.webp": ("webp", 1, ["RIFF 'XMP ' TC260:AIGC"], False),
    "webp/c2pa-ia.webp": ("webp", 0, [], True),
    "wav/aigc.wav": ("wav", 0, ["RIFF chunk 'AIGC'"], False),
    "wav/aigc-list-info.wav": ("wav", 0, ["RIFF LIST/INFO chunk 'AIGC'"], False),
    "wav/c2pa-ia.wav": ("wav", 0, [], True),
    "mp3/aigc.mp3": ("mp3", 0, ["ID3v2 TXXX 'AIGC'"], False),
    "mp3/c2pa-ia.mp3": ("mp3", 0, [], True),
    "mp4/aigc.mp4": ("mp4", 0, ["moov.udta.meta (keys/ilst) 'AIGC'"], False),
    "mp4/c2pa-ia.mp4": ("mp4", 0, [], True),
}


@pytest.mark.parametrize("nombre", sorted(ESPERADO))
def test_encuentra_las_marcas_donde_dicen_las_guias(nombre: str) -> None:
    formato, n_xmp, aigc, rastro = ESPERADO[nombre]
    m = inventaria(FIX / nombre)
    ex = contenedores.extrae((FIX / nombre).read_bytes())
    assert ex is not None
    assert m.formato == formato
    assert len(ex.xmp) == n_xmp
    assert ex.rastro_c2pa is rastro
    ubicaciones = [e.ubicacion for e in m.aigc]
    assert len(ubicaciones) == len(aigc)
    for fragmento, ubic in zip(aigc, ubicaciones, strict=True):
        assert fragmento in ubic
    for e in m.aigc:
        assert e.campos is not None and e.campos["ProduceID"] == "ai-mark-lint-fixture-0001"


def test_formato_por_firma_de_bytes_no_por_extension(tmp_path: Path) -> None:
    falso = tmp_path / "foto.jpg"
    falso.write_bytes(b"no soy un jpeg")
    with pytest.raises(FormatoNoSoportado):
        inventaria(falso)
    disfrazado = tmp_path / "audio.txt"
    disfrazado.write_bytes((FIX / "wav/aigc.wav").read_bytes())
    assert inventaria(disfrazado).formato == "wav"


def _mutaciones(datos: bytes, semilla: int) -> list[bytes]:
    rnd = random.Random(semilla)  # noqa: S311 - fuzzing reproducible, no criptografía
    out = [datos[:corte] for corte in sorted({0, 1, 3, 8, 12, 20, len(datos) // 2, len(datos) - 1})]
    for _ in range(25):
        b = bytearray(datos)
        for _ in range(rnd.randint(1, 8)):
            b[rnd.randrange(len(b))] = rnd.randrange(256)
        out.append(bytes(b))
    return out


@pytest.mark.parametrize("nombre", sorted(ESPERADO))
def test_un_fichero_hostil_nunca_hace_saltar_al_parser(nombre: str) -> None:
    datos = (FIX / nombre).read_bytes()
    for mutado in _mutaciones(datos, zlib.crc32(nombre.encode())):
        ex = contenedores.extrae(mutado)
        if ex is None:
            continue
        for _, paquete in ex.xmp:
            try:
                metadatos.lee_xmp(paquete)
            except metadatos.XmpIlegible:
                pass
        for _, tiff in ex.exif:
            metadatos.lee_user_comment(tiff)


@pytest.mark.parametrize("nombre", ["jpeg/completo.jpg", "png/c2pa-ia.png", "mp4/c2pa-ia.mp4"])
def test_inventario_de_un_fichero_truncado_no_revienta(nombre: str, tmp_path: Path) -> None:
    datos = (FIX / nombre).read_bytes()
    for corte in (len(datos) // 3, len(datos) // 2, len(datos) - 7):
        f = tmp_path / f"t{corte}"
        f.write_bytes(datos[:corte])
        m = inventaria(f)
        assert m.c2pa.estado in ("ausente", "ilegible", "invalido")


def test_tamano_imposible_se_anota_como_anomalia() -> None:
    png = (FIX / "png/aigc.png").read_bytes()
    roto = png[:8] + struct.pack(">I", 0x7FFFFFFF) + png[12:]
    ex = contenedores.extrae(roto)
    assert ex is not None and ex.anomalias and "truncated" in ex.anomalias[0]


XMP_BASE = (
    '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
    'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    '<rdf:Description xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/" {}>'
    "{}</rdf:Description></rdf:RDF></x:xmpmeta>"
)
DST = "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"


@pytest.mark.parametrize(
    ("atributos", "hijos"),
    [
        (f'Iptc4xmpExt:DigitalSourceType="{DST}"', ""),
        ("", f"<Iptc4xmpExt:DigitalSourceType>{DST}</Iptc4xmpExt:DigitalSourceType>"),
        ("", f'<Iptc4xmpExt:DigitalSourceType rdf:resource="{DST}"/>'),
    ],
)
def test_xmp_admite_las_tres_formas_rdf(atributos: str, hijos: str) -> None:
    datos = metadatos.lee_xmp(XMP_BASE.format(atributos, hijos).encode())
    assert datos.tipos_fuente == [DST]


def test_xmp_con_dtd_se_rechaza_antes_de_parsear() -> None:
    bomba = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><x:xmpmeta>&a;</x:xmpmeta>'
    with pytest.raises(metadatos.XmpIlegible, match="DTD"):
        metadatos.lee_xmp(bomba)


def test_itxt_comprimido_no_se_infla_sin_limite() -> None:
    enorme = zlib.compress(b"A" * (contenedores.MAX_ZLIB + 1024))
    assert contenedores._inflar(enorme) is None
    assert contenedores._inflar(zlib.compress(b"hola")) == b"hola"


def test_user_comment_unicode_big_endian() -> None:
    texto = '{"AIGC":{"Label":"1"}}'
    valor = b"UNICODE\x00" + texto.encode("utf-16-be")
    tiff = b"MM\x00*" + struct.pack(">I", 8)
    tiff += struct.pack(">H", 1) + struct.pack(">HHII", 0x8769, 4, 1, 26) + b"\0" * 4
    tiff += struct.pack(">H", 1) + struct.pack(">HHII", 0x9286, 7, len(valor), 44) + b"\0" * 4
    tiff += valor
    assert metadatos.lee_user_comment(tiff) == texto


def test_id3v24_txxx_utf16() -> None:
    def syncsafe(n: int) -> bytes:
        return bytes([(n >> 21) & 0x7F, (n >> 14) & 0x7F, (n >> 7) & 0x7F, n & 0x7F])

    carga = b"\x01" + "AIGC".encode("utf-16") + b"\x00\x00" + '{"Label":"1"}'.encode("utf-16")
    marco = b"TXXX" + syncsafe(len(carga)) + b"\x00\x00" + carga
    mp3 = b"ID3\x04\x00\x00" + syncsafe(len(marco)) + marco + b"\xff\xfb\x90\x00"
    ex = contenedores.extrae(mp3)
    assert ex is not None and ex.aigc == [("ID3v2 TXXX 'AIGC'", '{"Label":"1"}')]


def test_aigc_acepta_objeto_directo_y_envuelto() -> None:
    directo = metadatos.interpreta_aigc("x", '{"Label":"1","ProduceID":"a"}')
    envuelto = metadatos.interpreta_aigc("x", '{"AIGC":{"Label":"1","ProduceID":"a"}}')
    assert directo.campos == envuelto.campos == {"Label": "1", "ProduceID": "a"}
    assert metadatos.interpreta_aigc("x", "[1,2]").error == "the JSON is not an object"
