"""XMP, EXIF y la etiqueta AIGC: de bytes a datos con los que razonar.

El XMP se parsea con `xml.etree` de la biblioteca estándar. **Un paquete XMP nunca
lleva DTD**, así que cualquier `<!DOCTYPE` o `<!ENTITY` se rechaza antes de parsear:
es la forma de no exponerse a expansiones de entidades sin depender de `defusedxml`.
"""

from __future__ import annotations

import json
import re
import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

NS_RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
NS_IPTC_EXT = "http://iptc.org/std/Iptc4xmpExt/2008-02-29/"
NS_TC260 = "http://www.tc260.org.cn/ns/AIGC/1.0/"
NS_XMPMM = "http://ns.adobe.com/xap/1.0/mm/"
NS_DCTERMS = "http://purl.org/dc/terms/"


@dataclass
class DatosXmp:
    tipos_fuente: list[str] = field(default_factory=list)
    aigc: list[str] = field(default_factory=list)
    identificadores: list[str] = field(default_factory=list)
    procedencia: list[str] = field(default_factory=list)


class XmpIlegible(ValueError):
    pass


_RE_PAQUETE = re.compile(rb"<x:xmpmeta\b.*?</x:xmpmeta>|<rdf:RDF\b.*?</rdf:RDF>", re.S)


def _parsea_xml(crudo: bytes) -> ET.Element:
    if b"<!DOCTYPE" in crudo or b"<!ENTITY" in crudo:
        raise XmpIlegible("the packet declares a DTD or entities, which XMP never does")
    m = _RE_PAQUETE.search(crudo)
    if m is None:
        raise XmpIlegible("contains neither <x:xmpmeta> nor <rdf:RDF>")
    try:
        return ET.fromstring(m.group(0))  # noqa: S314 - sin DTD (comprobado arriba)
    except ET.ParseError as exc:
        raise XmpIlegible(f"malformed XML: {exc}") from exc


def _valores(desc: ET.Element, ns: str, nombre: str) -> list[str]:
    """Una propiedad XMP puede venir como atributo, como elemento con texto o como
    elemento con `rdf:resource`. Las tres formas son RDF válido y las tres se ven."""
    out: list[str] = []
    attr = desc.get(f"{{{ns}}}{nombre}")
    if attr is not None:
        out.append(attr.strip())
    for el in desc.findall(f"{{{ns}}}{nombre}"):
        recurso = el.get(f"{{{NS_RDF}}}resource")
        if recurso is not None:
            out.append(recurso.strip())
        elif el.text and el.text.strip():
            out.append(el.text.strip())
    return out


def lee_xmp(crudo: bytes) -> DatosXmp:
    raiz = _parsea_xml(crudo)
    datos = DatosXmp()
    for desc in raiz.iter(f"{{{NS_RDF}}}Description"):
        datos.tipos_fuente += _valores(desc, NS_IPTC_EXT, "DigitalSourceType")
        datos.aigc += _valores(desc, NS_TC260, "AIGC")
        datos.identificadores += _valores(desc, NS_XMPMM, "InstanceID")
        datos.identificadores += _valores(desc, NS_XMPMM, "DocumentID")
        datos.procedencia += _valores(desc, NS_DCTERMS, "provenance")
    return datos


def lee_user_comment(tiff: bytes) -> str | None:
    """EXIF UserComment (0x9286) del IFD Exif, que es donde el anexo B de la guía
    TC260-PG-20259A permite poner la etiqueta AIGC en JPEG y WebP."""
    if len(tiff) < 8:
        return None
    orden = {b"II": "<", b"MM": ">"}.get(tiff[:2])
    if orden is None:
        return None

    def entradas(off: int) -> dict[int, tuple[int, int, bytes]]:
        out: dict[int, tuple[int, int, bytes]] = {}
        if off + 2 > len(tiff):
            return out
        (n,) = struct.unpack(orden + "H", tiff[off : off + 2])
        for k in range(min(n, 512)):
            p = off + 2 + 12 * k
            if p + 12 > len(tiff):
                break
            tag, tipo, cuenta = struct.unpack(orden + "HHI", tiff[p : p + 8])
            out[tag] = (tipo, cuenta, tiff[p + 8 : p + 12])
        return out

    (ifd0,) = struct.unpack(orden + "I", tiff[4:8])
    puntero = entradas(ifd0).get(0x8769)
    if puntero is None:
        return None
    (off_exif,) = struct.unpack(orden + "I", puntero[2])
    uc = entradas(off_exif).get(0x9286)
    if uc is None:
        return None
    _, cuenta, valor = uc
    if cuenta <= 4:
        crudo = valor[:cuenta]
    else:
        (off,) = struct.unpack(orden + "I", valor)
        crudo = tiff[off : off + cuenta]
    juego, texto = crudo[:8], crudo[8:]
    if juego.startswith(b"UNICODE"):
        enc = "utf-16-le" if orden == "<" else "utf-16-be"
        return texto.decode(enc, errors="replace").rstrip("\x00").strip()
    return texto.decode("utf-8", errors="replace").rstrip("\x00").strip()


@dataclass(frozen=True)
class EtiquetaAigc:
    ubicacion: str
    crudo: str
    campos: dict[str, str] | None
    error: str = ""
    doble: bool = False
    """El valor es una cadena JSON que contiene el objeto (codificado dos veces)."""


def interpreta_aigc(ubicacion: str, crudo: str) -> EtiquetaAigc:
    """Las guías TC260 usan dos formas: el objeto directo (XMP, WAV, MP3, MP4) y el
    objeto envuelto en `{"AIGC": {...}}` (anexo B: EXIF UserComment y tEXt de PNG).
    Se aceptan las dos en cualquier sitio: lo que importa es lo que dice."""
    try:
        obj = json.loads(crudo)
    except json.JSONDecodeError as exc:
        return EtiquetaAigc(ubicacion, crudo, None, f"not JSON: {exc.msg}")
    # Hay generadores que guardan el objeto ya serializado como cadena JSON (lo midió el
    # estudio S6 de EasyxLab en Commons). La marca existe y se cuenta, pero quien lea una
    # sola vez, como describen las guías, no la encuentra: CN-45438-006.
    doble = False
    if isinstance(obj, str):
        try:
            interior = json.loads(obj)
        except json.JSONDecodeError:
            interior = None
        if isinstance(interior, dict):
            obj, doble = interior, True
    if isinstance(obj, dict) and set(obj) == {"AIGC"} and isinstance(obj["AIGC"], dict):
        obj = obj["AIGC"]
    if not isinstance(obj, dict):
        return EtiquetaAigc(ubicacion, crudo, None, "the JSON is not an object")
    campos = {str(k): ("" if v is None else str(v)) for k, v in obj.items()}
    return EtiquetaAigc(ubicacion, crudo, campos, doble=doble)
