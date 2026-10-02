# ai-mark-lint

<img alt="EasyxLab tool" src="https://raw.githubusercontent.com/easybytehub/ai-mark-lint/main/.github/badge-tool.svg">

**Checks, in CI or locally, that the synthetic images, video and audio you generate or
publish still carry the machine-readable AI marks the law asks for — and cites the
article for every finding.**

It reads the three marks that exist in practice — a **C2PA manifest** (validated with the
official `c2pa-python` library), **IPTC `DigitalSourceType`** in XMP, and the **`AIGC`
implicit label** of China's GB 45438-2025 — and checks them against:

- **EU AI Act, art. 50(2)** — applicable since 2 August 2026 (2 December 2026 for systems
  already on the market, per the Digital Omnibus, Regulation (EU) 2026/1744), and the
  Commission's **Code of Practice on Transparency of AI-Generated Content**.
- **California AI Transparency Act** (SB 942 as amended by AB 853, Bus. & Prof. Code
  §§ 22757–22757.6) — operative since 2 August 2026; platform duties from 1 January 2027.
- **China**: the CAC *Measures for Labeling AI-Generated Synthetic Content* and
  **GB 45438-2025**, in force since 1 September 2025, with the TC260 practice guides that
  fix where the label goes in each file format.

It also has a compare mode: **`--before A --after B` checks a file before and after
your pipeline** (resize, CDN, CMS, re-encode) and tells you which marks
were lost or broken on the way.

```console
$ ai-mark-lint --before generated.jpg --after edited.jpg

ai-mark-lint · 2 file(s) · jurisdictions: eu,ca · before/after mode

ERROR        DIFF-002 [edited.jpg]: The pipeline invalidated the C2PA manifest
             Before: valid. After: invalid (assertion.dataHash.mismatch).
             The step kept the manifest but changed the content: re-sign with the
             original as an ingredient, or do not touch the bytes.
             citation: Regulation (EU) 2024/1689 (AI Act), Art. 50(2); Code of Practice
             on Transparency of AI-Generated Content, Measure 1.2; Cal. Bus. & Prof. Code
             § 22757.3.1(b) (AB 853; operative January 1, 2027)

1 error · 0 warnings · 0 undetermined
Zero errors means these rules found no breach in the metadata; it does not certify
compliance, and invisible watermarks were not checked.
```

(That pair is real: a file signed with the c2patool test certificate, then one field
edited with exiftool. The manifest is still in the file; its signature no longer
matches.)

## Who it is for

- **Providers of generative systems** that must mark their outputs: put a sample of your
  system's outputs through it on every change, so a refactor that drops the
  `digitalSourceType` or breaks the signature shows up in the pull request.
- **Anyone who publishes synthetic media through a pipeline** (CMS, image CDN,
  transcoder): run the before/after mode on each step. The EasyxLab S3 study measured
  that **no "keep metadata" option preserved C2PA after re-encoding (0/136)**, and that
  editing one field with exiftool after signing **leaves the manifest in the file with a
  broken signature (6/6)** — a check that only asks "is there a manifest?" passes it.

## What it is, and what it is not

**It reads what a file declares about itself.** It does not tell whether content is
synthetic, and it is meant to be run on files your system generated or manipulated with
AI. On a camera photo, its findings make no sense.

**It does not see invisible watermarks.** Art. 50(2) does not mandate a format, and the
Code of Practice asks for *two* layers: signed metadata **and** an imperceptible
watermark. Watermarks are proprietary and only their vendor can detect them. That is why
a file with no metadata marks is a **warning** for the EU and California, not an error:
it may be compliant through a watermark this tool cannot see. Only in China, where the
rules say the label goes in the file metadata, is its absence an **error**.

