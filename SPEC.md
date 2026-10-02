# ai-mark-lint — rule specification (v0.1.0)

Every rule has a stable ID, the **literal** sentence of the law or standard that
supports it, the URL where it was read, the access date, its severity and how it is
checked. All sources were accessed on **2026-10-02** by downloading the HTML or PDF with
`curl` and searching for the literal sentence with `grep`; no quotation comes from an
automatic summary.

**Golden rule:** a requirement that could not be read at its source is tagged
`[unverified]` and is **never** an `error`. The catalogue
(`src/ai_mark_lint/catalogo.py`) enforces this when it is imported, and
`tests/test_catalogo.py` checks that this document and the catalogue agree.

Severities: `error` (the file contradicts the law or standard), `warning` (very likely
non-compliant, or the law allows a route that cannot be seen from the file) and
`undetermined` (cannot be decided from the file).

## Sources and their status

| Source | Status on 2026-10-02 | How it was verified |
|---|---|---|
| AI Act (Regulation (EU) 2024/1689), Art. 50(2) and 113 | In force. Art. 50 applies from **2 August 2026** (Art. 113: “It shall apply from 2 August 2026”, with no exception for Chapter IV). | EUR-Lex returns an empty `202` to `curl` (also via ELI). Text read on artificialintelligenceact.eu (FLI), which reproduces the Official Journal: <https://artificialintelligenceact.eu/article/50/>, <https://artificialintelligenceact.eu/article/113/> |
| Digital Omnibus on AI = **Regulation (EU) 2026/1744** of 8 July 2026 | Published. **It does not postpone Art. 50(2) in general.** It adds Art. 111(4): systems already on the market before 2 August 2026 have until **2 December 2026**. It amends Art. 50(7) (codes of practice approved by implementing act). | <https://artificialintelligenceact.eu/ai-act-explorer/digital-omnibus/>, <https://artificialintelligenceact.eu/article/111/> |
| Code of Practice on Transparency of AI-Generated Content | **Final version published.** “The Commission and the AI Board have confirmed that the code is an adequate voluntary tool to demonstrate compliance”. Page last updated 31 July 2026; about 190 signatories by end of July. Voluntary. | <https://digital-strategy.ec.europa.eu/en/policies/code-practice-ai-generated-content> and its PDF (`ec.europa.eu/newsroom/dae/redirection/document/129555`) |
| California AI Transparency Act (SB 942, amended by AB 853) | Bus. & Prof. Code §§ 22757–22757.6. Chapter **operative 2 August 2026** (§ 22757.6). Large online platforms and GenAI hosting platforms: **1 January 2027**. Capture device manufacturers: **1 January 2028**. | leginfo, consolidated text: <https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml?lawCode=BPC&division=8.&title=&part=&chapter=25.&article=> |
| China: CAC *Measures for Labeling AI-Generated Synthetic Content* (人工智能生成合成内容标识办法) | In force since **1 September 2025** (Art. 14). | <https://www.cac.gov.cn/2025-03/14/c_1743654684782215.htm> |
| China: **GB 45438-2025** (网络安全技术 人工智能生成合成内容标识方法) | Published 2025-02-28, in force **2025-09-01**, status 现行 (current) on openstd. `GB` prefix without `/T`: mandatory. **The text of the standard could not be read** (openstd only serves it in an image viewer); its Annex E is known through the TC260 guides that reproduce it. | <https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=F32EA2A561F1886CD8D606513512D547> |
| TC260 practice guides TC260-PG-20257A (video), 20258A (text), 20259A (image), 202510A (audio), V1.0-202508 | Published by the TC260 committee, “基于 GB 45438-2025”. They fix where the AIGC field goes in each format. | PDFs linked from <https://www.tc260.org.cn/tc260/sjzn/list_2.shtml> |
| C2PA Technical Specification 2.2 | Current (2.3 is out; § 18.14.2 read in 2.2). | <https://spec.c2pa.org/specifications/specifications/2.2/specs/C2PA_Specification.html> |
| IPTC Photo Metadata Standard 2025.1 and the Digital Source Type vocabulary | Current (vocabulary released 2024-10-23). | <https://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata>, <https://cv.iptc.org/newscodes/digitalsourcetype/> |

**What could NOT be verified:**

