"""Produce disposable upload examples without changing the supplied data."""
import csv
from pathlib import Path

root = Path(__file__).resolve().parents[1]
output = root / "artifacts"
output.mkdir(exist_ok=True)
with (root / "data" / "history_90_days.csv").open(encoding="utf-8-sig", newline="") as file:
    reader = csv.DictReader(file)
    fields = reader.fieldnames
    rows = [{**r, "record_id": "UPLOAD-" + r["record_id"]} for r in reader]
with (output / "valid_history_upload.csv").open("w", encoding="utf-8", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
invalid = [dict(rows[i]) for i in range(5)]
invalid[0]["prepared_kg"] = "-1"
invalid[1]["consumed_kg"] = "NaN"
invalid[2]["record_id"] = invalid[3]["record_id"]
invalid[3]["date"] = "2026-99-01"
invalid[4]["prepared_kg"] = "10000"
with (output / "invalid_history_upload.csv").open("w", encoding="utf-8", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=fields)
    writer.writeheader()
    writer.writerows(invalid)
print(f"Upload examples: {output}")
