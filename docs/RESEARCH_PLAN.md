# Research upgrade plan — 9 October 2026

Problem: the P0 served-food forecast and buffer let managers inspect trade-offs, but do not express asymmetric service costs; the sole baseline does not establish whether a more elaborate model adds value; portion advice lacks a repeatable measurement loop.

Before experiments, expected outcomes:

1. An empirical newsvendor decision should minimize historical average overage/underage loss, subject to an explicit kitchen capacity and maximum shortage frequency. Increasing shortage cost should never lower unconstrained preparation. It is a scenario based on observed served food, not a future service guarantee. Confirmed stockouts make latent demand unidentifiable: block automatic optimization until those observations are reviewed.
2. Compare the existing predictor with recent attendance-normalized mean, weekday seasonal naive, and a fixed regularized calendar model. Each fit must use strictly earlier dates and the same evaluation services. Hypothesis: simple attendance baselines may compete with extra complexity on 90 synthetic days. Keep the P0 default regardless of this exploratory comparison; promote a model only after a separate prospective evaluation with real data.
3. Smaller-first-serving advice should become an approved trial with optional seconds, explicit baseline/trial windows, source labels, evidence IDs, and attendance-weighted plate/served/consumed metrics. Five distinct services per phase is a demo minimum for showing a comparison, not a statistical power calculation. Empty, overlapping, or ambiguous duplicate services must not create a savings claim. No causal effect or nutrient adequacy is inferred.

Acceptance: mathematical optimizer oracle and monotonicity; capacity infeasibility; stockout guard; temporal leakage and metric recomputation; trial window/source/duplicate handling; persistence and reset; existing P0 scenarios; frontend type/build and browser workflow. Findings, exact references, and experiment results will be added to RESEARCH_REVIEW.md after implementation and checks.