- The **values of `Label`** in the AIGC label (GB 45438-2025 Annex E). Secondary sources
  give `1`, `2` and `3`; the TC260 guides only show `"Label":"value1"`. Hence
  CN-45438-004 is a warning `[unverified]`.
- The mapping **Label ↔ 属性信息 (content attribute), ContentProducer ↔
  服务提供者名称或者编码 (provider name or code), ProduceID ↔ 内容编号 (content number)** is
  inferred from Art. 5 of the Measures and the key names; Annex E, which fixes it, was
  not read. Hence CN-45438-003 is a warning `[unverified]`. No citation in this document
  relies on Annex E except those two rules.
- The **CAWG identity assertion** specification (Creator Assertions Working Group) was
  not read. C2PA-009 only relays what `c2pa-python` reports, as a warning `[unverified]`.
- The **official EUR-Lex** text of the AI Act and the Omnibus: FLI's reproduction, which
  states it is the Official Journal text, was read instead.

---

## Technical rules (always on)

### FMT-001 — Unsupported format

- **Severity:** undetermined
- **How it is checked:** by byte signature, not by extension. Supported: JPEG, PNG,
  WebP, AVIF/HEIF, MP4/MOV, MP3 and WAV. If no file can be read, the exit code is `2`.

### FMT-002 — The container has an anomalous structure

- **Severity:** warning
- **How it is checked:** the parser found a truncated segment, chunk, frame or box, an
  impossible size, or a form v0.1 does not read (JPEG ExtendedXMP, unsynchronised ID3).
  Whatever came after may not have been read.

### FMT-003 — The file cannot be read

- **Severity:** undetermined
- **How it is checked:** the path does not exist, is not a regular file, or cannot be
  read (permissions, I/O). The other files are still checked, and the exit code is `2`
  because the tool could not look at everything it was asked to.

### XMP-001 — Unreadable XMP packet

- **Severity:** warning
- **How it is checked:** the packet is not well-formed XML, contains neither
  `x:xmpmeta` nor `rdf:RDF`, or declares a DTD or entities (XMP never does; rejected
  before parsing).

### C2PA-001 — A C2PA manifest is present but cannot be read

- **Severity:** error
- **Literal:** “If the C2PA Manifest Store was located then the hard binding assertion
  present in its active manifest shall be used to validate that it is the matching
  manifest and whether the asset has been modified without manifest updates.”
- **Source:** C2PA 2.2, “Validation” — <https://spec.c2pa.org/specifications/specifications/2.2/specs/C2PA_Specification.html> (accessed 2026-10-02)
- **How it is checked:** the file contains the signature of a C2PA manifest store — a
  JUMBF description box (`jumd`) followed by the C2PA UUID
  `63327061-0011-0010-8000-00AA00389B71` — and `c2pa-python` cannot read it. The mark is
  there, and no validator will be able to read it. Loose `jumb`/`c2pa` substrings (for
  instance an orphan XMP `dcterms:provenance="self#jumbf=/c2pa/…"`) are **not** a
  manifest. When the library fails on a file *without* that signature (“Boxes are too
  deeply nested”, “Invalid RIFF format”), C2PA is reported absent and the library's
  message goes to FMT-002.

### C2PA-002 — The C2PA manifest fails validation

- **Severity:** error
- **Literal:** the same validation clause; the failure codes
  (`assertion.dataHash.mismatch`, `assertion.bmffHash.mismatch`,
  `claimSignature.mismatch`…) are those defined by the specification.
- **Source:** C2PA 2.2, “Validation” — <https://spec.c2pa.org/specifications/specifications/2.2/specs/C2PA_Specification.html> (accessed 2026-10-02)
- **How it is checked:** any failure code on the active manifest that is neither a
  trust code (`*.untrusted`, see C2PA-003) nor a CAWG code (`cawg.*`, see C2PA-009). This is the “present but
  invalid” case the EasyxLab S3 study measured in 6 out of 6 exiftool edits after
  signing: **a check that only asks “is there a manifest?” passes it.**

### C2PA-003 — Trust in the signer could not be established

- **Severity:** undetermined
- **Literal:** “It is then necessary to verify a chain of trust from the credential to
  an entry in one of the applicable trust anchor lists. If this chain of trust cannot
  be verified, the claim shall be rejected with a failure code of
  signingCredential.untrusted”
