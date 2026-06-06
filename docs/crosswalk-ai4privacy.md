# Ai4Privacy → KP taxonomy crosswalk (RES-93)

This is the committed field-comparability map between **Ai4Privacy's** PII classes and the
harmonized **KP** taxonomy (`europriv_bench.taxonomy`, v0.2.0). It doubles as documentation for the
external-synthetic detection track `ai4privacy-openpii-{lang}-v1` (adopted to break the F1 = 1.000
saturation of our own template-splice synthetic eval).

The crosswalk itself is **machine-defined** in
`src/europriv_bench/conf/taxonomy.yaml` under the `ai4privacy:` scheme (single source of truth,
inverted by `europriv_bench.crosswalk.to_kp`). This doc is the human-readable rendering + the
coverage/exclusion rationale. The native→KP map is a strict function (a native label maps to at most
one KP type); curation drops unmapped labels and **counts** them (no silent truncation), and every
produced span is validated byte-equal + strict BIOES via `europriv_bench.spans` (fail-loud on any
off-by-one).

## Source

- **Repo:** `ai4privacy/pii-masking-openpii-1m` — the verified-clean CC-BY-4.0 **open core**
  (1.43M rows, 23 EU languages, 19 PII classes). License verified live 2026-06-07; see the
  `klusai-datasets` manifest `conf/ai4privacy_openpii_manifest.yaml`.
- The 19-class label set is **fixed** across all languages in this release (confirmed by curation:
  the curated 10-language slice surfaced exactly these 19 native labels).

## The 19 Ai4Privacy classes → KP

| Ai4Privacy native | KP type | KP tier | identifier class |
|---|---|---|---|
| `GIVENNAME` | `PERSON` | core | direct |
| `SURNAME` | `PERSON` | core | direct |
| `EMAIL` | `EMAIL` | core | direct |
| `TELEPHONENUM` | `PHONE` | core | direct |
| `STREET` | `ADDRESS` | core | quasi |
| `CITY` | `ADDRESS` | core | quasi |
| `ZIPCODE` | `ADDRESS` | core | quasi |
| `BUILDINGNUM` | `ADDRESS` | core | quasi |
| `DATE` | `DATE` | core | quasi |
| `CREDITCARDNUMBER` | `ACCOUNT_ID` | core | direct |
| `TAXNUM` | `ACCOUNT_ID` | core | direct |
| `IDCARDNUM` | `NATIONAL_ID` | core | direct |
| `SOCIALNUM` | `NATIONAL_ID` | core | direct |
| `PASSPORTNUM` | `NATIONAL_ID` | core | direct |
| `DRIVERLICENSENUM` | `NATIONAL_ID` | core | direct |

15 of 19 native classes map cleanly onto KP core types.

## Intentionally unmapped (dropped + counted)

Four Ai4Privacy classes have **no clean KP entity** and are dropped during curation (counts are
recorded per run — observed counts in the 10×400-row curated slice in parentheses):

| Ai4Privacy native | why unmapped |
|---|---|
| `TITLE` (2006) | Honorific (Mr/Dr/…) — a name-adjacent token, not a PII entity in KP. Mapping to `PERSON` would inflate person recall with a closed-class function word. |
| `AGE` (1568) | Demographic quasi-identifier. KP has no demographic-attribute entity; adding one changes the BIOES label space (taxonomy version bump touching every config) — out of scope for an eval track. |
| `GENDER` (917) | Demographic quasi-identifier. Same rationale as `AGE`. |
| `SEX` (853) | Demographic quasi-identifier. Same rationale as `AGE`. |

Dropping (rather than force-mapping) keeps native→KP a clean function and avoids **inflating** a
core type — the same governance stance as the OpenMed/MAPA industry-label decision
(`docs/taxonomy.md`). The eval's fairness mask in the runner only scores the entity types the gold
annotates, so these dropped types are not counted against any model as false positives.

## Comparability notes

- KP `ADDRESS` is **coarser** than Ai4Privacy's 4 address sub-types (street/city/zip/building):
  Ai4Privacy annotates address components separately; KP merges them. Span boundaries therefore
  differ where Ai4Privacy tags two adjacent components that KP would treat as one region — handled
  by the per-token BIOES alignment, not by merging spans.
- KP `ACCOUNT_ID` absorbs both financial (`CREDITCARDNUMBER`) and fiscal (`TAXNUM`) identifiers;
  KP `NATIONAL_ID` absorbs the four government-issued IDs. This matches the existing OpenAI/HIPAA/
  OpenMed crosswalk grouping in `taxonomy.yaml`.
- Ai4Privacy has **no** URL, password/secret, or org/company class in this 19-class core, so KP
  `URL` / `SECRET` / `ORG_PARTY` simply never appear in the gold — an honest recall ceiling, not a
  miss.

## Contamination

Ai4Privacy is a **training substrate** for two board baselines: `openmed` and `tabularisai` were
trained on Ai4Privacy data, so they score every `ai4privacy-openpii-{lang}-v1` config as
`in_distribution` (not a fair held-out measurement for them). `kp-deid` (trained only on the KP
LocalePacks ro/en/pl, a **different** generator) is `clean_held_out` on the languages absent from
its training and honestly `unknown` on ro/en (a distinct Ai4Privacy generator in a trained
language). Rule-based / third-party systems (presidio/spacy/gliner/gliner2) are `clean_held_out`
on every config. Enforced in `europriv_bench.leaderboard.classify_contamination`.

## Headline result — saturation broken

Scored the board against these slices (80 rows/lang, computed by
`analysis/ai4privacy_openpii_saturation.py`; full numbers in
`analysis/ai4privacy_openpii_saturation.json` + `…_leaderboard.json`). On our own template-splice
synthetic, control detection F1 = **1.000** (de/fr/nl/pl/ro). On this external Ai4Privacy track the
board **de-saturates and spreads wide** — best F1 anywhere is **0.669** (tabularisai, fr,
`in_distribution`), and every language shows a 0.41–0.55 spread across models:

| model | F1 range (10 langs) | mean | contamination |
|---|---|---|---|
| tabularisai | 0.545 – 0.669 | 0.612 | `in_distribution` (trained on Ai4Privacy) |
| gliner | 0.497 – 0.608 | 0.541 | `unknown` |
| gliner2 | 0.456 – 0.577 | 0.502 | `clean_held_out` |
| kp-deid (kp-model) | 0.298 – 0.417 | 0.357 | `clean_held_out` (ro: `unknown`) |
| presidio | 0.246 – 0.377 | 0.299 | `clean_held_out` |
| spacy | 0.077 – 0.138 | 0.109 | `clean_held_out` (EN-only NER on multilingual structured PII) |
| dummy | 0.000 | 0.000 | — |

`privacy-filter` and `openmed` are **pending** on the full sweep: their MoE backends are too slow on
this Mac's CPU to score all the docs/lang in-session (both verified *runnable* — a 20-row probe gave
privacy-filter F1 ≈ 0.48, openmed ≈ 0.47 on `de`, both well below 1.0, consistent with the
non-saturation result). Numbers are computed, never hardcoded; rerun via the script above.