**It does not cover deepfake disclosure** (art. 50(4)), visible labels (Cal. § 22757.3(a),
China's explicit labels) or text.

**A clean result does not certify compliance.** It means these rules found no breach in
the metadata of these files. Whether you are a "covered provider" (California's
1,000,000-monthly-users threshold), a signatory of the Code of Practice, or a service
provided in China is not something a file can tell.

**It never goes to the network.** A file may point to a remote manifest; following that
link would make a CI linter an HTTP client steered by the file it audits. A remote
reference is reported as "reference only" (C2PA-008), never as a valid mark.

## Install

```bash
pip install ai-mark-lint
```

Python 3.11+. One runtime dependency, on purpose: `c2pa-python`, the C2PA's official
library. Validating a manifest means verifying a COSE signature, an X.509 chain and
hashes over the file; reimplementing that would be inventing cryptography in a tool whose
whole value is being believable. Everything else — XMP, EXIF, PNG/RIFF chunks, ID3, MP4
boxes, HEIF — is parsed with the standard library. If `c2pa-python` cannot load on your
platform, the tool keeps working and reports C2PA as undetermined (C2PA-007).

## Use

```bash
ai-mark-lint outputs/*.jpg outputs/*.mp4                # EU + California (default)
ai-mark-lint outputs/* --jurisdiction eu,ca,cn          # add China
ai-mark-lint outputs/* --jurisdiction none              # only technical C2PA/IPTC checks
ai-mark-lint outputs/* --format json                    # or sarif
ai-mark-lint outputs/* --strict                         # warnings fail too
ai-mark-lint outputs/* --trust-anchors trust.pem        # evaluate the C2PA signer
ai-mark-lint --before original.png --after cdn.webp     # what did the pipeline lose?
```

Formats, detected by their bytes and not by extension: JPEG, PNG, WebP, AVIF/HEIF,
MP4/MOV, MP3, WAV.

**Exit codes:** `0` no errors · `1` errors (or warnings with `--strict`) · `2` the tool
could not do its job (a file it could not read, no supported format, invalid trust
anchors, bad arguments, an internal error). A missing file does not stop the others from
being checked: the report covers them and the exit code is still `2`. Warnings and
undetermined findings do not fail by default: a tool that breaks the build over what it
could not determine gets switched off within a week.

China (`cn`) is opt-in because it is the only jurisdiction where a missing label is an
error, and it only binds services provided in China.

### In CI (GitHub Actions)

With SARIF output the findings show up in the repository's **Security** tab:

```yaml
name: ai-marks
on: [push, pull_request]
permissions:
  contents: read
jobs:
  marks:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
        with:
          persist-credentials: false
      - run: python generate_samples.py --out samples/   # your system's real outputs
      - uses: easybytehub/ai-mark-lint@94d400d98de666cff9bd6595ac88cd0a96a29a87  # v0.1.0
        with:
          files: |
            samples/*.jpg
            samples/*.mp4
          jurisdiction: "eu,ca"
          fail: "false"            # let the SARIF upload run, then fail on your terms
      - uses: github/codeql-action/upload-sarif@2892aa5e19bbd11bc0cff5427e3b750a04d9e3c2  # v4.38.2
        if: always()
        with:
          sarif_file: ai-mark-lint.sarif
```

The action is composite and **installs ai-mark-lint from its own code**
(`github.action_path`), not from PyPI: the commit you pin in `uses:` is exactly what
runs. Pin it by SHA, as above. `files` takes one path or glob per line; names with
spaces are fine. When the tool exits with `2` (nothing readable, bad trust anchors) the
action still leaves a minimal valid SARIF, so `upload-sarif` with `if: always()` does not
fail on its own. Note that `actions/setup-python` inside the action changes the job's
Python for the steps that follow; set `python-version` accordingly.

## What it checks

Full list, with the literal sentence of each rule, its URL, the date it was read and how
it is checked: **[SPEC.md](SPEC.md)**. In short:

| Family | Rules |
|---|---|
| C2PA | manifest unreadable (error) · fails validation, e.g. content changed after signing (error) · signer, timestamp or identity credential not trusted (undetermined) · CAWG identity assertion fails *[unverified]* · first action not `c2pa.created`/`c2pa.opened` (error) · `c2pa.created` without `digitalSourceType` (error) · unknown source type · remote reference only |
| IPTC / XMP | `DigitalSourceType` not a vocabulary URI · unreadable XMP · C2PA and IPTC contradict each other |
| EU | no machine-readable AI mark in metadata · AI mark only in unsigned metadata · signed manifest without a timestamp (Code of Practice 1.1.1) |
| California | no latent disclosure · missing provider name, system name and version, creation time or unique identifier (§ 22757.3(b)(1)(A)–(D)) |
| China | no `AIGC` label where the TC260 guides put it · not JSON · missing `Label`/`ContentProducer`/`ProduceID` *[unverified]* · unknown `Label` value *[unverified]* · conflicting labels |
| Before/after | C2PA removed · C2PA invalidated · IPTC AI type removed (error) or changed (warning) · AIGC removed · AIGC producer data rewritten · new manifest no longer declares AI |

Requirements that could not be read in the primary source are marked `[unverified]` and
are never errors. Today there are three: the meaning of the `Label` values and which AIGC
key carries which element of Art. 5 (both defined in GB 45438-2025 Annex E, whose text is
only served as images), and the CAWG identity assertion codes (C2PA-009), whose
specification was not read.

## Limitations (v0.1)

- No watermark detection, no soft-binding lookup, no remote manifests.
- HEIF/AVIF XMP is found by scanning the raw bytes, not by resolving `iloc`.
- JPEG ExtendedXMP and unsynchronised ID3 tags are flagged, not read.
- No GIF, TIFF, FLV, MKV/WebM or text, although the TC260 guides cover them.
- Trust lists are yours to provide (`--trust-anchors`); without one, every real
  signer is "untrusted" (an undetermined finding, not an error).

## Development

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy
.venv/bin/python scripts/generar-fixtures.py     # regenerate the ffmpeg-made media
```

Fixtures are documented in [tests/fixtures/README.md](tests/fixtures/README.md). **No
private key is committed:** each test session creates a throwaway test CA in a temporary
directory, signs the fixtures there and deletes it, and a test fails if a key ever lands
in the tree. The before/after pairs in `tests/fixtures/s3/` come unmodified from the EasyByte
Lab S3 study and were produced by real tools (sharp, ImageMagick, Pillow, ffmpeg,
exiftool, the next/image optimizer).

A rule is a function `Marcas -> list[Hallazgo]`; its ID, severity and citation live once,
in `src/ai_mark_lint/catalogo.py`, and a test keeps `SPEC.md` in sync. A new rule needs
the literal citation, a justified severity and a test that fires it and one that does
not. When a rule and the law disagree, the law is right and the rule is a bug.

## License

[Apache-2.0](LICENSE).

## Maintained by

EasyxLab, the research lab of EasyByte Hub S. Coop. Mad., a software cooperative in Spain.

---

EasyxLab · a research lab by [EasyByte](https://easybyte.es)
