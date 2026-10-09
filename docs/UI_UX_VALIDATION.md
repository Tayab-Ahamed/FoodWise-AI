# FoodWise AI — Kitchen Fieldbook redesign

Implemented and verified on Windows on 2026-10-09.

## Experience

- A bright paper palette with citrus, forest and tomato accents, editorial serif headings and clear operational controls.
- Horizontal Observe / Prepare / Account / Review / Learn navigation, with URL fragments, browser back/forward, page titles and keyboard focus management.
- An interactive accounting plate: consumed, untouched and plate waste masses come directly from backend totals. Selecting a segment explains its meaning and recovery restriction.
- A three-stage preparation flow: set attendance and menu, simulate surplus and shortage, then approve the preparation sheet. Cost optimization and model research expand on demand.
- Approved plan IDs carry into actual meal logging. Saved record IDs carry into recovery allocation. No safety transition or calculation moved to the frontend.
- Distinct meal-accounting, recovery-review and impact screens; a visible recovery procedure; concise evidence observations; measurement setup inside an optional disclosure.
- Named native dialogs, Escape dismissal, explicit focus restoration, inline import errors, accurate evidence loading states, visible focus styles, reduced-motion support and narrow-screen reflow.
- A built-in three-minute guide in the header. All fonts and assets work locally; no additional dependency or external service was added.

## Checks actually run

| Check | Result |
|---|---|
| `python -m pytest backend/tests -q --tb=short` through the workspace venv | **45 passed**, 6.31 seconds |
| `npm.cmd run typecheck` | Passed |
| Final `npm.cmd run build` (also runs `tsc --noEmit`) | Passed, 2,176 modules; Vite build 5.75 seconds |
| Backend and frontend | Running at `127.0.0.1:8000` and `127.0.0.1:5173`; browser connected to the live backend |
| Browser console | No warnings or errors during the checked optimizer/model flow |
| Responsive layout | Desktop 1440 × 1000; mobile 390 × 844; overview reflow at 320 × 800 with document scroll width equal to client width |

Initial sandbox-only invocations failed because Windows temporary database access and Vite `realpath` were blocked. The checks above were rerun successfully with normal Windows execution permissions. There is one existing non-blocking Starlette/httpx test-client deprecation warning.

## Browser rehearsal

1. Selected the accounting plate's untouched segment and verified the mass and review requirement.
2. Calculated the default lunch forecast. Reduced Dal preparation to 15 kg and observed 4.5 kg expected shortage and 100% historical shortage frequency. Increased preparation to 21 kg, approved a plan, and generated its offline explanation.
3. Opened the actual log from that approved plan and verified automatic linking. Entered a deliberately unbalanced meal: saving stayed disabled and the backend reported a 1 kg mass-balance discrepancy. Corrected it to 21 prepared / 18 consumed / 2 untouched / 1 plate, labeled it synthetic, and saved it.
4. Opened recovery from that saved meal and verified its record selection. Premature approval was rejected. Saved the five demo review attestations, obtained manager approval, and recorded a 2 kg simulated handoff.
5. Allocated 1 kg plate waste from the same synthetic meal. Attempted human redistribution and verified the backend rejection.
6. Inspected actual food, projected prevention, the approved-versus-actual comparison, and simulated recovery in the impact screen.
7. Tested invalid CSV row errors and valid preview confirmation on mobile. The confirm button remained disabled until the replacement checkbox was selected. Closed the dialog without committing a replacement.
8. Verified a 90-record evidence table with no premature missing-record warning; expanded cost optimization and model comparison; inspected a saved portion comparison and its optional registration form.
9. Tested the guide, Escape dismissal and focus restoration; skip navigation stayed on the current page; browser back/forward returned to the correct screens. Cancelled reset without clearing existing work.

The mutable demo includes the synthetic walkthrough plan, actual and simulated recovery records. Earlier prototype data was retained. The toolbar reset remains available when a clean rehearsal is wanted.

## Preview artifacts

- [Desktop overview](../artifacts/ui-overview-desktop.jpg)
- [Mobile overview](../artifacts/ui-overview-mobile.jpg)
- [Preparation simulator](../artifacts/ui-preparation-desktop.jpg)

## Scope and remaining limits

Manual browser and keyboard checks were completed in the in-app browser. A formal assistive-technology audit and real-user usability testing have not been performed. Unsaved form drafts are local component state and reset when leaving their page; saved decisions and records persist in SQLite. Research results and walkthrough data remain synthetic; projected prevention and simulated handoffs retain their explicit labels.
