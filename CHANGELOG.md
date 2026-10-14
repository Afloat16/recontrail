# Changelog

## Unreleased

- Read UTF-8 report fixtures with an explicit encoding so Windows locale defaults do not break the report test.
- Consume only the authenticated, size-checked remainder of rejected image uploads before returning an error, avoiding connection resets while clients are still sending. Discarding is limited to the declared body length and a 30-second deadline; oversized requests are still rejected without reading their bodies.
- Add HTTP regression coverage for large rejected uploads and immediate size-limit rejection.

## Repository launch documentation

- Make the homepage English-first, with a complete `README.zh-CN.md` and language navigation.
- Add English usage and validation summaries, accurate launch copy, and 20 relevant topic suggestions.
- Add canonical repository/documentation/issue links to package and citation metadata.
- Retain historical validation evidence and distinguish it from current remote CI status.


## 0.1.0 — 2026-10-08 source delivery

Initial implementation of a local capture-to-report workflow: photo diagnostics, conservative exact-pixel duplicate exclusion, match-graph diagnostics, CPU incremental sparse reconstruction, robust bundle adjustment, calibrated dense stereo, video frame selection, and standalone interactive reports.

Added PLY, camera JSON, normalized-image / COLMAP text exports, and an open stereo surface OBJ exporter. Added project locks, content signatures, completed-output reuse, provenance, per-project worker cancellation, and a token-protected loopback workbench.

Includes original synthetic fixtures, automated core / geometry / HTTP integration tests, optional PyCOLMAP 4.2.x adapter tests, documentation, upstream references, MIT source licensing, CI configuration and a first-publication script.

This entry records the source delivery, not a completed GitHub or PyPI release. Actual executed checks and remaining coverage gaps are recorded in `docs/VALIDATION.md`.
