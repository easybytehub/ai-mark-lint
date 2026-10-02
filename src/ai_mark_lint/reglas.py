"""Las reglas. Cada una es una función `Marcas -> list[Hallazgo]`.

No hay clase base ni registro por decorador: las de cada familia están en una tupla, y
`audita` decide qué familias corren según las jurisdicciones pedidas. Las técnicas
(C2PA, IPTC, XMP) corren siempre: un manifiesto roto es un defecto en cualquier país.
"""

from __future__ import annotations

from collections.abc import Callable

from ai_mark_lint.catalogo import REGLAS
from ai_mark_lint.hallazgos import Hallazgo
from ai_mark_lint.marcas import VOCABULARIO, Marcas, normaliza_tipo

Regla = Callable[[Marcas], list[Hallazgo]]
VALORES_LABEL = ("1", "2", "3")  # [unverified]: anexo E de GB 45438-2025 no leído
CLAVES_AIGC = ("Label", "ContentProducer", "ProduceID")


def _h(rid: str, m: Marcas, detalle: str) -> list[Hallazgo]:
    return [REGLAS[rid].hallazgo(detalle, fichero=m.fichero)]


# --- Técnicas ----------------------------------------------------------------------


def estructura(m: Marcas) -> list[Hallazgo]:
    out: list[Hallazgo] = []
    if m.anomalias:
        out += _h("FMT-002", m, "\n".join(m.anomalias))
    for donde, error in m.xmp_ilegible:
        out += _h("XMP-001", m, f"{donde}: {error}. Whatever that XMP said could not be read.")
    return out


def c2pa_validez(m: Marcas) -> list[Hallazgo]:
    c = m.c2pa
    if c.estado == "sin_libreria":
        return _h(
            "C2PA-007",
            m,
            "The file contains C2PA data, but c2pa-python is not installed or does not load "
            "on this platform. Without it neither the signature nor the hashes are checked.",
        )
    if c.estado == "solo_referencia":
        return _h(
            "C2PA-008",
            m,
            f"{c.error}.\nThere is no embedded manifest, only a link (XMP dcterms:provenance). "
            "ai-mark-lint never follows links, and the EasyxLab S3 study measured that, "
            "when the link survives in a derivative, the hash fails against the original's "
            "manifest (3 out of 3). It does not count as a mark.",
        )
    if c.estado == "ilegible":
        return _h(
            "C2PA-001",
            m,
            f"{c.error}.\nA C2PA validator will reject this manifest: the mark is in the "
            "file, but nobody will be able to read it.",
        )
    if c.estado == "invalido":
        codigos = ", ".join(c.fallos) or "no code"
        pista = ""
        if any("dataHash.mismatch" in f or "bmffHash.mismatch" in f for f in c.fallos):
            pista = (
                "\nThe content changed after signing: something in the pipeline re-encoded or "
                "edited the file and kept a manifest that no longer matches it."
            )
        return _h("C2PA-002", m, f"Failure codes: {codigos}.{pista}") + _cawg(m)
    out: list[Hallazgo] = []
    if c.firma_valida and c.no_confiable:
        out += _h(
            "C2PA-003",
            m,
            f"The signature is intact, but a certificate (signer “{c.firmante or '?'}”, its "
            "timestamp or an identity credential) does not chain to any configured trust "
            "anchor. Pass the trust list your verifier uses with --trust-anchors."
            + (
                "\nThe signer's certificate has expired. It was valid when signed only if you "
                "trust the time-stamp authority; a validator without that TSA in its trust "
                "list rejects the manifest (C2PA 2.2 § 15.8.2)."
                if c.caducidad_por_tsa
                else ""
            ),
        )
    return out + _cawg(m)


def _cawg(m: Marcas) -> list[Hallazgo]:
    if not m.c2pa.fallos_cawg:
        return []
    return _h(
        "C2PA-009",
        m,
        f"Codes: {', '.join(m.c2pa.fallos_cawg)}. CAWG identity assertions are not part of "
        "the core C2PA specification: they do not affect the manifest's validity here.",
    )


def c2pa_acciones(m: Marcas) -> list[Hallazgo]:
    c = m.c2pa
    if not c.legible:
        return []
    if c.version_claim is not None and c.version_claim < 2:
        # § 18.14.2 es de la especificación 2.x; a un claim v1 no se le puede exigir.
        return []
    if c.actualizacion:
        # «This requirement does not apply to Update Manifests» (§ 18.14.2).
        return []
    if not c.hay_acciones:
        return _h(
            "C2PA-004",
            m,
            "The active manifest has no c2pa.actions assertion, and the specification "
            "requires at least one.",
        )
    accion = str(c.primera_accion.get("action", ""))
    out: list[Hallazgo] = []
    if accion not in ("c2pa.created", "c2pa.opened"):
        out += _h(
            "C2PA-004",
            m,
            f"The first action is “{accion or '(empty)'}”. Content generated from scratch "
            "must start with c2pa.created; edited content, with c2pa.opened.",
        )
    if accion == "c2pa.created" and not c.primera_accion.get("digitalSourceType"):
        out += _h(
            "C2PA-005",
            m,
            "Without a digitalSourceType a C2PA reader cannot tell whether the content is a "
            "capture or was generated by a model: the mark exists but does not say “AI”.",
        )
    raros = sorted({t for t in c.tipos_fuente if normaliza_tipo(t) not in VOCABULARIO})
    if raros:
        out += _h("C2PA-006", m, "Unrecognised values: " + ", ".join(raros))
    return out


