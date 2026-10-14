# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: SemVer.

## [0.1.3] — unreleased

First release on PyPI. California's law changed on 30 September 2026, two days before
0.1.0: the California rules now cite the text in force. No rule fires on files where it
did not fire before, or stops firing where it did.

### Changed — California
- **The law.** SB 1000 (Stats. 2026, ch. 861), an urgency statute in force since
  30 September 2026, amended Bus. & Prof. Code §§ 22757.1–22757.5. The latent disclosure
  moved from § 22757.3(b) to § 22757.3(a): its items are now (a)(1)(A)–(F), with
  (B) reading “name and version information”, a new (E) “Whether the GenAI system
  created or altered the content” and, from 1 January 2029, (F) whether the system is
  designed to primarily function as assistive technology; it is required “to the extent
  it is technically feasible” (no longer “and reasonable”). The manifest (visible)
  disclosure is gone. A “covered provider” (now § 22757.1(e)) is anyone who produces a
  GenAI system publicly accessible in California: the 1,000,000-users threshold is
  gone. § 22757.3(b) is now the duty to notify licensees. AB 2713 (Stats. 2026,
  ch. 856), operative 1 January 2027, rewrites § 22757.3.1: the large online platforms'
  duty not to strip provenance data becomes (c), and AB 853's (b) never applies.
- **The tool.** CA-942-001 cites § 22757.3(a) and CA-942-002 to CA-942-005 cite
  § 22757.3(a)(1)(A)–(D), “SB 942, as amended by AB 853 and SB 1000”, and link to the
  § 22757.3 page on leginfo. SPEC quotes the text in force, read on 2026-10-14. The
  CA-942-001 message no longer says that only systems with over 1,000,000 monthly users
  are bound; it quotes § 22757.1(e). The note on CA-942-002 to CA-942-005 quotes
  “to the extent it is technically feasible”. With `ca`, before/after findings cite
  § 22757.3.1(c) as amended by AB 2713 instead of § 22757.3.1(b) of AB 853. Rule IDs
  are unchanged: SB 942 is still the act's bill.
- **Not checked**, and now said in SPEC and README: item (E), and item (F), which only
  applies from 2029. The README no longer cites § 22757.3(a) as a visible-label duty;
  no rule checked the manifest disclosure, so none is withdrawn.
- The descriptions in `action.yml` and `pyproject.toml` name SB 942 as amended by AB 853
  and SB 1000.

### Fixed
- README: the S3 figure for C2PA after re-encoding is 0/124, the outputs of Pillow,
  sharp (also with the call chain of the `next/image` optimizer), ImageMagick and
  ffmpeg. The 0/136 it gave also counted 12 ExifTool strip/restore outputs, which are
  not re-encodings.
- README: `pip install ai-mark-lint` is marked as pending publication on PyPI, with the
  command that works until then; links to SPEC, LICENSE and the fixtures are absolute,
  so they also work on PyPI.
- Two code comments and one SPEC note no longer cite the withdrawn S6 study.
- README: editing a field with exiftool after signing does not break the signature, as
  it said: the signature still verifies, and the manifest is invalid because the content
  hash it signs no longer matches the file.
- README and the fixtures README: the S3 `next/image` pairs were made by sharp with the
  call chain of the `next/image` optimizer, not by Next.js itself.

### Changed
- SPEC compares the C2PA sections it quotes with C2PA 2.4 (April 2026) and explains
  why it keeps citing 2.2. The requirement that a `c2pa.opened` action reference its
  ingredient, which 2.4 repeats in § 18.15.2, was already in 2.2 (§ 18.14.4.7 and
  § 15.10.3.2.2): c2pa-rs enforces it and ai-mark-lint reports it as C2PA-002, now
  pinned by a fixture.
- The release workflow runs the tests, ruff and mypy before building.
- CI still runs the GitHub Action on the S3 fixtures, but no longer uploads their SARIF
  to code scanning: those files break the rules on purpose. It checks instead that the
  SARIF is version 2.1.0 and has findings.

## [0.1.2] — 2026-10-03