- **Source:** C2PA 2.2, “Validation” — <https://spec.c2pa.org/specifications/specifications/2.2/specs/C2PA_Specification.html> (accessed 2026-10-02)
- **How it is checked:** signature and hashes validate, but a `*.untrusted` code is
  reported (`signingCredential.untrusted`, `timeStamp.untrusted`,
  `cawg.x509.credential.untrusted`…). Which trust list applies depends on the
  verifier, not on the file: `--trust-anchors PEM` evaluates against the one you give.

### C2PA-004 — The manifest does not start with c2pa.created or c2pa.opened

- **Severity:** error
- **Literal:** “There shall be at least one actions assertion present in either the
  created_assertions or gathered_assertions array of the Claim of a standard C2PA
  Manifest. […] If the asset was created de novo (for example, […] generating the
  media by a generative AI model), then the actions array in the first c2pa.actions
  assertion […] shall have a c2pa.created action as its first element.” And for edited
  assets: “shall have a c2pa.opened action as its first element”. And: “This
  requirement does not apply to Update Manifests.”
- **Source:** C2PA 2.2, § 18.14.2 — <https://spec.c2pa.org/specifications/specifications/2.2/specs/C2PA_Specification.html> (accessed 2026-10-02)
- **How it is checked:** in the active manifest (claim v2 or later; not applied to v1
  claims, nor to Update Manifests — recognised because they carry no hard-binding
  `c2pa.hash.*` assertion) there is no `c2pa.actions*` assertion, or its first action is
  neither `c2pa.created` nor `c2pa.opened`.

### C2PA-005 — The c2pa.created action does not declare a digitalSourceType

- **Severity:** error
- **Literal:** “For all assets, a corresponding digitalSourceType field, with an
  appropriate value, shall be recorded with the c2pa.created action, to indicate the
  nature of the asset at its inception.”
- **Source:** C2PA 2.2, § 18.14.2 — <https://spec.c2pa.org/specifications/specifications/2.2/specs/C2PA_Specification.html> (accessed 2026-10-02)
- **How it is checked:** the first action is `c2pa.created` without `digitalSourceType`.
  The manifest exists but does not say “AI”. (`c2pa-rs` 0.91 refuses to sign this; the
  test fixture is built with its post-signing verification turned off.)

### C2PA-006 — digitalSourceType outside the IPTC and C2PA vocabularies

- **Severity:** warning
- **Literal:** “An action may include a digitalSourceType key, whose value shall be one
  of the terms defined by the IPTC or a C2PA specific value from the list below”
- **Source:** C2PA 2.2, “Actions” — <https://spec.c2pa.org/specifications/specifications/2.2/specs/C2PA_Specification.html> (accessed 2026-10-02)
- **How it is checked:** a `digitalSourceType` is neither a URI under
  <http://cv.iptc.org/newscodes/digitalsourcetype/> (`https://` also accepted) nor
  `http://c2pa.org/digitalsourcetype/{empty,trainedAlgorithmicData}`. A warning because
  the vocabulary grows and a new term is not a defect of the file.

### C2PA-007 — C2PA could not be validated: c2pa-python is missing

- **Severity:** undetermined
- **Literal:** the validation clause of C2PA 2.2 (signature, chain and hashes).
- **Source:** C2PA 2.2, “Validation” — <https://spec.c2pa.org/specifications/specifications/2.2/specs/C2PA_Specification.html> (accessed 2026-10-02)
- **How it is checked:** the file contains C2PA data and the official library cannot be
  imported on this platform. Cryptographic validation is never reimplemented.

### C2PA-008 — Only a reference to a remote manifest, not a manifest

- **Severity:** warning
- **Literal:** the validation clause of C2PA 2.2: a manifest is validated against the
  *hard binding* of the content at hand.
- **Source:** C2PA 2.2, “Validation” — <https://spec.c2pa.org/specifications/specifications/2.2/specs/C2PA_Specification.html> (accessed 2026-10-02)
- **How it is checked:** there is no embedded manifest and `c2pa-python` reports a
  remote reference (XMP `dcterms:provenance`). **ai-mark-lint never follows it**
  (`remote_manifest_fetch = false`): a CI linter does not make requests dictated by the
  file it audits. It does not count as a mark: the S3 study measured that, when the
  reference survives in a derivative, the hash fails against the original's manifest
  (3 out of 3).

