# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: SemVer.

## [0.1.1] — 2026-10-03

### Fixed
- **False C2PA-002 on valid manifests signed with standard C2PA certificates.** The c2pa
  context was built without an extended-key-usage list, and c2pa-rs then behaved as if
  that list were empty. Certificates whose EKU is C2PA claim signing, `documentSigning`
  or Microsoft's C2PA OID were reported as `signingCredential.invalid` — among them
  OpenAI's 2026 certificates (issued by Trufo, on the official C2PA Trust List) and
  Microsoft's. ai-mark-lint now always passes c2pa-rs's own default EKU list. Found by
  EasyxLab study S6, which measured 187 such false errors among 623 manifests on
  Wikimedia Commons.
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
