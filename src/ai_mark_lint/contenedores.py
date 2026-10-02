"""Lectura de contenedores en Python puro: JPEG, PNG, WebP, WAV, MP3 y MP4.

No se interpreta ni un píxel ni una muestra de audio: sólo se recorre la estructura
del contenedor para sacar los sitios donde viven las marcas —paquetes XMP, bloques
EXIF, el chunk `AIGC`, el marco ID3 `TXXX`, las claves `moov.udta.meta`— y para notar
si hay rastro de un manifiesto C2PA.

**Todo parser de este módulo trata el fichero como hostil.** Cada longitud leída del
fichero se contrasta con lo que queda de buffer antes de usarse, y un contenedor mal
formado produce una anomalía anotada, nunca una excepción ni un bucle infinito. Un
linter que revienta con el fichero raro es justo el que no sirve en un CI.
"""

from __future__ import annotations

import re
import struct
import zlib
from dataclasses import dataclass, field

XMP_JPEG = b"http://ns.adobe.com/xap/1.0/\x00"
XMP_JPEG_EXT = b"http://ns.adobe.com/xmp/extension/\x00"
UUID_XMP_BMFF = bytes.fromhex("BE7ACFCB97A942E89C71999491E3AFAC")
UUID_C2PA_BMFF = bytes.fromhex("D8FEC3D61B0E483C92975828877EC481")
# Caja de descripción JUMBF (`jumd`) seguida del UUID del almacén de manifiestos C2PA
# («c2pa» 0011-0010-8000-00AA00389B71). Es la firma inequívoca de un manifiesto: las
# subcadenas sueltas «jumb» y «c2pa» también aparecen en un XMP huérfano con
# `dcterms:provenance="self#jumbf=/c2pa/…"`, que no es un manifiesto.
FIRMA_C2PA = b"jumd" + bytes.fromhex("6332706100110010800000AA00389B71")
MAX_ZLIB = 16 * 1024 * 1024  # un iTXt comprimido no puede inflarse sin límite


@dataclass
class Extraccion:
    formato: str
    xmp: list[tuple[str, bytes]] = field(default_factory=list)
    exif: list[tuple[str, bytes]] = field(default_factory=list)
    # Valores candidatos a etiqueta AIGC, con el sitio exacto donde se encontraron.
    aigc: list[tuple[str, str]] = field(default_factory=list)
    rastro_c2pa: bool = False
    anomalias: list[str] = field(default_factory=list)


