# Evaluation Plan

**Status:** the harness does not exist and no metric has been measured. Nothing in this
document is a result. It states what will be measured, how, and against what, so that
the numbers reported later cannot be chosen after the fact.

The build plan is explicit that no accuracy percentage may be claimed without
validation evidence. This document exists to make that constraint operational.

## 1. What is being evaluated

Three separate things, which must not be conflated:

1. **Extraction quality** - did we read the receipt correctly?
2. **Policy-result correctness** - did the deterministic engine reach the right
   `PASS`/`FAIL`/`UNKNOWN` for a labelled claim/rule pair?
3. **Duplicate candidate quality** - does the candidate list contain the true pairs
   without drowning a reviewer in false ones?

A product can be excellent at one and useless at another, so they are reported
independently and never averaged into a single "accuracy" number.

## 2. Dataset requirements

**Dataset status: not supplied.** This is the primary blocker for the whole evaluation
plan and it is an open question in `docs/policy-assumptions.md`.

Required before any number can be reported:

- The actual receipt set, or a rights-cleared synthetic equivalent.
- A statement of what use is authorized, including whether any of it may be sent to an
  external AI provider.
- Human-labelled ground truth for the critical fields.

The labelled set must span the cases the problem statement describes, because a clean,
flat, machine-printed receipt set would produce a flattering and useless number:

| Case | Why it must be present |
|---|---|
| Clean, machine-printed | the baseline |
| Faded / low contrast | the most common real degradation |
| Rotated / skewed | tests orientation handling before hashing |
| Cropped (total present, merchant cut) | partial evidence must yield `UNKNOWN` for the missing field, not a guess |
| Handwritten / partially handwritten | a genuinely different failure mode |
| Itemised | required to test line-item arithmetic |
| Mixed currency | required to test "detect unknown currency rather than assuming" |
| Incomplete (no total visible) | must produce `UNKNOWN`, and the pipeline must not invent one |
| True duplicate pair, one image altered | positive pair for the detector |
| Hard negative: same amount and date, different merchant | the pair the detector must not escalate |

Note on prior work: earlier IndicOCR/PaddleOCR-VL experiments on electricity bills are
background only. They are **not** evidence of expense-receipt performance, and must not
be cited as such.

## 3. Extraction metrics

Per *critical* field - merchant, transaction date, total, currency - not per field
count:

| Metric | Definition |
|---|---|
| Exact match rate | string-identical after documented normalisation |
| Normalised match rate | case/whitespace/punctuation-normalised; merchant name variants counted here |
| Amount match rate | exact after decimal normalisation, reported separately from near-misses |
| Date match rate | exact after document-format normalisation |
| Missing-field detection | how often an absent field is reported absent rather than filled with a plausible wrong value. **This is the metric that matters most**, because a wrongly-filled total is worse than a blank one. |
| Correction rate | fraction of extracted fields a human subsequently changed |
| Latency | per-receipt wall time, reported per provider |
| Cost | per receipt, per provider, at the time of measurement |

Every metric is reported with its sample size. A rate computed over 12 receipts is
reported as "over 12 receipts" and not as a capability.

## 4. Policy-result correctness

Requires the authoritative policy document, which has not been supplied. When it
arrives:

1. A human writes the expected result for a labelled set of (claim, rule) pairs, citing
   the clause.
2. The engine is run on the same pairs.
3. Disagreements are classified as: engine wrong, human label wrong, or the clause is
   genuinely ambiguous. The third class is the interesting one - it means the policy
   needs clarification before it can be encoded, and it belongs in
   `docs/policy-assumptions.md`, not in a code comment.

Because the engine is deterministic, this is a conformance check rather than a
statistical one: a rule either returns the right tri-state for a given input or it has
a bug. Boundary cases (exactly at the limit, one unit below, one unit above) are part
of the labelled set.

`UNKNOWN` correctness is evaluated separately and deliberately: an engine that returns
`UNKNOWN` for everything scores perfectly on "never wrongly fails a claim" and is
worthless. So the report includes the `UNKNOWN` rate alongside correctness, and a rule
that returns `UNKNOWN` where the policy and evidence suffice is counted as an error.

## 5. Duplicate-detection metrics

- **Precision and recall** on labelled positive and negative pairs, with the sample size
  and the composition of the set stated.
- **Reported per signal** (exact hash, field match) so the contribution of each is
  visible rather than hidden in a blended score.
- **Explicitly not reported:** a calibrated probability. `ranking_score` is a queue
  ordering. Until a threshold is tuned against a representative labelled set, it must
  be described as a ranking signal.
- The perceptual-similarity signal is **not implemented** and therefore has no metric.
  Reporting one would require inventing it.

## 6. Human-effort metrics

The product's claim is that it reduces unnecessary manual work while surfacing genuine
exceptions. So the report must include:

- Percentage of claims requiring correction or human review.
- Time to resolve a representative exception, ideally against a human-only baseline if
  one is available.
- The false-positive rate of findings, because a system that flags everything is a
  system a reviewer learns to ignore.

## 7. Reporting rules

- Every number is accompanied by its denominator and the date it was measured.
- No number is reported before the harness has been run.
- Results that are worse than a baseline are reported, not omitted.
- "We did not measure this" is an acceptable and preferred entry. Ambiguity is not.
- The demo runbook's cached-extraction fallback is labelled as fallback in any report
  that uses it, and is never counted as live inference.

## 8. What exists today

| Piece | Status |
|---|---|
| `ExtractionEvaluation` data model | Not implemented |
| Labelled receipt set | Not supplied |
| Extraction harness (`scripts/evaluate_receipts.py`) | Not written |
| Provider adapter | Interface only; `UnavailableExtractor` returns no fields |
| Policy conformance set | Blocked on the policy document |
| Duplicate labelled pairs | Not supplied |
| Any measured metric | None |

The only honest statement today is: **extraction is not implemented, no policy is
loaded, and no metric has been measured.**
