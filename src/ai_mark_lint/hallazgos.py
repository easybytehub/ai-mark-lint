"""Qué es un hallazgo, y por qué hay tres severidades y no dos.

**`INCOMPLETO` es la severidad que hace honesta a esta herramienta**, igual que en su
hermana `verifactu-lint`. Un linter de cumplimiento tiene dos formas de equivocarse y
no cuestan lo mismo: callar un incumplimiento real es malo, y afirmar uno que no existe
es peor, porque quien lo lee cambia un pipeline correcto y deja de creerse el resto del
informe.

Aquí eso pesa todavía más que en facturación: **la marca de agua invisible no se ve
desde fuera.** Un fichero sin metadatos de IA puede llevar una marca de agua
propietaria que cumpla el art. 50(2) por sí sola. Por eso la ausencia de metadatos es
`AVISO` en la UE y en California —donde la norma no fija dónde va la marca— y `ERROR`
sólo en China, donde la norma sí dice que va en los metadatos del fichero.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Severidad(StrEnum):
    ERROR = "error"
    """Lo que hay en el fichero contradice la norma o el estándar citados."""

    AVISO = "warning"
    """Muy probablemente incumple, o la norma admite una vía que desde el fichero no se
    puede ver (una marca de agua, un enlace externo). No basta para afirmar `ERROR`."""

    INCOMPLETO = "undetermined"
    """No se puede determinar con este fichero. El hallazgo dice qué haría falta mirar."""


@dataclass(frozen=True)
class Hallazgo:
    """Un incumplimiento, o la imposibilidad de descartarlo.

    `norma` no es decorado: sin la cita, quien recibe el informe no puede contrastarlo.
    """

    regla: str
    severidad: Severidad
    titulo: str
    detalle: str
    norma: str
    fichero: str = ""
    url: str = ""

    def linea(self, con_fichero: bool = False) -> str:
        donde = f" [{self.fichero}]" if con_fichero and self.fichero else ""
        return f"{self.severidad.value.upper():12} {self.regla}{donde}: {self.titulo}"


@dataclass
class Informe:
    """El resultado completo de auditar uno o varios ficheros."""

    hallazgos: list[Hallazgo]
    ficheros: list[str]
    jurisdicciones: tuple[str, ...] = ()
    modo: str = "audit"

    @property
    def errores(self) -> list[Hallazgo]:
        return [h for h in self.hallazgos if h.severidad is Severidad.ERROR]

    @property
    def avisos(self) -> list[Hallazgo]:
        return [h for h in self.hallazgos if h.severidad is Severidad.AVISO]

    @property
    def incompletos(self) -> list[Hallazgo]:
        return [h for h in self.hallazgos if h.severidad is Severidad.INCOMPLETO]
