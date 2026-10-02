"""El catálogo de reglas: un sitio, y sólo uno, donde vive cada cita.

Cada regla lleva su severidad, la norma que cita, la URL donde se leyó y si el
requisito se pudo verificar en la fuente. **Una regla `verificada=False` nunca puede
ser `ERROR`**: lo impone `_comprueba_catalogo` al importar el módulo. `SPEC.md`
describe las mismas reglas con la frase literal y la fecha de consulta, y un test
comprueba que ambos listados coinciden. Lo que ve el usuario va en inglés.
"""

from __future__ import annotations

from dataclasses import dataclass

from ai_mark_lint.hallazgos import Hallazgo, Severidad

E, A, INC = Severidad.ERROR, Severidad.AVISO, Severidad.INCOMPLETO

URL_AIA_50 = "https://artificialintelligenceact.eu/article/50/"
URL_AIA_111 = "https://artificialintelligenceact.eu/article/111/"
URL_COP = "https://digital-strategy.ec.europa.eu/en/policies/code-practice-ai-generated-content"
URL_CA = (
    "https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml"
    "?lawCode=BPC&division=8.&title=&part=&chapter=25.&article="
)
URL_CN_CAC = "https://www.cac.gov.cn/2025-03/14/c_1743654684782215.htm"
URL_CN_GB = "https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=F32EA2A561F1886CD8D606513512D547"
URL_CN_TC260 = "https://www.tc260.org.cn/tc260/sjzn/list_2.shtml"
URL_C2PA = "https://spec.c2pa.org/specifications/specifications/2.2/specs/C2PA_Specification.html"
URL_IPTC = "https://cv.iptc.org/newscodes/digitalsourcetype/"

AIA_50_2 = "Regulation (EU) 2024/1689 (AI Act), Art. 50(2)"
AIA_111_4 = (
    "Regulation (EU) 2024/1689, Art. 111(4), added by Regulation (EU) 2026/1744 "
    "(Digital Omnibus on AI)"
)
COP_111 = "Code of Practice on Transparency of AI-Generated Content, Sub-measure 1.1.1"
COP_12 = "Code of Practice on Transparency of AI-Generated Content, Measure 1.2"
CA_3B = "Cal. Bus. & Prof. Code § 22757.3(b) (SB 942, as amended by AB 853)"
CA_31B = "Cal. Bus. & Prof. Code § 22757.3.1(b) (AB 853; operative January 1, 2027)"
CN_MEDIDAS = (
    "CAC Measures for Labeling AI-Generated Synthetic Content (人工智能生成合成内容标识办法)"
)
CN_ART5 = f"{CN_MEDIDAS}, Art. 5 (in force since 2025-09-01)"
CN_ART10 = f"{CN_MEDIDAS}, Art. 10"
CN_GB = "GB 45438-2025 (mandatory, in force since 2025-09-01)"
# El anexo E de la GB no se ha leído (sólo se sirve como imágenes): sólo lo cita la regla
# [unverified] que depende de él.
CN_GB_E = "GB 45438-2025, Annex E (not read at the source)"
CN_TC260 = "TC260-PG-20257A/20259A/202510A (V1.0-202508), clause 6"
C2PA_18142 = "C2PA Technical Specification 2.2, § 18.14.2"
C2PA_VAL = "C2PA Technical Specification 2.2, “Validation”"
IPTC_DST = "IPTC Photo Metadata Standard 2025.1, Digital Source Type (Iptc4xmpExt)"


@dataclass(frozen=True)
class Regla:
    id: str
    severidad: Severidad
    titulo: str
    norma: str
    url: str
    verificada: bool = True

    def hallazgo(self, detalle: str, fichero: str = "", norma: str | None = None) -> Hallazgo:
        return Hallazgo(
            regla=self.id,
            severidad=self.severidad,
            titulo=self.titulo,
            detalle=detalle,
            norma=norma or self.norma,
            fichero=fichero,
            url=self.url,
        )


