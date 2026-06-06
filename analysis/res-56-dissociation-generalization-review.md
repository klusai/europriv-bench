# RES-56 — Review gate: detection ≠ re-identification dissociation, generalization & paper-worthiness

**Date:** 2026-06-06
**Reviewer scope:** read-only sanity check of the committed dissociation artifacts. No re-scoring, no new measurement. Every number below is quoted from a committed file and cited inline.
**Status of underlying configs:** all `config_status=dev` — NOT citable/public. See caveats.

## 0. What the thesis claims (and what would falsify it)

> **detection ≠ re-identification.** A model can have strong/comparable PII *detection* F1 yet a very different *re-identification-protection* profile on decode-bearing national IDs. The kp-deid "protector" leaks ≈0% of the national ID while typed detectors leak substantially.

Re-identification here is reserved for the **deterministic national-ID channel** (the ID decodes to QIs: DOB/SEX/place/county). Name/QI residual is "residual distinctiveness", not re-id.

The dissociation is operationalised per language as a **Newcombe difference-of-proportions CI** on (detector national-ID leak-rate − kp-deid leak-rate). It "holds" for a detector if that CI excludes 0.

**Falsification I actively looked for:** (a) kp-deid leak materially above 0; (b) the high-detection-F1 models *not* leaking (which would collapse the dissociation); (c) coverage so thin that "holds" rests on 1–2 detectors; (d) the headline "comparable detection F1" being false.

## 1. Sanity — do PL (PESEL) and IT (codice fiscale) reproduce RO/CNP?

Source artifacts: `analysis/family_dissociation_ro_realskeleton.json` (RO, two families A+B), `analysis/pl_dissociation.json` (PL), `analysis/it_dissociation.json` (IT). F1 = token/entity detection F1 stored per model in those files.

| Lang | ID | kp-deid leak | Wilson UB (95%) | kp-deid F1 | best typed-detector F1 (model, leak) | detectors w/ gap-CI excl. 0 | Verdict |
|---|---|---:|---:|---:|---|:--:|:--:|
| RO (fam A) | CNP | 0.0000 (0/190) | 0.0198 | 0.733 | gliner 0.852 (leak 0.279) | 5/7 | HOLDS |
| RO (fam B) | CNP | 0.0000 (0/250) | 0.0151 | 0.495 | tabularisai 0.728 (leak 0.012) | 6/7 | HOLDS |
| PL | PESEL | 0.0000 (0/1096) | 0.0035 | 0.763 | gliner 0.825 (leak 0.578) | 5/7 | HOLDS |
| IT | codice fiscale | 0.0000 (0/224) | 0.0169 | 0.707 | gliner 0.858 (leak 0.397) | 6/7 | HOLDS |

