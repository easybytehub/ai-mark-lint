"""Cómo se presenta el informe: texto, JSON y SARIF (todo en inglés).

SARIF no está por completismo: es lo que GitHub ingiere en la pestaña Security.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_mark_lint.catalogo import REGLAS
from ai_mark_lint.hallazgos import Informe, Severidad

_NIVEL_SARIF = {
    Severidad.ERROR: "error",
    Severidad.AVISO: "warning",
    Severidad.INCOMPLETO: "note",
}
AVISO_LEGAL = (
    "Zero errors means these rules found no breach in the metadata; it does not certify "
    "compliance, and invisible watermarks were not checked."
)


def texto(informe: Informe, color: bool = True) -> str:
    rojo, amarillo, azul, gris, fin = (
        ("\033[31m", "\033[33m", "\033[34m", "\033[90m", "\033[0m") if color else ("",) * 5
    )
    tinte = {Severidad.ERROR: rojo, Severidad.AVISO: amarillo, Severidad.INCOMPLETO: azul}
    sangria = " " * 13
    lineas = [
        f"ai-mark-lint · {len(informe.ficheros)} file(s) · "
        f"jurisdictions: {','.join(informe.jurisdicciones) or '(technical only)'}"
        + (" · before/after mode" if informe.modo == "compare" else ""),
        "",
    ]
    varios = len(informe.ficheros) > 1
    if not informe.hallazgos:
        lineas.append("No findings.")
    for h in informe.hallazgos:
        lineas.append(f"{tinte[h.severidad]}{h.linea(con_fichero=varios)}{fin}")
        lineas += [f"{sangria}{d}" for d in h.detalle.splitlines()]
        lineas.append(f"{gris}{sangria}citation: {h.norma}{fin}")
        lineas.append("")

    def plural(n: int, s: str, p: str) -> str:
        return f"{n} {s if n == 1 else p}"

    lineas.append(
        " · ".join(
            (
                plural(len(informe.errores), "error", "errors"),
                plural(len(informe.avisos), "warning", "warnings"),
                f"{len(informe.incompletos)} undetermined",
            )
        )
    )
    lineas.append(f"{gris}{AVISO_LEGAL}{fin}")
    return "\n".join(lineas)


def como_json(informe: Informe, inventario: dict[str, Any] | None = None) -> str:
    datos: dict[str, Any] = {
        "mode": informe.modo,
        "files": informe.ficheros,
        "jurisdictions": list(informe.jurisdicciones),
        "summary": {
            "errors": len(informe.errores),
            "warnings": len(informe.avisos),
            "undetermined": len(informe.incompletos),
        },
        "findings": [
            {
                "rule": h.regla,
                "severity": h.severidad.value,
                "title": h.titulo,
                "detail": h.detalle,
                "citation": h.norma,
                "url": h.url,
                "file": h.fichero,
            }
            for h in informe.hallazgos
        ],
        "marks": inventario or {},
        "notice": AVISO_LEGAL,
    }
    return json.dumps(datos, ensure_ascii=False, indent=2)


def _uri(fichero: str) -> str:
    """Relativa al directorio de trabajo (la raíz del checkout en CI, que es lo que GitHub
    sabe anclar); `file://` absoluta si el fichero está fuera de él."""
    ruta = Path(fichero)
    if not ruta.is_absolute():
        return ruta.as_posix()
    absoluta = ruta.resolve()  # /var y /private/var son el mismo sitio en macOS
    try:
        return absoluta.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return absoluta.as_uri()


def como_sarif(informe: Informe, version: str) -> str:
    reglas_vistas: dict[str, dict[str, Any]] = {}
    resultados: list[dict[str, Any]] = []
    for h in informe.hallazgos:
        regla = REGLAS[h.regla]
        descriptor: dict[str, Any] = {
            "id": h.regla,
            "shortDescription": {"text": regla.titulo},
            "fullDescription": {"text": regla.norma},
            "defaultConfiguration": {"level": _NIVEL_SARIF[regla.severidad]},
        }
        if regla.url:
            descriptor["helpUri"] = regla.url
        reglas_vistas.setdefault(h.regla, descriptor)
        resultados.append(
            {
                "ruleId": h.regla,
                "level": _NIVEL_SARIF[h.severidad],
                "message": {"text": f"{h.titulo}. {h.detalle}\nCitation: {h.norma}"},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": _uri(h.fichero)},
                            # Un binario no tiene líneas; GitHub necesita una región.
                            "region": {"startLine": 1},
                        }
                    }
                ],
            }
        )
    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "ai-mark-lint",
                        "version": version,
                        "informationUri": "https://github.com/easybytehub/ai-mark-lint",
                        "rules": list(reglas_vistas.values()),
                    }
                },
                "results": resultados,
            }
        ],
    }
    return json.dumps(sarif, ensure_ascii=False, indent=2)
