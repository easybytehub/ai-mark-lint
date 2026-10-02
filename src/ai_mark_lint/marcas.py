"""El inventario de marcas de un fichero: lo que hay, dónde está y qué dice.

Las reglas razonan sobre este inventario y nunca sobre bytes. Eso permite probar cada
regla con un `Marcas` construido a mano —un manifiesto con sello de tiempo, una
etiqueta con un Label raro— sin tener que fabricar el fichero que lo contendría, y
permite que el modo `--antes/--despues` compare dos inventarios en vez de dos ficheros.

Los identificadores de marca (`c2pa`, `iptc-dst`, `aigc`) son los mismos que usa el
estudio S3 de EasyxLab sobre supervivencia de marcas en pipelines, para que los
resultados de uno y otro se puedan cruzar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ai_mark_lint import contenedores, metadatos
from ai_mark_lint.lector_c2pa import C2paInfo
from ai_mark_lint.lector_c2pa import lee as lee_c2pa

PREFIJO_IPTC = "http://cv.iptc.org/newscodes/digitalsourcetype/"
PREFIJO_C2PA = "http://c2pa.org/digitalsourcetype/"

# Del vocabulario IPTC (cv.iptc.org/newscodes/digitalsourcetype, consultado el
# 2026-10-02), los tres términos que declaran IA generativa; más el término propio de
# C2PA para datos (no medios) generados por un modelo.
TIPOS_IA = frozenset(
    {
        PREFIJO_IPTC + "trainedAlgorithmicMedia",
        PREFIJO_IPTC + "compositeWithTrainedAlgorithmicMedia",
        PREFIJO_IPTC + "compositeSynthetic",
        PREFIJO_C2PA + "trainedAlgorithmicData",
    }
)
VOCABULARIO = frozenset(
    {
        PREFIJO_IPTC + t
        for t in (
            "digitalCapture computationalCapture negativeFilm positiveFilm print "
            "minorHumanEdits humanEdits compositeWithTrainedAlgorithmicMedia "
            "algorithmicallyEnhanced softwareImage digitalArt digitalCreation "
            "dataDrivenMedia trainedAlgorithmicMedia algorithmicMedia screenCapture "
            "virtualRecording composite compositeCapture compositeSynthetic"
        ).split()
    }
    | {PREFIJO_C2PA + "trainedAlgorithmicData", PREFIJO_C2PA + "empty"}
)


def normaliza_tipo(valor: str) -> str:
    """`https://` y `http://` designan el mismo término; el vocabulario usa `http`."""
    v = valor.strip()
    if v.startswith("https://cv.iptc.org/"):
        v = "http://" + v[len("https://") :]
    return v


def es_tipo_ia(valor: str) -> bool:
    return normaliza_tipo(valor) in TIPOS_IA


@dataclass
class Marcas:
    fichero: str
    formato: str
    c2pa: C2paInfo
    tipos_fuente_xmp: list[tuple[str, str]] = field(default_factory=list)
    aigc: list[metadatos.EtiquetaAigc] = field(default_factory=list)
    identificadores_xmp: list[str] = field(default_factory=list)
    xmp_ilegible: list[tuple[str, str]] = field(default_factory=list)
    anomalias: list[str] = field(default_factory=list)

    @property
    def ia_en_c2pa(self) -> bool:
        tipos = self.c2pa.tipos_fuente + self.c2pa.tipos_fuente_ingredientes
        return self.c2pa.legible and any(es_tipo_ia(t) for t in tipos)

    @property
    def ia_en_xmp(self) -> bool:
        return any(es_tipo_ia(t) for _, t in self.tipos_fuente_xmp)

    @property
    def ia_en_aigc(self) -> bool:
        # Sólo una etiqueta legible que dice algo; el valor concreto de Label es
        # cosa de CN-45438-004, que está sin verificar.
        return any(e.campos is not None and e.campos.get("Label") for e in self.aigc)

    @property
    def alguna_marca_ia(self) -> bool:
        return self.ia_en_c2pa or self.ia_en_xmp or self.ia_en_aigc

    def resumen(self) -> dict[str, object]:
        """La forma estable que se compara en `--antes/--despues` y que sale en JSON."""
        return {
            "c2pa": self.c2pa.estado_en.replace(" ", "-"),
            "c2pa_ai": self.ia_en_c2pa,
            "iptc-dst": sorted({normaliza_tipo(t) for _, t in self.tipos_fuente_xmp}),
            "aigc": [e.ubicacion for e in self.aigc],
        }


class FormatoNoSoportado(ValueError):
    pass


def inventaria(ruta: Path, anclas: str | None = None) -> Marcas:
    datos = ruta.read_bytes()
    ex = contenedores.extrae(datos)
    if ex is None:
        raise FormatoNoSoportado(str(ruta))

    marcas = Marcas(
        fichero=str(ruta),
        formato=ex.formato,
        c2pa=lee_c2pa(ruta, ex.rastro_c2pa, anclas),
        anomalias=list(ex.anomalias),
    )
    if marcas.c2pa.estado == "ausente" and marcas.c2pa.error:
        # La librería no pudo recorrer el fichero, pero no hay firma JUMBF de C2PA: no hay
        # manifiesto. Lo que dijo la librería es una anomalía del contenedor, no un C2PA roto.
        marcas.anomalias.append(f"c2pa-python: {marcas.c2pa.error}")
    for donde, paquete in ex.xmp:
        try:
            x = metadatos.lee_xmp(paquete)
        except metadatos.XmpIlegible as exc:
            marcas.xmp_ilegible.append((donde, str(exc)))
            continue
        marcas.tipos_fuente_xmp += [(donde, t) for t in x.tipos_fuente]
        marcas.aigc += [metadatos.interpreta_aigc(f"{donde} TC260:AIGC", a) for a in x.aigc]
        marcas.identificadores_xmp += x.identificadores
    for donde, tiff in ex.exif:
        comentario = metadatos.lee_user_comment(tiff)
        # Un comentario libre («Shot on film, no AIGC used») no es una etiqueta: sólo
        # cuenta un objeto JSON con la clave AIGC, que es la forma del anexo B de la guía.
        if comentario and comentario.lstrip().startswith("{"):
            etiqueta = metadatos.interpreta_aigc(f"{donde} UserComment", comentario)
            if etiqueta.campos is not None and '"AIGC"' in comentario:
                marcas.aigc.append(etiqueta)
    marcas.aigc += [metadatos.interpreta_aigc(d, v) for d, v in ex.aigc]
    return marcas