_REGLAS = (
    # --- Técnicas: se aplican siempre ---------------------------------------------------
    Regla("FMT-001", INC, "Unsupported format", "—", ""),
    Regla("FMT-002", A, "The container has an anomalous structure", "—", ""),
    Regla("FMT-003", INC, "The file cannot be read", "—", ""),
    Regla("C2PA-001", E, "A C2PA manifest is present but cannot be read", C2PA_VAL, URL_C2PA),
    Regla("C2PA-002", E, "The C2PA manifest fails validation", C2PA_VAL, URL_C2PA),
    Regla("C2PA-003", INC, "Trust in the signer could not be established", C2PA_VAL, URL_C2PA),
    Regla(
        "C2PA-004",
        E,
        "The manifest does not start with c2pa.created or c2pa.opened",
        C2PA_18142,
        URL_C2PA,
    ),
    Regla(
        "C2PA-005",
        E,
        "The c2pa.created action does not declare a digitalSourceType",
        C2PA_18142,
        URL_C2PA,
    ),
    Regla(
        "C2PA-006",
        A,
        "digitalSourceType outside the IPTC and C2PA vocabularies",
        C2PA_18142,
        URL_C2PA,
    ),
    Regla(
        "C2PA-007", INC, "C2PA could not be validated: c2pa-python is missing", C2PA_VAL, URL_C2PA
    ),
    Regla(
        "C2PA-008", A, "Only a reference to a remote manifest, not a manifest", C2PA_VAL, URL_C2PA
    ),
    Regla(
        "C2PA-009",
        A,
        "A CAWG identity assertion does not validate [unverified]",
        "CAWG Identity Assertion (outside the C2PA core specification)",
        URL_C2PA,
        verificada=False,
    ),
    Regla(
        "IPTC-001",
        A,
        "XMP DigitalSourceType is not a URI from the IPTC vocabulary",
        IPTC_DST,
        URL_IPTC,
    ),
    Regla("XMP-001", A, "Unreadable XMP packet", "XMP (ISO 16684-1)", ""),
    Regla(
        "MARK-001",
        A,
        "The file's marks contradict each other about AI origin",
        f"{AIA_50_2}; {C2PA_18142}",
        URL_AIA_50,
    ),
    # --- EU -----------------------------------------------------------------------------
    Regla(
        "EU-50-2-001",
        A,
        "No machine-readable metadata marks the file as AI-generated",
        f"{AIA_50_2}; {AIA_111_4}",
        URL_AIA_50,
    ),
    Regla("EU-COP-001", A, "The AI mark is only in unsigned metadata", COP_111, URL_COP),
    Regla("EU-COP-002", A, "The signed C2PA manifest has no timestamp", COP_111, URL_COP),
    # --- California ---------------------------------------------------------------------
    Regla("CA-942-001", A, "No latent disclosure found", CA_3B, URL_CA),
    Regla(
        "CA-942-002",
        A,
        "The latent disclosure does not state the provider's name",
        f"{CA_3B}(1)(A)",
        URL_CA,
    ),
    Regla(
        "CA-942-003",
        A,
        "The latent disclosure does not state the GenAI system's name and version",
        f"{CA_3B}(1)(B)",
        URL_CA,
    ),
    Regla(
        "CA-942-004",
        A,
        "The latent disclosure does not state the creation date and time",
        f"{CA_3B}(1)(C)",
        URL_CA,
    ),
    Regla(
        "CA-942-005", A, "The latent disclosure has no unique identifier", f"{CA_3B}(1)(D)", URL_CA
    ),
    # --- China --------------------------------------------------------------------------
    Regla(
        "CN-45438-001",
        E,
        "The implicit AIGC label is missing from the metadata",
        f"{CN_ART5}; {CN_GB}; {CN_TC260}",
        URL_CN_CAC,
    ),
    Regla(
        "CN-45438-002", E, "The AIGC label is not a readable JSON object", CN_TC260, URL_CN_TC260
    ),
    Regla(
        "CN-45438-003",
        A,
        "The AIGC label lacks an element of Art. 5 [unverified]",
        f"{CN_ART5}; {CN_TC260}",
        URL_CN_CAC,
        verificada=False,
    ),
    Regla(
        "CN-45438-004",
        A,
        "Unrecognised Label value [unverified]",
        CN_GB_E,
        URL_CN_GB,
        verificada=False,
    ),
    Regla(
        "CN-45438-005",
        A,
        "The file carries several AIGC labels that disagree",
        f"{CN_ART5}; {CN_TC260}",
        URL_CN_TC260,
    ),
    Regla("CN-45438-006", A, "The AIGC label is JSON-encoded twice", CN_TC260, URL_CN_TC260),
    # --- Before/after -------------------------------------------------------------------
    Regla("DIFF-001", E, "The pipeline removed the C2PA manifest", "", URL_C2PA),
    Regla("DIFF-002", E, "The pipeline invalidated the C2PA manifest", "", URL_C2PA),
    Regla("DIFF-003", E, "The pipeline removed the IPTC AI DigitalSourceType", "", URL_IPTC),
    Regla("DIFF-004", E, "The pipeline removed the AIGC label", "", URL_CN_TC260),
    Regla("DIFF-005", A, "The pipeline changed the AIGC label's production data", "", URL_CN_TC260),
    Regla("DIFF-006", A, "The new C2PA manifest no longer declares AI origin", "", URL_C2PA),
    Regla("DIFF-007", A, "The pipeline changed the IPTC DigitalSourceType", "", URL_IPTC),
)

REGLAS: dict[str, Regla] = {r.id: r for r in _REGLAS}


def _comprueba_catalogo() -> None:
    for r in _REGLAS:
        if not r.verificada and (r.severidad is Severidad.ERROR or "[unverified]" not in r.titulo):
            raise AssertionError(f"{r.id}: an unverified rule cannot be an error")
    if len(REGLAS) != len(_REGLAS):
        raise AssertionError("duplicate rule IDs")


_comprueba_catalogo()


def norma_diff(jurisdicciones: tuple[str, ...]) -> str:
    """La cita de los hallazgos DIFF depende de dónde se publica: en la UE el 50(2)
    obliga a que la salida esté marcada (y el Code of Practice pide no quitar marcas);
    en California la prohibición es de las grandes plataformas desde 2027; en China
    está prohibido eliminarla con mala fe. Se cita lo que aplica, no todo."""
    partes: list[str] = []
    if "eu" in jurisdicciones:
        partes.append(f"{AIA_50_2}; {COP_12}")
    if "ca" in jurisdicciones:
        partes.append(CA_31B)
    if "cn" in jurisdicciones:
        partes.append(CN_ART10)
    return "; ".join(partes) or "—"