### C2PA-009 — A CAWG identity assertion does not validate [unverified]

- **Severity:** warning
- **Literal:** not available: the CAWG identity assertion specification was not read.
- **Source:** reported by `c2pa-python`; C2PA 2.2 — <https://spec.c2pa.org/specifications/specifications/2.2/specs/C2PA_Specification.html> (accessed 2026-10-02)
- **How it is checked:** a `cawg.*` failure code that is not a trust code. CAWG
  assertions are outside the core C2PA specification, so they never make the manifest
  invalid here.

### IPTC-001 — XMP DigitalSourceType is not a URI from the IPTC vocabulary

- **Severity:** warning
- **Literal:** “Iptc4xmpExt:DigitalSourceType [URI <External>]” · “Data type: CV-code /
  Cardinality: 0..1” · “Required: Digital Source Type NewsCodes”.
- **Source:** IPTC Photo Metadata Standard 2025.1, “Digital Source Type” — <https://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata> (accessed 2026-10-02)
- **How it is checked:** the value is not a vocabulary URI. The typical mistake is the
  bare code (`trainedAlgorithmicMedia`) instead of the full URI.

### MARK-001 — The file's marks contradict each other about AI origin

- **Severity:** warning
- **Literal:** Art. 50(2): outputs must be “marked in a machine-readable format and
  detectable as artificially generated or manipulated”; and C2PA § 18.14.2: the
  `digitalSourceType` must have “an appropriate value”.
- **Source:** <https://artificialintelligenceact.eu/article/50/> (accessed 2026-10-02)
- **How it is checked:** C2PA declares an AI source type and IPTC XMP a non-AI one, or
  the other way round. Each detector will believe the mark it reads.

## European Union (`--jurisdiction eu`)

### EU-50-2-001 — No machine-readable metadata marks the file as AI-generated

- **Severity:** warning
- **Literal:** “Providers of AI systems, including general-purpose AI systems,
  generating synthetic audio, image, video or text content, shall ensure that the
  outputs of the AI system are marked in a machine-readable format and detectable as
  artificially generated or manipulated. Providers shall ensure their technical
  solutions are effective, interoperable, robust and reliable as far as this is
  technically feasible […]”. Transitional rule (Art. 111(4), Regulation (EU)
  2026/1744): “Providers of AI systems […] that have been placed on the market before
  2 August 2026 shall take the necessary steps in order to comply with Article 50(2) by
  2 December 2026.”
- **Source:** <https://artificialintelligenceact.eu/article/50/> and <https://artificialintelligenceact.eu/article/111/> (accessed 2026-10-02)
- **How it is checked:** no readable C2PA with an AI `digitalSourceType` (in the active
  manifest or an ingredient), no AI `Iptc4xmpExt:DigitalSourceType`, no AIGC label with
  a `Label`. AI types: `trainedAlgorithmicMedia`, `compositeWithTrainedAlgorithmicMedia`,
  `compositeSynthetic` (IPTC) and `trainedAlgorithmicData` (C2PA). **A warning, not an
  error**: Art. 50(2) does not mandate a format, and an imperceptible watermark — which
  this tool cannot see — may comply.

### EU-COP-001 — The AI mark is only in unsigned metadata

- **Severity:** warning
- **Literal:** “If content is generated, manipulated or exported in a data format that
  supports attaching metadata (e.g., an audio, image, video, or containerised text),
  Signatories will record information in the metadata on whether the content is
  AI-generated or manipulated. All recorded information will be digitally signed and
  time-stamped (on systems where time information is available) in a secure and
  tamper-evident manner.”
- **Source:** Code of Practice on Transparency of AI-Generated Content, Sub-measure 1.1.1 — <https://digital-strategy.ec.europa.eu/en/policies/code-practice-ai-generated-content> (accessed 2026-10-02)
- **How it is checked:** there is an AI declaration (IPTC XMP, AIGC, or a C2PA whose
  signature does not validate) but no validly signed C2PA manifest declaring it. A
  warning: the Code is voluntary, although the Commission and the AI Board have declared
  it adequate to demonstrate compliance.