**PL/PESEL (`pl_dissociation.json`).** kp-deid leaks 0/1096 national IDs (Wilson UB 0.0035 — the tightest in the set, because PL is scored on the full `pl-realskeleton-v1` board track, n=1500 docs → 1096 distinct subjects, and reconciles with `baselines/leaderboard.json` per RES-87). The detection winner, GLiNER, has the **highest** detection F1 of all models (0.825 > kp-deid's 0.763) yet leaks **57.8%** of PESELs (gap CI [0.549, 0.607]). 5 of 7 typed detectors have a gap CI excluding 0 (gliner, gliner2, openmed, spacy, tabularisai). The 2 that do not — presidio (own leak 0.000) and privacy-filter (own leak 0.001) — are themselves near-zero leakers; the CI fails to exclude 0 because *two protectors agree*, NOT because the dissociation broke. **Verdict: HOLDS.**

**IT/codice fiscale (`it_dissociation.json`).** kp-deid leaks 0/224 (Wilson UB 0.0169). GLiNER again highest detection F1 (0.858 > kp-deid 0.707) yet leaks 39.7%; presidio leaks 96.4% (gap CI [0.927, 0.982]). 6 of 7 typed detectors' gap CIs exclude 0; the lone exception is privacy-filter (own leak 0.004 — again a protector, not a failure). **Verdict: HOLDS.**

**RO/CNP baseline (`family_dissociation_ro_realskeleton.json`).** Both authored families hold (A: 5/7, B: 6/7). Note family B: kp-deid detection F1 is only 0.495 — *below* gliner (0.606) and tabularisai (0.728) — yet kp-deid still leaks 0% while gliner leaks 100% and presidio 90%. The summary row aggregates both families (14 detector arms, 11 excluding 0; worst-case Wilson UB 0.0198).

PL and IT reproduce the RO pattern cleanly, with the **same mechanism**: the model that wins on detection F1 (GLiNER) is among the worst at re-id protection, and the protector (kp-deid) achieves ≈0 national-ID leak.

### Honest correction to the headline wording
The phrase "comparable/strong detection F1" is **only partly true and should not be the load-bearing claim.** GLiNER out-scores kp-deid on detection F1 in **every** language (0.81–0.86 vs kp-deid 0.71–0.79), and in RO-family-B and legal, kp-deid is *clearly below* the best detector (0.495 and 0.600). The honest and stronger framing is: **detection-F1 ranking does not predict re-id-protection ranking** — the F1 leader leaks heavily while a model that is at best F1-comparable (sometimes F1-inferior) leaks ≈0. That is the dissociation, and it survives this scrutiny.

## 2. Generalization across all 11 decode-bearing languages

Sources: per-language `analysis/{ro,pl,it,se,cz,dk,fi,ee,lt,si,sk}_dissociation.json` (RO via the family file) and the consolidated `analysis/dissociation_summary.json`. GLiNER leak/F1 quoted from each per-language `models.gliner` block.

| Lang | ID | kp-deid leak | Wilson UB | gap-CI excl.0 | GLiNER F1 / leak (highest-F1 model) | Models scored | Holds |
|---|---|---:|---:|:--:|---|:--:|:--:|
| RO | CNP | 0.0000 | 0.0198 | 11/14 | 0.852 / 0.279–1.000 | 8 | YES |
| PL | PESEL | 0.0000 | 0.0035 | 5/7 | 0.825 / 0.578 | 8 | YES |
| IT | codice fiscale | 0.0000 | 0.0169 | 6/7 | 0.858 / 0.397 | 8 | YES |
| SE | personnummer | 0.0000 | 0.0163 | 3/4 | 0.819 / 1.000 | 5 | YES |
| CZ | rodné číslo | 0.0000 | 0.0171 | 3/4 | 0.850 / 0.674 | 5 | YES |
| DK | CPR-nummer | 0.0000 | 0.0167 | 4/4 | 0.829 / 0.854 | 5 | YES |
| FI | henkilötunnus | 0.0000 | 0.0166 | 4/4 | 0.823 / 0.877 | 5 | YES |
| EE | isikukood | 0.0000 | 0.0165 | 3/4 | 0.838 / 0.782 | 5 | YES |
| LT | asmens kodas | 0.0000 | 0.0166 | 3/4 | 0.810 / 0.974 | 5 | YES |
| SI | EMŠO | 0.0000 | 0.0172 | 3/4 | 0.834 / 0.364 | 5 | YES |
| SK | rodné číslo | 0.0000 | 0.0160 | 3/4 | 0.821 / 0.996 | 5 | YES |
| **legal (RO)** | CNP | **0.0407** | 0.0519 | 7/7 | 0.803 / — | 8 | YES |

**The consistent signal.** kp-deid leaks **exactly 0** national IDs in all 11 languages (Wilson UB ≤ 0.020 everywhere; tightest 0.0035 PL). In **every** language GLiNER has the **highest detection F1** (0.81–0.86) of all models scored, yet leaks **36.4%–100%** of national IDs. That single, uniform contrast — best detector by F1 ↔ among worst by protection, vs. kp-deid 0% — is the cleanest statement of the dissociation and it is present in 11/11 languages plus the RO legal domain.

**Where it does not "hold" per detector — and why that is not a counterexample.** Every detector whose gap CI fails to exclude 0 is itself a near-zero national-ID leaker: presidio (PL/EE/LT/SI/SK, leak 0.000) and privacy-filter (PL/IT/SE/CZ, leak 0.000–0.014). These are protectors agreeing with kp-deid, not the dissociation breaking. So the "3/4" and "5/7" tallies understate consistency: no scored detector with a non-trivial leak rate failed the test. I found **no language where a high-leak detector's gap CI included 0** — i.e., no genuine counterexample to the thesis.

**Second channel (name-in-context, RO, `name_in_context_leak_ro_realskeleton.json`).** kp-deid: id-leak 0.0000 [0,0.0087], name-leak 0.0000 [0,0.0056]; spacy id-leak 0.905 [0.873,0.929]; presidio name-leak 0.137 [0.113,0.164]. Consistent with the anchor channel. Per program discipline this is *residual distinctiveness*, NOT a population re-id rate (no k-anonymity diagnostic — KLU-122).

### Heterogeneity / weaknesses I am obligated to flag

1. **Coverage is uneven and thin in 8 of 11 languages.** RO/PL/IT/legal score all 8 board models; the Nordic set (SE/CZ/DK/FI) and Baltic set (EE/LT/SI/SK) score only **5 models each, and they are *different* fives** — Nordic includes openmed-free {gliner, gliner2, privacy-filter, tabularisai}; Baltic includes {presidio, spacy} instead of {privacy-filter, tabularisai}. So no single non-kp model is scored across all 11. The cross-language claim rests on **gliner + gliner2 + kp-deid** as the only models present everywhere.
2. **Per-language n is small outside RO/PL.** Most languages have ~224–232 scored subjects (IT 224, SE 232) on **a single authored template family**. RO is the only language with two independent families. Single-family means template-specific artifacts cannot be ruled out (KLU-101).
3. **Detection-F1 "comparability" is not uniform** (see §1 correction): kp-deid is the F1 leader in *zero* languages; GLiNER is. The claim must be framed as ranking-dissociation, not "kp-deid matches detection while winning protection."
4. **kp-deid is not a perfect protector in the legal domain** — leak 0.0407 (UB 0.0519). Still ~0 relative to typed detectors and the dissociation holds (7/7), but the protector is not literally 0% everywhere; the headline "≈0%" must carry "in the synthetic ID-card track; 4% in legal."

## 3. Paper-worthiness decision (acceptance criterion)

**Verdict (2026-06-06): YES, conditionally — it strengthens the Papers 1/3 generalization claim, with the scope tightened as below.** The dissociation is not a RO/CNP artifact: it reproduces on PL/PESEL and IT/codice fiscale at full board coverage, and the uniform GLiNER-vs-kp-deid contrast generalizes to 11/11 decode-bearing national IDs + the RO legal domain + a second (name-in-context) RO channel. I found **no counterexample** (no high-leak detector with a gap CI overlapping 0). This is a defensible "partial→strong" outcome, not a rubber stamp.

### Exact claim the paper may make
> "Across 11 EU decode-bearing national identifiers, the detection-F1 ranking of PII models does **not** predict their re-identification-protection ranking on the deterministic national-ID channel: the highest-detection-F1 model (GLiNER, F1 0.81–0.86) leaks 36–100% of national IDs, while the kp-deid protector leaks ≈0% (0/N in 10/11 languages; 4.1% in the RO legal domain). We present this as the first **unified** multi-language demonstration of the detection ≠ re-identification dissociation."

### Mandatory caveats the claim MUST carry
- **"First *unified*"**, never "first" — it consolidates prior per-language measurements (RES-86), not a first observation of the phenomenon.
- **All configs `config_status=dev`. NOT a SOTA or citable claim.** Before any public/citable use, two gates must clear: native-speaker / IAA validation (RES-77) and a consistent full-model re-score (RES-53). State this verbatim wherever the result is reported.
- **Cross-language coverage rests on 3 models** (gliner, gliner2, kp-deid) present in all 11; only RO/PL/IT/legal have all 8. Scope the 11-language claim to "consistent on the models scored per language"; reserve the strong 8-model statement for RO/PL/IT.
- **Single authored template family** in every language except RO. A second independent family per language is required before citation (KLU-101).
- **Re-identification reserved for the national-ID channel.** The name/QI channel is *residual distinctiveness* on synthetic data, NOT population re-id; no k-anonymity diagnostic (KLU-122).
- **kp-deid is ≈0%, not literally 0%, in the legal domain (4.07%).** Report the legal number explicitly rather than folding it into "0%."

### If a reviewer insists on a narrower claim
The fully bullet-proof core (full 8-model coverage, RO with two families) is **RO + PL + IT**. The Nordic/Baltic 8 are supporting evidence of breadth on a reduced model panel. Scoping to "demonstrated at full coverage on RO/PL/IT, replicated on a reduced panel across 8 further languages" is honest and still supports the generalization narrative.

## Provenance
All figures quoted from committed artifacts: `analysis/dissociation_summary.{md,json}`, `analysis/family_dissociation_ro_realskeleton.json`, `analysis/{pl,it,se,cz,dk,fi,ee,lt,si,sk}_dissociation.json`, `analysis/legal_dissociation.json`, `analysis/name_in_context_leak_ro_realskeleton.json`. No re-scoring was performed for this review.
