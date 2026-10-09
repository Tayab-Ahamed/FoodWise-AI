# Executed research-upgrade verification — 9 October 2026

These are checks actually run in the selected Windows workspace. Earlier P0 verification remains in the root VALIDATION.md.

| Check | Result |
|---|---|
| Domain tests and supplied P0 acceptance scenarios | `python -m pytest backend/tests -q`: **45 passed**, final run **5.62 seconds**. Original 30 cases plus 15 new collected cases. |
| Frontend type checking | `npm.cmd run typecheck`: **passed**, exit 0. |
| Production build | `npm.cmd run build`: **passed**; Vite 6.4.4, **2,175 modules**, **6.02 seconds**. Main JS 286.44 kB, chart JS 431.63 kB; gzip 86.07 / 124.05 kB. |
| Dependency audit | `npm.cmd audit`: **0 vulnerabilities**. No new runtime packages were installed. |
| Synthetic experiment | `python -m scripts.research_experiment`: **completed**, wrote docs/research_results.json from original history with the accounting fixture excluded. |
| Local services | Backend restarted with the upgrades at **127.0.0.1:8000**; existing Vite frontend running at **127.0.0.1:5173**. |
| Browser | Tested in the Codex in-app browser. Final browser error-log query returned **[]**. Expected domain rejections displayed in the application alert. |
| Responsive planning | Widths **320, 390, 768, 1024, 1440 px**; document client width equaled scroll width, including cost planner and benchmark table. Inner tables scroll within their containers. |
| Persistence | Approved plans and two measurement protocols remained accessible after backend restart. Existing P0 prototype state was retained by the additive SQLite migration. |

The non-failing Starlette TestClient `httpx` deprecation warning remains (one warning). It does not indicate a failed domain assertion. Initial failures were fixed: new optional CSV column was inadvertently required; a test package import was corrected; the shortage test was changed to the actual matching weekday; one missing frontend prop and a JSX typo were corrected. The final suite/type/build have no unresolved failures. Browser verification caught an error-detail shape mismatch (`undefined` text); backend details were corrected and the final displayed rejection identified the shortage record correctly.

## Meaningful new domain checks

- Empirical loss compared with an independent dense continuous quantity grid; underage-cost monotonicity; duplicate demand values and flat minima; zero-demand samples.
- Capacity between demand knots, infeasible service frequency, valid feasible boundary, invalid/nonfinite input rejection.
- Optimization decision persistence, exact plan/forecast/item/quantity provenance, offline report assumptions and stale-version rejection.
- Confirmed shortages block automatic optimization; absent shortage flag remains unknown; insufficient history cannot produce a policy; legacy and blank optional CSV columns remain valid.
- All five model metrics independently recomputed; every training date strictly precedes the evaluation date; adding a future actual cannot alter a past benchmark; sparse history yields null metrics.
- Descriptive interval rolling coverage recomputed, without claiming calibration.
- Portion phases use sums per total diners (not unweighted averaging); ordered nonoverlapping windows; source filtering; empty scopes; duplicate service exclusion; no difference before five services; prospective trials use actual logs; historical windows require retrospective labeling; SQLite persistence/reset.
- The original mass accounting, temporal forecasting, atomic import, manager approval, safety review, permanent plate-waste block, allocation, idempotency, expiry and offline-report acceptance cases also pass.

## Browser actions verified

1. Calculated the original lunch forecast; five model rows and empirical range coverage appeared.
2. Optimized Dal with surplus penalty 70, shortage penalty 180, maximum historical shortage frequency 20%, capacity 38.52. Proposed **20.3726 kg**, displayed 20.4 kg; adopted it and approved the plan. The offline explanation retained exact decision assumptions and projected scenario loss.
3. Set capacity to 0. The UI explicitly reported infeasibility and offered no quantity to adopt.
4. Registered a prospective actual-log trial. No phase difference appeared because insufficient services were recorded.
5. Loaded the synthetic historical comparison and saved it. Baseline **41 services / 7,893 diners**, comparison **49 / 9,069**; Rice plate waste **23.80 / 24.62 g per diner**. No intervention or causal saving was claimed. Historical evidence opened and the dialog closed using Escape.
6. Logged a separate balanced **synthetic Rice** actual: **40 prepared / 38 consumed / 0 untouched / 2 plate**, 160 diners, confirmed shortage. The 16 October matching-Friday forecast included its record **ACT-b3563b13**. Clicking optimization produced the backend censoring rejection, with the correct field/record detail after repair. No lost-demand number was invented.
7. Tested responsive planning at five widths. Revisited Impact after backend restart and verified saved protocols and source-labeled results remained available.

Screenshot: [verified retrospective measurement result](../artifacts/research-trial-desktop.jpg). Browser test state was retained: approved demo plans, a prospective protocol, a retrospective synthetic protocol and one synthetic Rice actual. Reset remains available through the existing explicit demo reset flow; unrelated source files and original datasets were preserved.

## Practical limits

Research review is targeted, with abstract-only/access-limited sources identified in RESEARCH_REVIEW.md. Source code was inspected at pinned commits, not every file of every repository. The new calendar model is an exploratory fixed ridge challenger, not a reproduced Bayesian GAM or automatic production model switch. Range diagnostics do not provide calibrated coverage. Manager cost penalties and quantity outcomes are scenarios based on observed served food; missing shortage data can hide demand. Portion comparisons are observational and have no causal, statistical significance or nutrition adequacy claim. Recipe/ingredient yield planning and provider integration remain deferred. The complete runtime workflow stays offline and food recovery stays simulated.