### EU-COP-002 — The signed C2PA manifest has no timestamp

- **Severity:** warning
- **Literal:** as EU-COP-001: “digitally signed and time-stamped (on systems where time
  information is available)”.
- **Source:** Code of Practice, Sub-measure 1.1.1 — <https://digital-strategy.ec.europa.eu/en/policies/code-practice-ai-generated-content> (accessed 2026-10-02)
- **How it is checked:** the valid manifest declaring AI has no signing time from a TSA
  (`signature_info.time` empty).

## California (`--jurisdiction ca`)

It only binds *covered providers*: “a person that creates, codes, or otherwise produces
a generative artificial intelligence system that has over 1,000,000 monthly visitors or
users and is publicly accessible within the geographic boundaries of the state”
(§ 22757.1(d)). The tool cannot know whether you are one.

### CA-942-001 — No latent disclosure found

- **Severity:** warning
- **Literal:** “(b) A covered provider shall include a latent disclosure in
  AI-generated image, video, or audio content, or content that is any combination
  thereof, created by the covered provider’s GenAI system that meets all of the
  following criteria: […] (3) The disclosure is consistent with widely accepted
  industry standards.” And § 22757.6: “This chapter shall become operative on August 2,
  2026.”
- **Source:** Cal. Bus. & Prof. Code § 22757.3(b) — <https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml?lawCode=BPC&division=8.&title=&part=&chapter=25.&article=> (accessed 2026-10-02)
- **How it is checked:** no readable C2PA manifest, no IPTC XMP, no AIGC label. A
  warning: the law does not fix the format, and a watermark or a link could comply.

### CA-942-002 — The latent disclosure does not state the provider's name

- **Severity:** warning
- **Literal:** “(1) To the extent that it is technically feasible and reasonable, the
  disclosure conveys all of the following information, either directly or through a
  link to a permanent internet website: (A) The name of the covered provider.”
- **Source:** § 22757.3(b)(1)(A) — <https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml?lawCode=BPC&division=8.&title=&part=&chapter=25.&article=> (accessed 2026-10-02)
- **How it is checked:** neither a C2PA signer (`signature_info.issuer` or
  `common_name`) nor an AIGC `ContentProducer`.

### CA-942-003 — The latent disclosure does not state the GenAI system's name and version

- **Severity:** warning
- **Literal:** “(B) The name and version number of the GenAI system that created or
  altered the content.”
- **Source:** § 22757.3(b)(1)(B) — <https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml?lawCode=BPC&division=8.&title=&part=&chapter=25.&article=> (accessed 2026-10-02)
- **How it is checked:** no C2PA action with a `softwareAgent` that has a name and a
  version, and no `claim_generator_info` with a version. IPTC and AIGC have no field
  for this.

### CA-942-004 — The latent disclosure does not state the creation date and time

- **Severity:** warning
- **Literal:** “(C) The time and date of the content’s creation or alteration.”
- **Source:** § 22757.3(b)(1)(C) — <https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml?lawCode=BPC&division=8.&title=&part=&chapter=25.&article=> (accessed 2026-10-02)
- **How it is checked:** neither `when` in the C2PA actions nor a TSA signing time.
  (Manifests produced by c2patool with its defaults have neither.)

### CA-942-005 — The latent disclosure has no unique identifier

- **Severity:** warning
- **Literal:** “(D) A unique identifier.”
- **Source:** § 22757.3(b)(1)(D) — <https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml?lawCode=BPC&division=8.&title=&part=&chapter=25.&article=> (accessed 2026-10-02)
- **How it is checked:** no C2PA manifest label (`urn:c2pa:…`), no AIGC `ProduceID`,
  no `xmpMM:InstanceID`/`DocumentID`.

All five CA rules are warnings: the items are required “to the extent that it is
technically feasible and reasonable” and may be given through a link.

## China (`--jurisdiction cn`, not on by default)

### CN-45438-001 — The implicit AIGC label is missing from the metadata