### Added
- **CN-45438-006 (warning): the AIGC label is JSON-encoded twice.** Some generators
  store the label object as a JSON *string*. ai-mark-lint 0.1.0–0.1.1 reported it as
  CN-45438-002 and did not count the file as marked; it now reads the label, counts it,
  and warns that a reader following the TC260 guides would miss it. Found by EasyxLab
  study S6 (withdrawn on 2026-10-05).

### Changed
- When C2PA-003 comes from a certificate that expired after a time-stamped signature with
  an untrusted time-stamp authority, the message now says so. SPEC documents why this is
  reported as a trust question rather than a rejection, quoting C2PA 2.2 § 15.8.2.

## [0.1.1] — 2026-10-03

### Fixed
- **False C2PA-002 on valid manifests signed with standard C2PA certificates.** The c2pa
  context was built without an extended-key-usage list, and c2pa-rs then behaved as if
  that list were empty. Certificates whose EKU is C2PA claim signing, `documentSigning`
  or Microsoft's C2PA OID were reported as `signingCredential.invalid` — among them
  OpenAI's 2026 certificates (issued by Trufo, on the official C2PA Trust List) and
  Microsoft's. ai-mark-lint now always passes c2pa-rs's own default EKU list. Found by
  EasyxLab study S6 (withdrawn on 2026-10-05).
- **A certificate that expired after a time-stamped signature is no longer an error
  when the time-stamp authority is not trusted.** c2pa-rs then checks the certificate
  at today's date; whether it was valid when signed depends on trusting that TSA, so it
  is reported as a trust question (C2PA-003), not as an invalid manifest. Without a
  time-stamp, an expired certificate is still C2PA-002.

### Changed
- The lab behind the tool is now called EasyxLab; one diagnostic message that cites
  its S3 study uses the new name.

## [0.1.0] — 2026-10-02

First release.

### Added
- `ai-mark-lint` CLI with text, JSON and SARIF output. Options: `--jurisdiction
  eu,ca,cn|none` (default `eu,ca`), `--format text|json|sarif`, `--strict`,
  `--before A --after B`, `--trust-anchors PEM`, `--no-color`.
- Exit codes: `0` no errors, `1` errors (or warnings with `--strict`), `2` the tool could
  not do its job. Unreadable files are reported (FMT-003) without stopping the others;
  invalid trust anchors and internal errors exit `2` with a one-line message, never a
  traceback.
- Pure-Python reading of JPEG, PNG, WebP, AVIF/HEIF, MP4/MOV, MP3 and WAV (XMP, EXIF
  UserComment, PNG/RIFF chunks, ID3v2 TXXX, `moov.udta.meta`), hardened against hostile
  files (nested RIFF lists, truncated ID3 headers, impossible box sizes).
- C2PA validation with `c2pa-python` 0.38 (c2pa-rs 0.91), offline. A manifest is
  detected by the JUMBF `jumd` box with the C2PA UUID, not by loose substrings. Trust
  codes (`*.untrusted`) are undetermined, never errors; CAWG identity codes are reported
  apart; Update Manifests are exempt from § 18.14.2.
- 35 rules: technical (C2PA, IPTC, XMP, container), EU (Art. 50(2), Art. 111(4) and the
  Code of Practice), California (§ 22757.3(b)), China (CAC Measures, GB 45438-2025, TC260
  guides) and before/after comparison. A rule not verified at its source is never an
  error; three are tagged `[unverified]`.
- Compare mode `--before A --after B`: which marks a pipeline removes or breaks; losing
  the IPTC AI declaration is an error, changing it is a warning.
- `SPEC.md` with the literal sentence, URL and access date of every rule.
- GitHub Action (composite, installs from its own code), CI workflow and release
  workflow (build, provenance attestation, GitHub Release, PyPI via Trusted Publishing
  once enabled). Every third-party action pinned by SHA with its exact version.
- Tests: fixtures built at test time with a throwaway CA (no private key in the
  repository), 13 before/after pairs from the EasyxLab S3 study and four public
  c2pa-rs fixtures that reproduce the false positives of an adversarial review.