def iptc(m: Marcas) -> list[Hallazgo]:
    raros = sorted({t for _, t in m.tipos_fuente_xmp if normaliza_tipo(t) not in VOCABULARIO})
    if not raros:
        return []
    detalle = "Values: " + ", ".join(raros) + "."
    if any("/" not in t for t in raros):
        detalle += (
            "\nThe value must be the full URI (e.g. http://cv.iptc.org/newscodes/"
            "digitalsourcetype/trainedAlgorithmicMedia), not the bare code: a reader that "
            "compares URIs will not recognise it."
        )
    return _h("IPTC-001", m, detalle)


def coherencia(m: Marcas) -> list[Hallazgo]:
    declaraciones: list[tuple[str, bool]] = []
    if m.c2pa.legible and m.c2pa.tipos_fuente:
        declaraciones.append(("C2PA", m.ia_en_c2pa))
    if m.tipos_fuente_xmp:
        declaraciones.append(("IPTC XMP", m.ia_en_xmp))
    if not declaraciones or len({ia for _, ia in declaraciones}) == 1:
        return []
    texto = "; ".join(f"{fuente}: {'AI' if ia else 'not AI'}" for fuente, ia in declaraciones)
    return _h(
        "MARK-001",
        m,
        f"{texto}.\nEach detector will believe whichever mark it reads first. One of them is "
        "redundant or wrong.",
    )


TECNICAS: tuple[Regla, ...] = (estructura, c2pa_validez, c2pa_acciones, iptc, coherencia)


# --- UE ----------------------------------------------------------------------------


def _sin_libreria(m: Marcas) -> str:
    if m.c2pa.estado == "sin_libreria":
        return (
            "The file contains C2PA data that could not be checked (c2pa-python is missing), "
            "so it is not counted. "
        )
    return ""


def ue(m: Marcas) -> list[Hallazgo]:
    if not m.alguna_marca_ia:
        return _h(
            "EU-50-2-001",
            m,
            _sin_libreria(m)
            + "No C2PA with an AI digitalSourceType, no AI IPTC DigitalSourceType, no AIGC "
            "label.\nArt. 50(2) does not mandate a format: if your system marks only with an "
            "imperceptible watermark, this tool cannot see it. But the Code of Practice asks "
            "for signed metadata on top of the watermark in every format that supports "
            "metadata.\nApplies from 2 August 2026; for systems already on the market before "
            "that date, from 2 December 2026 (Art. 111(4)).",
        )
    out: list[Hallazgo] = []
    if not (m.ia_en_c2pa and m.c2pa.firma_valida):
        donde = [n for n, si in (("IPTC XMP", m.ia_en_xmp), ("AIGC", m.ia_en_aigc)) if si]
        if m.ia_en_c2pa:
            donde.insert(0, "a C2PA manifest whose signature does not validate")
        out += _h(
            "EU-COP-001",
            m,
            f"The AI declaration is in {' and in '.join(donde)}, with no valid digital "
            "signature behind it. Anyone can remove or change it without a trace, and "
            "Sub-measure 1.1.1 asks for the recorded information to be signed and "
            "time-stamped.",
        )
    elif not m.c2pa.hora_firma:
        out += _h(
            "EU-COP-002",
            m,
            "The signature carries no timestamp from a TSA (RFC 3161). Sub-measure 1.1.1 asks "
            "for one “on systems where time information is available”, which is almost any "
            "server.",
        )
    return out


# --- California ---------------------------------------------------------------------


