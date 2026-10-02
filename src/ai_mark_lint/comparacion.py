"""`--before A --after B`: qué marcas se han perdido por el camino.

El generador marca bien; luego el fichero pasa por un redimensionado, un CDN o un CMS,
y lo que se publica ya no lleva nada. Comparar el antes y el después de cada paso dice
*qué paso* rompió la marca. Sólo se informa de lo que se pierde o se estropea: que el
pipeline añada marcas (una plataforma que añade ContentPropagator, como le pide el
art. 6 de las medidas chinas) no es un hallazgo.
"""

from __future__ import annotations

from ai_mark_lint.catalogo import REGLAS, norma_diff
from ai_mark_lint.hallazgos import Hallazgo
from ai_mark_lint.marcas import Marcas, normaliza_tipo
from ai_mark_lint.reglas import CLAVES_AIGC


def compara(antes: Marcas, despues: Marcas, jurisdicciones: tuple[str, ...]) -> list[Hallazgo]:
    norma = norma_diff(jurisdicciones)
    out: list[Hallazgo] = []

    def h(rid: str, detalle: str) -> None:
        out.append(REGLAS[rid].hallazgo(detalle, fichero=despues.fichero, norma=norma))

    a, d = antes.c2pa, despues.c2pa
    if a.legible and d.estado in ("ausente", "solo_referencia"):
        queda = (
            "only a remote reference, which is not a credential"
            if d.estado == "solo_referencia"
            else "none"
        )
        h(
            "DIFF-001",
            f"Before: manifest {a.etiqueta or '(no label)'} ({a.estado_en}). After: {queda}.\n"
            f"Format {antes.formato} → {despues.formato}. Usually a re-encode or a "
            "“strip metadata” step that drops the JUMBF segments.",
        )
    elif a.firma_valida and d.estado in ("invalido", "ilegible"):
        motivo = ", ".join(d.fallos) or d.error
        h(
            "DIFF-002",
            f"Before: {a.estado_en}. After: {d.estado_en} ({motivo}).\nThe step kept the "
            "manifest but changed the content: re-sign with the original as an ingredient, "
            "or do not touch the bytes.",
        )
    elif antes.ia_en_c2pa and d.firma_valida and not despues.ia_en_c2pa:
        h(
            "DIFF-006",
            "The processed file carries a new, valid manifest that no longer declares an AI "
            "digitalSourceType. If the step re-signed, it must keep the original as an "
            "ingredient or repeat the digitalSourceType.",
        )

    tipos_a = {normaliza_tipo(t) for _, t in antes.tipos_fuente_xmp}
    tipos_d = {normaliza_tipo(t) for _, t in despues.tipos_fuente_xmp}
    # Error sólo si se pierde la declaración de IA; aviso si cambia y sigue siendo IA (o
    # nunca lo fue); nada si el después conserva todo lo de antes.
    if tipos_a and not tipos_a <= tipos_d:
        cambio = (
            f"Before: {', '.join(sorted(tipos_a))}.\n"
            f"After: {', '.join(sorted(tipos_d)) or '(none)'}."
        )
        h("DIFF-003" if antes.ia_en_xmp and not despues.ia_en_xmp else "DIFF-007", cambio)

    legibles_a = [e.campos for e in antes.aigc if e.campos is not None]
    legibles_d = [e.campos for e in despues.aigc if e.campos is not None]
    if antes.aigc and not despues.aigc:
        h("DIFF-004", "Before: " + "; ".join(e.ubicacion for e in antes.aigc) + ".\nAfter: none.")
    elif legibles_a and legibles_d:
        prod_a = {tuple(c.get(k, "") for k in CLAVES_AIGC) for c in legibles_a}
        prod_d = {tuple(c.get(k, "") for k in CLAVES_AIGC) for c in legibles_d}
        if not prod_a & prod_d:
            h(
                "DIFF-005",
                f"Before (Label, ContentProducer, ProduceID): {sorted(prod_a)}.\n"
                f"After: {sorted(prod_d)}.\nA platform may add ContentPropagator and "
                "PropagateID; it should not rewrite the producer's data.",
            )
    return out
