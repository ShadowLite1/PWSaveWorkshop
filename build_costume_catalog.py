"""Gather costume names without treating text IDs as save-field IDs."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent
rows = json.loads((root / "loadout_catalogs/items.json").read_text(encoding="utf-8"))
excluded = {"WALKMAN", "LETTER", "ID CARD(P)", "ID CARD(H)", "CAMERA"}
entries = {}
for row in rows:
    if not 373 <= row["quote_id"] <= 480:
        continue
    name = row["text"].strip()
    if not name or name in excluded:
        continue
    entry = entries.setdefault(name, {"name": name, "text_references": [], "save_id": None, "status": "name-only"})
    entry["text_references"].append({"quote_id": row["quote_id"], "key_hash": row["key_hash"]})
    if name == "ESCORT":
        entry.update(save_id="55", save_offset="B5E8", mode="MSF Soldier - Versus Ops", status="save-confirmed")
catalog = {
    "source": "loadout_catalogs/items.json (extracted game OLANG)",
    "notes": [
        "Text references are NOT costume save IDs.",
        "Regional, dummy and cut-content names do not establish usable PC models.",
        "Only Escort is independently confirmed here against the supplied Versus save.",
        "Existing ESW uniform mappings require individual verification; do not infer IDs from list order.",
    ],
    "costumes": list(entries.values()),
}
output = root / "loadout_catalogs/costumes.json"
output.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"Collected {len(entries)} unique names in {output}")
