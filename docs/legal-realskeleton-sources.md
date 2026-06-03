# Legal real-skeleton sources & verified licenses (for `legal-realskeleton-v1`, KLU-111)

The legal-domain real-skeleton track is a **bounded proof-of-concept** that the EuroPriv-Bench
harness generalizes to the **legal domain** — the roadmap's under-served, differentiating domain.
It ships `config_status=dev`, a **single authored template family** (the legal genre), and the same
per-distinct-subject re-identification accounting + Wilson CIs as the RO/PL/IT real-skeleton tracks.

## What the track contains

Three **authored** legal-document skeletons that reproduce the public **section structure** of the
legal-document types the EU privacy world runs on — populated with synthetic CNP-bearing PII
(valid-checksum CNP whose encoded date matches the stated DOB, CUI, +40 phones, addresses):

| Document type | Structure modelled on | Sections reproduced (authored boilerplate) |
|---|---|---|
| EUR-Lex-style legal instrument | EU legislation layout (EUR-Lex) | titled act → numbered recitals "Întrucât (n)…" → numbered "Articolul n" provisions → "Adoptată la … " |
| ECHR-style court judgment | ECHR judgment structure (HUDOC) | caption `CAUZA … ÎMPOTRIVA ROMÂNIEI` + application no. → `ÎN FAPT` → `ÎN DREPT` → `PENTRU ACESTE MOTIVE, INSTANȚA` |
| GDPR Article 15 DSAR response | data-controller access-request reply | identification → categories of data → recipients → retention → rights; repeats the applicant CNP in the identity-confirmation line |

## Licensing — STRUCTURE ONLY, no redistributed text (the load-bearing KLU-111 guard)

The shipped artifact contains **no copyrighted source text**. Every sentence is original boilerplate
and every identifier/party is synthetic, so there is **no residual real PII by construction**
(GDPR-clean) and the artifact is **CC-BY-4.0**-redistributable. Two source-license facts were
verified (2026-06-03) and are recorded in `klusai-datasets/conf/datasets.yaml`:

- **EUR-Lex — clean (reuse authorised), but not relied on.** General reuse of Commission documents is
  authorised under **Commission Decision 2011/833/EU** (reuse permitted, attribution `© European
  Union`, no exclusive rights). We do **not** redistribute any EUR-Lex text — only the
  (uncopyrightable) section-layout convention — so even this permission is not load-bearing.
  Independently, Romanian Law 8/1996 **Art. 9(b)** excludes official legislative/judicial texts from
  copyright (see `ro-sources.md`).
  Source: <https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011D0833>
- **ECHR / HUDOC — RESTRICTED → no text used.** ECHR/HUDOC reuse is permitted only "for private use
  or … information and education" with `© ECHR-CEDH` attribution, and HUDOC translations are
  **copyright-protected**. This is **NOT** cleanly redistributable under the program's license gate
  (`klusai.privacy.datasets.data.licensing.assert_clean_license`), so **no ECHR/HUDOC text is
  included** — we reproduce only the public judgment *structure* (caption → facts → law → operative
  parts), which is not copyrightable.
  Source: <https://www.echr.coe.int/copyright-and-disclaimer>

A falsifiable test (`klusai-datasets/tests/test_ro_skeletons_legal.py::test_no_source_text_redistributed`)
asserts distinctive verbatim phrases from the real instruments (e.g. the French ECHR formula
`PAR CES MOTIFS, LA COUR`, `Official Journal of the European Union`, `© ECHR-CEDH`) never appear in
generated documents.

## Re-identification accounting (the dissociation in the legal domain)

Rows carry `country='RO'` so the harness `national_id_leakage` metric dispatches to the CNP
validator: a missed (un-redacted) CNP deterministically discloses **DATE_OF_BIRTH + SEX + COUNTY**.
Re-identification is counted **per distinct subject** `(document, country, normalized value)`
(KLU-49) — the DSAR response legitimately repeats the applicant CNP, so the repeat collapses to one
subject and never double-counts. The per-typed-detector difference-of-proportions (Newcombe CI) is
emitted by `analysis/legal_dissociation.py` (and `analysis/legal_dissociation.md`).

## Honesty caveats (same discipline as RO/PL/IT)

- `config_status=dev` — a citable-track candidate, **not** validated (pending native-speaker review +
  IAA); no SOTA / validated / citable claim (gated KLU-27).
- **Single authored template family** — a leak headline from one family is not validated
  generalization; a **second independent legal template family** is required before this is cited
  (the KLU-101 RO hardening, replicated for the legal track).
- Bounded PoC scope: **1 language (RO), 3 document types**. Cross-lingual legal breadth (DE/FR/PL via
  EUR-Lex structure) is the KLU-23 / KLU-30 epics, not this wave.