def detecta_formato(datos: bytes) -> str | None:
    if datos[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if datos[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "webp"
    if datos[:4] == b"RIFF" and datos[8:12] == b"WAVE":
        return "wav"
    if datos[4:8] == b"ftyp":
        marcas = {datos[i : i + 4] for i in range(8, min(len(datos), 64), 4)}
        if marcas & {b"avif", b"avis", b"heic", b"heix", b"mif1", b"msf1"}:
            return "heif"
        return "mp4"
    if datos[:3] == b"ID3" or (len(datos) > 1 and datos[0] == 0xFF and datos[1] & 0xE0 == 0xE0):
        return "mp3"
    return None


def extrae(datos: bytes) -> Extraccion | None:
    formato = detecta_formato(datos)
    if formato is None:
        return None
    ex = Extraccion(formato=formato)
    {
        "jpeg": _jpeg,
        "png": _png,
        "webp": _riff,
        "wav": _riff,
        "mp3": _mp3,
        "mp4": _mp4,
        "heif": _heif,
    }[formato](datos, ex)
    # El rastro se busca en bruto y sólo por la firma JUMBF del almacén C2PA: así no
    # depende de que el parser haya llegado (estructura rota) ni se dispara con texto.
    ex.rastro_c2pa = FIRMA_C2PA in datos
    return ex


def _texto(b: bytes) -> str:
    return b.rstrip(b"\x00").decode("utf-8", errors="replace").strip()


# --- JPEG --------------------------------------------------------------------------


def _jpeg(d: bytes, ex: Extraccion) -> None:
    i = 2
    n = len(d)
    while i + 4 <= n:
        if d[i] != 0xFF:
            ex.anomalias.append(f"JPEG: expected a marker at byte {i}")
            return
        marcador = d[i + 1]
        if marcador == 0xFF:  # relleno permitido entre marcadores
            i += 1
            continue
        if marcador in (0xD8, 0x01) or 0xD0 <= marcador <= 0xD7:
            i += 2
            continue
        if marcador in (0xDA, 0xD9):  # inicio de datos de imagen o fin: no hay más APPn
            return
        (largo,) = struct.unpack(">H", d[i + 2 : i + 4])
        if largo < 2 or i + 2 + largo > n:
            ex.anomalias.append(f"JPEG: segmento 0xFF{marcador:02X} truncated at byte {i}")
            return
        carga = d[i + 4 : i + 2 + largo]
        if marcador == 0xE1 and carga.startswith(XMP_JPEG):
            ex.xmp.append(("JPEG APP1 XMP", carga[len(XMP_JPEG) :]))
        elif marcador == 0xE1 and carga.startswith(XMP_JPEG_EXT):
            ex.anomalias.append("JPEG: ExtendedXMP present; v0.1 only reads the main packet")
        elif marcador == 0xE1 and carga.startswith(b"Exif\x00\x00"):
            ex.exif.append(("JPEG APP1 EXIF", carga[6:]))
        i += 2 + largo


# --- PNG ---------------------------------------------------------------------------


def _inflar(b: bytes) -> bytes | None:
    try:
        z = zlib.decompressobj()
        out = z.decompress(b, MAX_ZLIB)
        return None if z.unconsumed_tail else out
    except zlib.error:
        return None


def _png(d: bytes, ex: Extraccion) -> None:
    i = 8
    n = len(d)
    while i + 12 <= n:
        (largo,) = struct.unpack(">I", d[i : i + 4])
        tipo = d[i + 4 : i + 8]
        if i + 12 + largo > n:
            ex.anomalias.append(f"PNG: chunk {tipo!r} truncated at byte {i}")
            return
        carga = d[i + 8 : i + 8 + largo]
        if tipo in (b"tEXt", b"zTXt", b"iTXt"):
            clave, valor = _png_texto(tipo, carga)
            if clave == "XML:com.adobe.xmp" and valor is not None:
                ex.xmp.append((f"PNG {tipo.decode()} XML:com.adobe.xmp", valor))
            elif clave == "AIGC" and valor is not None:
                ex.aigc.append((f"PNG {tipo.decode()} AIGC", _texto(valor)))
        elif tipo == b"eXIf":
            ex.exif.append(("PNG eXIf", carga))
        elif tipo == b"IEND":
            return
        i += 12 + largo


def _png_texto(tipo: bytes, carga: bytes) -> tuple[str, bytes | None]:
    clave_b, _, resto = carga.partition(b"\x00")
    clave = clave_b.decode("latin-1")
    if tipo == b"tEXt":
        return clave, resto
    if tipo == b"zTXt":
        return clave, _inflar(resto[1:]) if resto[:1] == b"\x00" else None
    # iTXt: flag de compresión, método, idioma\0, clave traducida\0, texto
    if len(resto) < 2:
        return clave, None
    comprimido = resto[0] == 1
    _, _, tras_idioma = resto[2:].partition(b"\x00")
    _, _, texto = tras_idioma.partition(b"\x00")
    return clave, (_inflar(texto) if comprimido else texto)


# --- RIFF (WebP, WAV) --------------------------------------------------------------


def _riff(d: bytes, ex: Extraccion) -> None:
    _riff_chunks(d, 12, len(d), ex, "RIFF")


def _riff_chunks(
    d: bytes, i: int, fin: int, ex: Extraccion, donde: str, anidado: bool = False
) -> None:
    """`LIST/INFO` no anida: sólo se baja un nivel. Sin ese límite, un fichero con mil
    LIST encadenadas agotaba la pila (RecursionError) en vez de dar un informe."""
    fin = min(fin, len(d))
    while i + 8 <= fin:
        cid = d[i : i + 4]
        (largo,) = struct.unpack("<I", d[i + 4 : i + 8])
        if i + 8 + largo > fin:
            ex.anomalias.append(f"{donde}: chunk {cid!r} truncated at byte {i}")
            return
        carga = d[i + 8 : i + 8 + largo]
        nombre = cid.decode("latin-1")
        if cid in (b"XMP ", b"_PMX"):
            ex.xmp.append((f"{donde} {nombre!r}", carga))
        elif cid == b"EXIF":
            ex.exif.append(
                (f"{donde} 'EXIF'", carga[6:] if carga.startswith(b"Exif\0\0") else carga)
            )
        elif cid in (b"AIGC", b"aigc"):
            ex.aigc.append((f"{donde} chunk {nombre!r}", _texto(carga)))
        elif cid == b"LIST" and carga[:4] == b"INFO":
            if anidado:
                ex.anomalias.append(f"{donde}: nested LIST at byte {i}; not read")
            else:
                _riff_chunks(d, i + 12, i + 8 + largo, ex, f"{donde} LIST/INFO", anidado=True)
        i += 8 + largo + (largo & 1)  # los chunks RIFF se alinean a número par


# --- MP3 (ID3v2) -------------------------------------------------------------------


def _syncsafe(b: bytes) -> int:
    return (b[0] << 21) | (b[1] << 14) | (b[2] << 7) | b[3]


def _id3_cadena(cod: int, b: bytes) -> tuple[str, bytes]:
    """Separa una cadena terminada en nulo según la codificación ID3."""
    if cod in (1, 2):
        j = 0
        while j + 1 < len(b) and b[j : j + 2] != b"\x00\x00":
            j += 2
        crudo, resto = b[:j], b[j + 2 :]
        enc = "utf-16" if cod == 1 else "utf-16-be"
    else:
        crudo, _, resto = b.partition(b"\x00")
        enc = "latin-1" if cod == 0 else "utf-8"
    return crudo.decode(enc, errors="replace"), resto


def _id3_valor(cod: int, b: bytes) -> str:
    enc = {0: "latin-1", 1: "utf-16", 2: "utf-16-be"}.get(cod, "utf-8")
    return b.decode(enc, errors="replace").rstrip("\x00").strip()


def _mp3(d: bytes, ex: Extraccion) -> None:
    if d[:3] != b"ID3" or len(d) < 10:
        return
    version = d[3]
    if d[5] & 0x80:
        ex.anomalias.append("ID3: unsynchronised tag; v0.1 does not undo it")
    fin = min(10 + _syncsafe(d[6:10]), len(d))
    i = 10
    if d[5] & 0x40:  # cabecera extendida
        if len(d) < 14:
            ex.anomalias.append("ID3: extended header flag set but the tag is truncated")
            return
        i += _syncsafe(d[10:14]) if version == 4 else 4 + struct.unpack(">I", d[10:14])[0]
    while i + 10 <= fin:
        fid = d[i : i + 4]
        if fid == b"\x00\x00\x00\x00":
            return
        largo = (
            _syncsafe(d[i + 4 : i + 8])
            if version == 4
            else struct.unpack(">I", d[i + 4 : i + 8])[0]
        )
        if i + 10 + largo > fin:
            ex.anomalias.append(f"ID3: frame {fid!r} truncated at byte {i}")
            return
        carga = d[i + 10 : i + 10 + largo]
        if fid == b"TXXX" and carga:
            desc, valor = _id3_cadena(carga[0], carga[1:])
            if desc.strip() == "AIGC":
                ex.aigc.append(("ID3v2 TXXX 'AIGC'", _id3_valor(carga[0], valor)))
        elif fid == b"PRIV":
            dueno, _, valor = carga.partition(b"\x00")
            if dueno == b"XMP":
                ex.xmp.append(("ID3v2 PRIV 'XMP'", valor))
        i += 10 + largo


# --- MP4 / MOV (ISO BMFF) ----------------------------------------------------------


def _cajas(d: bytes, i: int, fin: int, ex: Extraccion) -> list[tuple[bytes, int, int]]:
    """(tipo, inicio del contenido, fin) de cada caja entre `i` y `fin`."""
    out: list[tuple[bytes, int, int]] = []
    fin = min(fin, len(d))
    while i + 8 <= fin:
        (largo,) = struct.unpack(">I", d[i : i + 4])
        tipo = d[i + 4 : i + 8]
        cab = 8
        if largo == 1:
            if i + 16 > fin:
                break
            (largo,) = struct.unpack(">Q", d[i + 8 : i + 16])
            cab = 16
        elif largo == 0:
            largo = fin - i
        if largo < cab or i + largo > fin:
            ex.anomalias.append(f"BMFF: box {tipo!r} with an impossible size at byte {i}")
            break
        out.append((tipo, i + cab, i + largo))
        i += largo
    return out


def _mp4(d: bytes, ex: Extraccion) -> None:
    for tipo, ini, fin in _cajas(d, 0, len(d), ex):
        if tipo == b"uuid" and d[ini : ini + 16] == UUID_XMP_BMFF:
            ex.xmp.append(("BMFF uuid XMP", d[ini + 16 : fin]))
        elif tipo == b"moov":
            for t2, i2, f2 in _cajas(d, ini, fin, ex):
                if t2 == b"meta":
                    _mp4_meta(d, i2, f2, ex, "moov.meta")
                elif t2 == b"udta":
                    for t3, i3, f3 in _cajas(d, i2, f2, ex):
                        if t3 == b"meta":
                            _mp4_meta(d, i3, f3, ex, "moov.udta.meta")
                        elif t3 == b"XMP_":
                            ex.xmp.append(("BMFF moov.udta.XMP_", d[i3:f3]))


_RE_XMP_BRUTO = re.compile(rb"<x:xmpmeta\b.{0,1048576}?</x:xmpmeta>", re.S)


def _heif(d: bytes, ex: Extraccion) -> None:
    """HEIF/AVIF guardan el XMP como un *item* (meta/iinf/iloc), no como caja propia.
    v0.1 no resuelve `iloc`: busca el paquete en bruto, que en estos ficheros va sin
    comprimir. Sin esto, un AVIF que conserva el XMP se informaría como «marcas
    perdidas», que es justo el falso positivo que más daño hace en `--antes/--despues`."""
    _mp4(d, ex)
    if not ex.xmp:
        ex.xmp += [("HEIF item XMP (raw scan)", m.group(0)) for m in _RE_XMP_BRUTO.finditer(d)]


def _mp4_meta(d: bytes, ini: int, fin: int, ex: Extraccion, donde: str) -> None:
    # `meta` es FullBox en ISO BMFF y caja simple en QuickTime: se distingue mirando si
    # lo primero que contiene ya es una caja `hdlr`.
    if d[ini + 4 : ini + 8] != b"hdlr":
        ini += 4
    claves: list[str] = []
    valores: dict[int, str] = {}
    for tipo, i, f in _cajas(d, ini, fin, ex):
        if tipo == b"keys" and i + 8 <= f:
            (cuantas,) = struct.unpack(">I", d[i + 4 : i + 8])
            j = i + 8
            for _ in range(cuantas):
                if j + 8 > f:
                    break
                (tam,) = struct.unpack(">I", d[j : j + 4])
                if tam < 8 or j + tam > f:
                    ex.anomalias.append(f"BMFF: {donde}.keys is malformed")
                    break
                claves.append(d[j + 8 : j + tam].decode("utf-8", errors="replace"))
                j += tam
        elif tipo == b"ilst":
            for t_item, i_item, f_item in _cajas(d, i, f, ex):
                (indice,) = struct.unpack(">I", t_item)
                for t_dato, i_dato, f_dato in _cajas(d, i_item, f_item, ex):
                    if t_dato == b"data" and i_dato + 8 <= f_dato:
                        valores[indice] = _texto(d[i_dato + 8 : f_dato])
    for n, clave in enumerate(claves, start=1):
        if clave == "AIGC" and n in valores:
            ex.aigc.append((f"BMFF {donde} (keys/ilst) 'AIGC'", valores[n]))
