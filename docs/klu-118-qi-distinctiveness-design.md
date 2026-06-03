# KLU-118 — Design decision: a second, non-token re-identification mechanism

**Status:** design-panel-approved spec (synthesis of a 3-expert panel: re-id methodologist,
reference-population/licensing engineer, adversarial red-team). Implementation staged v1 → v2.
Everything here is `config_status=dev` and gated on KLU-27 (native-speaker + IAA) before any public
headline use.

## Problem

EuroPriv-Bench's headline finding — *detection-F1 does not track re-identification protection* — is
currently demonstrated only on **decode-bearing national IDs** (RO CNP, PL PESEL, IT codice fiscale):
a deterministic, single-token decode leak. Three identifiers in three languages are still the **same
mechanism**. To stop the thesis resting on one concept we want a **second, independent** mechanism
that is *not* a single structured token, and to test whether the dissociation reproduces there. A
null/weak result is an acceptable, even valuable, outcome — it would sharpen the claim to "the
dissociation is specific to structured, decode-bearing identifiers."

## Decision (staged)

### v1 — ship now (assumption-light, defensible)

1. **Name-in-context residual leak = the v1 second mechanism.** A leaked `PERSON` full name that the
   model left **un-redacted** (computed on the *post-detection residual*, not raw text) is a
   re-identifying signal that needs **no reference-population model**. Measured per distinct subject,
   same unit shape as the national-ID anchor `(doc, country, subject)`, with a **Wilson CI**, and a
   **2×2 cross-tab** vs. the national-ID anchor (a subject can be ID-leaked, name-leaked, both, or
   neither — the scientific point is the *independence* of the channels).
2. **k-anonymity-violation rate = an exploratory diagnostic, clearly labelled.** Over the residual QI
   tuple, report the **within-corpus equivalence-class-size distribution** (histogram) and the
   k=1 / k<5 violation rates — labelled **"sample distinctiveness, not population re-identification."**
   Cheap, reference-free, auditable. Never a headline number.
3. **Claim language (hard rule, from the red-team).** Do **not** say "re-identification rate" for the
   QI channel on synthetic data. Use **"residual quasi-identifier distinctiveness"** /
   **"k-anonymity-violation rate."** Reserve "re-identification" for the deterministic national-ID
   anchor. Report the equivalence-class distribution, never a single scalar headline.

### v2 — the rigorous population metric (PURR), once prerequisites land

The full **Population-Uniqueness Re-id Rate (PURR@τ)** — Rocher–Hendrickx–de Montjoye (2019)
individual uniqueness `ξ(x) = 1 − p(x)^(n−1)`, default **τ=0.95** (their calibrated ~5–6.7% FDR
operating point), computed on the **post-detection residual** QI tuple, aggregated per subject with a
**Wilson CI**, reported alongside `F1_QI` and `ΔPURR` (= baseline − model) so the dissociation is
visible, plus mean `κ` (re-id correctness) as a secondary scalar. Lead with **model rankings and
ΔPURR**, which are robust to the reference-population choice; treat absolute PURR as
reference-conditional. Adopt the **prosecutor** attacker framing (El Emam/Dankar); journalist/marketer
are reportable variants.

**v2 is blocked on two prerequisites** (this is the crux the panel surfaced):

- **A cleanly-licensed reference population** (the denominator) — *solved in design* (see below).
- **A census-calibrated generator** (the numerator). On synthetic documents, QI *values* are whatever
  the generator drew, so PURR against a real census is only meaningful once the benchmark's QI values
  are **sampled from that same census joint** (otherwise "uniqueness" measures the generator's
  sampling temperature, not realistic distinctiveness). This ties to the synthetic-to-real drift work
  (KLU-103) and the LocalePack generators. **Until the generator is calibrated, PURR stays an
  internal sensitivity analysis, not a reported metric.**

## Reference-population design (the denominator — cleanly licensed, reproducible)

Primary: a per-country **synthetic joint** over the frozen QI schema, fitted by **Iterative
Proportional Fitting** from published census **cross-tabulations**, with a **Gaussian-copula**
population-uniqueness estimator (Rocher 2019) on top. Sources + verified licenses:

| Source | Role | License (verified) | Redistribute / commercial |
|---|---|---|---|
| **Eurostat 2021 Census Hub** (hypercubes) | workhorse, all EU countries, uniform | Commission Decision **2011/833/EU** (+CC BY 4.0 editorial) | **yes / yes**, attribution |
| **ISTAT** (IT supplements) | finer IT joints | **CC BY 3.0** | yes / yes |
| **GUS** (PL supplements) | finer PL joints | **CC BY 4.0** | yes / yes |
| **INS/Romania** | RO — **route via Census Hub** (TEMPO terms murky) | ROU-OGL / CC BY 3.0 | yes, attribution |
| **Rocher 2019** uniqueness method/code | the estimator | **CC BY 4.0** | yes / yes, cite |
| ~~IPUMS-International microdata~~ | statistically ideal but **DISQUALIFIED** | per-user, **no redistribution, no commercial** | **NO** |

Module `europriv_bench/refpop/`: vendored + **SHA-256-checksummed** sources with a `manifest.yaml`
(dataset code, retrieval date, license, attribution); deterministic offline `build_joint.py`
(IPF, pinned tolerance) → sparse joint; `uniqueness.py` lookup API; `fallbacks.py`
(marginal-independence + in-sample, both **labelled weaker**); `report.py` auto-emits the required
attributions; a **CI license-gate** test that fails the build on any source whose license isn't on the
allowlist (`CC-BY-4.0`, `CC-BY-3.0`, `EU-2011/833`, `ROU-OGL`). Health `condition` has no census
cross-tab → approximate via conditional-independence given (age, sex) from prevalence tables, **flagged
explicitly** (not ground truth).

## QI schema (frozen, versioned — `schema.py`)

v1 fields: **DOB/age** (exact → year → 5-yr band → decade), **sex**, **locality/postcode** (postcode →
locality → NUTS-2 → country), **nationality**, **profession** (→ ISCO-08 major group), **rare-condition
flag**. Direct identifiers (name, the IDs, email, phone) are **not** QIs (name has its own v1 channel).
Bins must match between eval QIs and census tables or the lookup is meaningless; schema version is part
of the dataset version string.

## Must-NOT-do (red-team)

- No "re-identification rate" / "X% re-identified" for the QI channel on synthetic data.
- No uniqueness from **independent marginals** presented as meaningful (correlations matter; label it an
  upper bound only).
- No single scalar headline without the equivalence-class distribution + the declared reference pop.
- No distinctiveness on **raw text** implying detection would've prevented it — always the
  post-detection residual (else the dissociation is illusory; this is the QI analogue of FM-6).
- No cross-reference-population number transfer; no promotion out of `dev` / no headline use before
  KLU-27 validation.
- Do **not** let the QI channel replace the structured-ID anchor as primary evidence — it corroborates.
- Do **not** suppress a null/weak QI result — pre-register it as an acceptable, thesis-sharpening
  outcome.

## Literature

Sweeney 2002 (k-anonymity); Rocher, Hendrickx & de Montjoye 2019, *Nat. Commun.* 10:3069 (individual
uniqueness / copula, CC BY 4.0); Dankar & El Emam 2010 (prosecutor/journalist/marketer); El Emam,
*Guide to the De-Identification of Personal Health Information* (risk-based de-id, ARX).
