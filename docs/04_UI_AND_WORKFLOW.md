# Interface and corrected workflow
Premium light interface inspired by the user's image: warm white background, navy text, emerald actions, pale blue/lilac/green sections, amber review states. Use a restrained dark sidebar if helpful. No chatbot-first screen. All kg, units, dates and simulation labels readable from a judging table.
Navigation: Overview / Plan Next Meal / Record Meal / Recovery / Impact. Investigation is a panel within Overview and Plan, not an extra mandatory screen.
Persistent banner: “Synthetic demo data • Simulated recovery”. Dataset source and API/offline status visible.
1 Input: actual history CSV, expected attendance, selected date/meal/event, current raw stock and label expiry dates, separately measured untouched/plate quantities. Unknown values remain unknown.
2 Analyze: forecast served demand by item, show evidence references and historical range, identify repeated overproduction and plate-waste rates. Attendance drop ≠ causal proof.
3 Action: preparation sheet with cooked quantities, editable buffer, optional ingredient requirements with explicit yield conversions, near-expiry warnings. Manager approval saves the exact quantities.
4 Service: entry form prepared, consumed, untouched surplus, plate waste and actual attendance. Show served mass and live mass-balance check. Block inconsistent save.
5 Recovery and impact: two independent category cards. Plate waste has permanent “No human redistribution” badge. Untouched has “Review required” until reviewed/approved. Demo processors clearly named simulated. Display activity log.
6 Feedback: saved actuals update next forecast and error summary; show old versus new forecast with dataset version. No fictional self-training animation.
## Key simulator panel
Slider/input Q with baseline reference, demand line/range, predicted untouched surplus, shortage kg, empirical shortage frequency, potential production cost difference. Under it show assumptions and historical sample count. Use amber shortage warning instead of making minimum quantity look optimal.
## States
Empty dataset, insufficient history, invalid CSV, loading, offline/provider unavailable, zero waste, no eligible recovery, approval invalidated, duplicate handoff and unsaved edits all receive readable feedback. Disable submit while pending; show error details without wiping forms.
## Added differentiators
Evidence drawer links findings to table rows. Approval and audit trail connect a recommendation to actual action. Simulator protects service levels. Feedback updates future planning. Inventory warnings prevent ingredient waste without asserting food safety.