def california(m: Marcas) -> list[Hallazgo]:
    c = m.c2pa
    hay_c2pa = c.legible
    if not (hay_c2pa or m.tipos_fuente_xmp or m.aigc):
        enlace = (
            "There is only a link to a remote manifest: the law allows the data to be given "
            "“through a link”, but this tool does not follow it and cannot see what it holds.\n"
            if c.estado == "solo_referencia"
            else ""
        )
        return _h(
            "CA-942-001",
            m,
            enlace
            + _sin_libreria(m)
            + "No readable C2PA manifest, no IPTC XMP, no AIGC label. The law allows the "
            "latent "
            "disclosure to be something else (a watermark, a link), but it must be “consistent "
            "with widely accepted industry standards” and convey the four data items of "
            "§ 22757.3(b)(1).\nIt only binds “covered providers”: GenAI systems with over "
            "1,000,000 monthly visitors or users. Operative since 2 August 2026.",
        )
    aigc = [e.campos for e in m.aigc if e.campos]
    out: list[Hallazgo] = []
    proveedor = c.firmante if hay_c2pa else ""
    proveedor = proveedor or next(
        (a.get("ContentProducer", "") for a in aigc if a.get("ContentProducer")), ""
    )
    if not proveedor:
        out += _h("CA-942-002", m, "Neither a C2PA signer nor an AIGC ContentProducer.")
    sistemas = [a for a in c.agentes if a[0] and a[1]] + [g for g in c.generador if g[0] and g[1]]
    if not sistemas:
        out += _h(
            "CA-942-003",
            m,
            "Looked for softwareAgent (name and version) in the C2PA actions and for "
            "claim_generator_info with a version. IPTC and AIGC have no field for this.",
        )
    if not (c.cuando or c.hora_firma):
        out += _h(
            "CA-942-004",
            m,
            "Neither “when” in the C2PA actions nor a signing time stamped by a TSA.",
        )
    unico = c.etiqueta or next((a["ProduceID"] for a in aigc if a.get("ProduceID")), "")
    if not (unico or m.identificadores_xmp):
        out += _h(
            "CA-942-005",
            m,
            "Neither a C2PA manifest label, nor an AIGC ProduceID, nor xmpMM:InstanceID.",
        )
    if out:
        texto = (
            "\nThe law requires these items “to the extent that it is technically feasible and "
            "reasonable” and allows them “through a link to a permanent internet website”: "
            "hence a warning, not an error."
        )
        out[-1] = REGLAS[out[-1].regla].hallazgo(out[-1].detalle + texto, fichero=m.fichero)
    return out


# --- China -------------------------------------------------------------------------


def china(m: Marcas) -> list[Hallazgo]:
    if not m.aigc:
        return _h(
            "CN-45438-001",
            m,
            f"Format {m.formato}: no AIGC key in any of the places the TC260 guides set out "
            "(XMP TC260:AIGC; EXIF UserComment; PNG tEXt “AIGC”; RIFF chunk “AIGC”; ID3v2 TXXX "
            "“AIGC”; MP4 moov.udta.meta).\nA C2PA manifest does not replace this label: the "
            "Chinese rules define their own field.",
        )
    out: list[Hallazgo] = []
    for e in m.aigc:
        if e.campos is None:
            out += _h("CN-45438-002", m, f"{e.ubicacion}: {e.error}.\nValue: {e.crudo[:200]}")
            continue
        if e.doble:
            out += _h(
                "CN-45438-006",
                m,
                f"{e.ubicacion}: the value is a JSON string that contains the label object.\n"
                "A reader that parses it once, as the TC260 guides describe, gets a string "
                f"and misses the label. Value: {e.crudo[:200]}",
            )
        faltan = [k for k in CLAVES_AIGC if not e.campos.get(k, "").strip()]
        if faltan:
            out += _h(
                "CN-45438-003",
                m,
                f"{e.ubicacion}: missing or empty {', '.join(faltan)}. Art. 5 requires the "
                "generated-content attribute, the provider's name or code and the content "
                "number; that these are Label, ContentProducer and ProduceID is inferred from "
                "the key names (GB 45438 Annex E, which defines them, could not be read). "
                "Hence a warning.",
            )
        label = e.campos.get("Label", "").strip()
        if label and label not in VALORES_LABEL:
            out += _h(
                "CN-45438-004",
                m,
                f"{e.ubicacion}: Label = “{label}”. Secondary sources give 1, 2 and 3 as the "
                "valid values; GB 45438 Annex E, which defines them, could not be read at the "
                "source. Hence a warning.",
            )
    produccion = {
        tuple(e.campos.get(k, "") for k in CLAVES_AIGC) for e in m.aigc if e.campos is not None
    }
    if len(produccion) > 1:
        out += _h(
            "CN-45438-005",
            m,
            "Labels found:\n" + "\n".join(f"  {e.ubicacion}: {e.crudo[:160]}" for e in m.aigc),
        )
    return out


POR_JURISDICCION: dict[str, tuple[Regla, ...]] = {
    "eu": (ue,),
    "ca": (california,),
    "cn": (china,),
}


def audita(m: Marcas, jurisdicciones: tuple[str, ...]) -> list[Hallazgo]:
    reglas: list[Regla] = list(TECNICAS)
    for j in jurisdicciones:
        reglas += POR_JURISDICCION[j]
    out: list[Hallazgo] = []
    for regla in reglas:
        out += regla(m)
    return out
