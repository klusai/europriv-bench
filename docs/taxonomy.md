# The harmonized KP (KlusAI Privacy) taxonomy

**Framing:** this is **standardization infrastructure**, not a new taxonomy. Every target
scheme below is mature. The contribution is *one GDPR-aligned crosswalk* unifying them
across **general + legal + clinical** for European jurisdictions, with explicit:

- **GDPR Art. 4 / Art. 9** mapping (Art. 9 = special-category data, e.g. health → higher leakage stakes).
- **Direct vs. quasi-identifier** marking (à la TAB / MultiGraSCCo) — quasi-identifiers
  drive *re-identification risk*, the benchmark's headline metric.

Labels use **BIOES**, so the space is directly compatible with `openai/privacy-filter`.
The machine-readable source of truth is `src/europriv_bench/taxonomy.py` (and a versioned
YAML in a later phase); this document is the human-facing crosswalk + paper appendix.

## Tiers

- **Core** — the shared base (overlaps OpenAI's 8 + AI4Privacy core). Every language/domain split uses it.
- **Clinical** — PHI, anchored on HIPAA's 18 identifiers, GDPR Art. 9 aware.
- **Legal** — legal quasi-identifiers, anchored on MAPA.

## Crosswalk (seed — expanded with the full ~50 types during Phase 0/1)

| KP type | Tier | ID class | GDPR Art.9 | OpenAI | AI4Privacy | HIPAA | MAPA |
|---|---|---|---|---|---|---|---|
| PERSON | core | direct | | private_person | GIVENNAME/SURNAME/… | names | PERSON |
| ADDRESS | core | quasi | | private_address | STREET/CITY/ZIPCODE | geo_subdivisions | ADDRESS |
| EMAIL | core | direct | | private_email | EMAIL | — | — |
| PHONE | core | direct | | private_phone | TELEPHONENUM | — | — |
| URL | core | quasi | | private_url | — | — | — |
| DATE | core | quasi | | private_date | DATE | dates | — |
| ACCOUNT_ID | core | direct | | account_number | ACCOUNTNUM/IDCARDNUM/… | account/ssn | — |
| SECRET | core | direct | | secret | PASSWORD | — | — |
| MRN | clinical | direct | | — | — | medical_record_numbers | — |
| HEALTH_CONDITION | clinical | quasi | ✅ | — | — | — | — |
| PROVIDER | clinical | quasi | | — | — | —¹ | — |
| FACILITY | clinical | quasi | | — | — | — | —² |
| CASE_NUMBER | legal | direct | | — | — | — | AMOUNT |
| COURT | legal | quasi | | — | — | — | —² |
| STATUTE_REF | legal | quasi | | — | — | — | — |
| ORG_PARTY | legal | quasi | | — | — | — | ORGANIZATION |

¹ HIPAA `names` → **PERSON** (general owner); PROVIDER is a KP-native refinement not
recoverable from the flat source label. ² MAPA `ORGANIZATION` → **ORG_PARTY**; FACILITY/COURT
are KP-native refinements. Rule: each native label maps to exactly one KP type (native→KP is a
function), enforced at import by `crosswalk.py`.

## Coverage gaps surfaced by live curation (AI4Privacy, 2026-05-30)

Captured now (no label-space change): `CREDITCARDNUMBER`, `DRIVERLICENSENUM` → ACCOUNT_ID;
`TIME` → DATE. **Deferred** (need new entity types — bump `TAXONOMY_VERSION` when added):
`AGE`, `SEX` (GDPR-sensitive: SEX is Art.9-adjacent — design as special-category?), `TITLE`
(honorific; PERSON-adjacent). The curation script logs all dropped labels so coverage stays auditable.

## Open crosswalk decisions (resolve in Phase 1)

- Whether to split PERSON into role-typed sub-labels (patient vs. provider vs. legal party)
  — affects re-identification scoring and cross-scheme comparability.
- How to map AI4Privacy's 79 industry labels and OpenMed's 54 without inflating the core
  label space (likely: keep core tight, expose finer types as an optional extended config).
- GDPR Art. 9 coverage beyond HEALTH_CONDITION (religion, ethnicity, biometrics, sexual
  orientation) — add as quasi-identifiers with special-category flags.
