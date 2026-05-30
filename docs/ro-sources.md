# Romanian skeleton sources & legal basis (for `ro-realskeleton-v1`)

Findings from a deep-research pass (2026-05-30, ~109 agents, adversarially verified). This is the
sourcing + legal basis for the **real-skeleton + synthetic-PII** Romanian gold. Verdict:
**defensible and buildable**, strongest in the legal/legislative domain.

## Legal basis (verified high-confidence)

- **Copyright — official texts are NOT protected.** Romanian Law 8/1996 **Art. 9(b)** excludes
  "textele oficiale de natură politică, legislativă, administrativă, judiciară și traducerile
  oficiale ale acestora" — i.e. **legislation AND court decisions** are not copyrightable and may
  be reused as skeletons. `legislatie.just.ro/Public/Termeni` states this explicitly. (Does NOT
  remove (a) portal database sui-generis rights, or (b) GDPR duties on residual personal data.)
- **GDPR — only TRULY anonymised data is out of scope** (Recital 26 + WP216): must defeat
  singling-out, linkability, and inference by all means reasonably likely. **Pseudonymisation ≠
  anonymisation** — initials-only/partially-redacted RO court decisions **remain personal data**
  and must be scrubbed + synthetic-PII-substituted before any CC-BY release.
- **Law 190/2018** (RO GDPR implementer): **Art. 4** governs the CNP/national-ID → a CC-BY
  benchmark must contain **no real CNPs** (synthetic substitution sidesteps this). **Art. 7**
  (journalistic/academic derogation) is **not** a blanket research exemption — cannot rely on it
  to ship residual real PII.
- **Quality signal:** CSM replaced the ROLII portal with **ReJust (Mar 2022)** citing ROLII's
  failure to meet anonymisation standards → published RO decisions have documented anonymisation
  gaps → **scrubbing is mandatory**, not optional.

## Source shortlist (verdicts)

| Domain | Source | Verdict | Notes |
|---|---|---|---|
| Legal | **Legislation** — legislatie.just.ro, Monitorul Oficial | ✅ **CC-BY-OK** (skeleton) | Not copyrightable; statutory text has little/no residual personal data → cleanest skeleton. |
| Legal | **Court decisions** — ReJust / portal.just.ro / ECLI-RO | ⚠️ **needs-scrub** | Not copyrightable, but pseudonymised-only → scrub residual PII + inject synthetic. |
| Legal | EUR-Lex Romanian | ✅ CC-BY-OK | EU official texts; reusable. |
| Clinical | **CNAS `SCRISOARE MEDICALĂ`** discharge-letter template (2024) | ✅ **CC-BY-OK** (skeleton) | Official template with CNP / `cod unic de asigurare` (CASS) / name / DOB slots + labeled clinical narrative structure — ideal scaffolding. |
| Clinical | MoH clinical practice guidelines | ⛔ **mostly not-usable** | Many carry **NON-COMMERCIAL** reuse terms incompatible with CC-BY — exclude those. |
| Admin | Official government/CNAS form templates | ✅ CC-BY-OK | Public official forms; reusable scaffolding. |

## Reusable prior corpora (licenses)

| Corpus | License | Verdict |
|---|---|---|
| **RONEC v2.0** (RO named-entity) | **MIT** | ✅ reusable (CC-BY-compatible) |
| LegalNERo (RO legal NER, MARCELL subset) | **CC-BY-NC-ND** | ⛔ DO NOT redistribute (NC + ND) |
| MoNERo (RO biomedical NER) | corpus **CC-BY-SA** (paper CC-BY) | ⛔ copyleft — exclude from CC-BY-clean set |
| MARCELL (RO legal corpus) | copyleft / NC | ⛔ encumbered |

## Recommended scrub procedure (before synthetic-PII injection)

1. Strip residual direct/partial identifiers (initials, residual names, signatures, file IDs).
2. **Period-shift dates** (consistent per-document offset).
3. **Generalize localities** (commune→county or coarser).
4. **Break decision-chain links** (don't carry first-instance↔appeal↔ÎCCJ references that re-link).
5. **Neutralize rare-fact phrasing** (unusual circumstances enabling inference).
6. Inject synthetic RO PII (CNP/IBAN/CUI/plate/phone/address via `ro_generators`).
7. **Validate**: native-speaker review + inter-annotator agreement on a sample; confirm no
   singling-out/linkability remains.

## DO NOT USE
- Real CNPs or any real litigant/patient PII in a redistributed artifact (Law 190/2018 Art. 4).
- MoH guidelines with NON-COMMERCIAL terms; LegalNERo (NC-ND); MoNERo & MARCELL (copyleft/NC).
- ROLII (decommissioned; anonymisation-quality issues).

## Recommendation
**Lead with legal**: legislation skeletons (cleanest — non-copyright, minimal residual PII) +
scrubbed ReJust decisions. **Clinical** via the official CNAS SCRISOARE MEDICALĂ template (not the
NC guidelines). Reuse **RONEC (MIT)** for entity coverage; exclude the NC/ND/SA corpora. All real
PII scrubbed + replaced with synthetic; CC-BY release is defensible once truly anonymised.

_Full cited report: workflow run `w8o388h5n` (sources incl. legislatie.just.ro/Public/Termeni,
WIPO Lex Law 8/1996, GDPR Recital 26 / WP216, Law 190/2018, CNAS template, RONEC MIT)._