- **Severity:** error
- **Literal:** “服务提供者应当按照《互联网信息服务深度合成管理规定》第十六条的规定，在生成合成内容的文件元数据中添加隐式标识，隐式标识包含生成合成内容属性信息、服务提供者名称或者编码、内容编号等制作要素信息。”
  (Art. 5: service providers shall add an implicit label to the file metadata of
  generated content, containing the content attribute, the provider's name or code and
  the content number) · “本办法自2025年9月1日起施行。” (Art. 14). And the image guide:
  “RDF 中新增自定义命名空间 TC260，URI 为 http://www.tc260.org.cn/ns/AIGC/1.0/ […] 在 TC260 空间下 AIGC 键值中填入 GB 45438-2025 附录 E 规定字符串”.
- **Source:** <https://www.cac.gov.cn/2025-03/14/c_1743654684782215.htm> and TC260-PG-20259A/20257A/202510A — <https://www.tc260.org.cn/tc260/sjzn/list_2.shtml> (accessed 2026-10-02)
- **How it is checked:** no `AIGC` key in any of the places the guides fix: XMP
  `TC260:AIGC` (any format; APP1 in JPEG, iTXt in PNG, the `XMP ` chunk in WebP); image
  guide Annex B: EXIF `UserComment` (JPEG/WebP) and `tEXt` “AIGC” (PNG); audio: RIFF
  chunk `AIGC` (WAV) and ID3v2 `TXXX` with description `AIGC` (MP3); video: key `AIGC`
  in `moov.udta.meta` (keys/ilst) (MP4/MOV). **An error** because, unlike the EU and
  California, the Chinese rules do say the label goes in the file metadata. A C2PA
  manifest does not replace it.

### CN-45438-002 — The AIGC label is not a readable JSON object

- **Severity:** error
- **Literal:** the guides serialise the value as
  `{"Label":"value1","ContentProducer":"value2","ProduceID":"value3","ReservedCode1":"value4","ContentPropagator":"value5","PropagateID":"value6","ReservedCode2":"value7"}`
  (“GB 45438—2025 附录 E b）所定义的字符串”, the string defined in GB 45438-2025 Annex E
  b)), and Annex B wraps it in `{"AIGC":{…}}`.
- **Source:** TC260-PG-20259A clause 6 and Annex B; 202510A clause 6.1 (the guides, not
  GB 45438 itself) — <https://www.tc260.org.cn/tc260/sjzn/list_2.shtml> (accessed 2026-10-02)
- **How it is checked:** `json.loads` of the value fails or does not yield an object.
  Both the direct and the wrapped form are accepted in any location.

### CN-45438-003 — The AIGC label lacks an element of Art. 5 [unverified]

- **Severity:** warning
- **Literal:** “隐式标识包含生成合成内容属性信息、服务提供者名称或者编码、内容编号等制作要素信息” (Art. 5).
- **Source:** <https://www.cac.gov.cn/2025-03/14/c_1743654684782215.htm> (accessed 2026-10-02)
- **How it is checked:** `Label`, `ContentProducer` or `ProduceID` is missing or empty.
  `[unverified]` because which key carries which Art. 5 element is inferred from the key
  names: Annex E, which defines them, was not read.
  The propagation fields (`ContentPropagator`, `PropagateID`) are added by platforms
  (Art. 6) and not required from the producer.

### CN-45438-004 — Unrecognised Label value [unverified]

- **Severity:** warning
- **Literal:** not available: GB 45438-2025 Annex E could not be read at the source.
  The TC260 guides only show `"Label":"value1"`.
- **Source:** <https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=F32EA2A561F1886CD8D606513512D547> (accessed 2026-10-02; standard metadata only)
- **How it is checked:** `Label` is not `1`, `2` or `3` (values from secondary sources).

### CN-45438-005 — The file carries several AIGC labels that disagree

- **Severity:** warning
- **Literal:** Art. 5 (one label with the production elements) and the guides, which
  define a single value per file.
- **Source:** <https://www.cac.gov.cn/2025-03/14/c_1743654684782215.htm> (accessed 2026-10-02)
- **How it is checked:** more than one AIGC label, differing in `Label`,
  `ContentProducer` or `ProduceID`.

## Before/after comparison (`--before A --after B`)

The citation of these findings depends on the jurisdictions requested: EU → Art. 50(2)
(the published output must be marked) and Code of Practice Measure 1.2; California →
§ 22757.3.1(b); China → Art. 10 of the Measures. Literals:

- Code of Practice, Measure 1.2 a): “retain, and abstain from intentionally altering or
  removing, existing metadata markings, where such content is used as input and
  subsequently transformed by their AI system into an output.”
- § 22757.3.1(b): “A large online platform shall not, to the extent technically
  feasible, knowingly strip any system provenance data or digital signature that is
  compliant with widely adopted specifications adopted by an established
  standards-setting body from content uploaded or distributed on the large online
  platform.” (c): “This section shall become operative on January 1, 2027.”
- Art. 10: “任何组织和个人不得恶意删除、篡改、伪造、隐匿本办法规定的生成合成内容标识” (no
  organisation or individual may maliciously delete, tamper with, forge or conceal the
  labels).

They are `error` because the fact is certain — the mark was there and is gone — not
because the tool claims which rule obliges you to keep it in your case.

### DIFF-001 — The pipeline removed the C2PA manifest

- **Severity:** error
- **Literal:** see above.
- **Source:** <https://digital-strategy.ec.europa.eu/en/policies/code-practice-ai-generated-content>, <https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml?lawCode=BPC&division=8.&title=&part=&chapter=25.&article=> (accessed 2026-10-02)
- **How it is checked:** there was a readable manifest before; after, there is none or
  only a remote reference.

### DIFF-002 — The pipeline invalidated the C2PA manifest

- **Severity:** error
- **Literal:** see above.
- **Source:** same as DIFF-001 (accessed 2026-10-02)
- **How it is checked:** the signature validated before; after, the manifest is still
  there but does not validate or cannot be read (e.g. `assertion.dataHash.mismatch`
  after editing a field).

### DIFF-003 — The pipeline removed the IPTC AI DigitalSourceType

- **Severity:** error
- **Literal:** see above.
- **Source:** same as DIFF-001 (accessed 2026-10-02)
- **How it is checked:** before, an `Iptc4xmpExt:DigitalSourceType` declared AI; after,
  none does. (If the values change but still declare AI, that is DIFF-007; if the new set
  contains the old one, nothing is reported.)

### DIFF-004 — The pipeline removed the AIGC label

- **Severity:** error
- **Literal:** see above (Art. 10).
- **Source:** <https://www.cac.gov.cn/2025-03/14/c_1743654684782215.htm> (accessed 2026-10-02)
- **How it is checked:** there was at least one AIGC label before; after, none.

### DIFF-005 — The pipeline changed the AIGC label's production data

- **Severity:** warning
- **Literal:** see above (Art. 10: “篡改”, tamper with).
- **Source:** <https://www.cac.gov.cn/2025-03/14/c_1743654684782215.htm> (accessed 2026-10-02)
- **How it is checked:** no (`Label`, `ContentProducer`, `ProduceID`) triple after
  matches one before. Adding `ContentPropagator`/`PropagateID` is not a finding.

### DIFF-006 — The new C2PA manifest no longer declares AI origin

- **Severity:** warning
- **Literal:** C2PA § 18.14.2 (see C2PA-005).
- **Source:** <https://spec.c2pa.org/specifications/specifications/2.2/specs/C2PA_Specification.html> (accessed 2026-10-02)
- **How it is checked:** before, the C2PA declared AI; after, a valid manifest declares
  it neither in the active manifest nor in its ingredients (the step re-signed without
  keeping the original as an ingredient).

### DIFF-007 — The pipeline changed the IPTC DigitalSourceType

- **Severity:** warning
- **Literal:** see above.
- **Source:** same as DIFF-001 (accessed 2026-10-02)
- **How it is checked:** the set of values changed without losing an AI declaration (for
  example `trainedAlgorithmicMedia` → `compositeWithTrainedAlgorithmicMedia`), or changed
  on a file that never declared AI.

## Out of scope

- **Imperceptible watermarks** (Code of Practice Sub-measure 1.1.2) and fingerprinting
  (1.1.3): proprietary, each vendor ships its own detector.
- **Deepfakes and visible labels** (Art. 50(4), § 22757.3(a), China's explicit labels):
  the linter reads metadata, it does not look at the content.
- **Text** (Art. 50(2) covers text, and so does TC260-PG-20258A): v0.1 handles image,
  video and audio only.
- **Whether content is synthetic**: the tool reads what the file declares about itself.
