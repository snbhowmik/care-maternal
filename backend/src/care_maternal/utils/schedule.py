"""Pure schedule engine: LMP -> gestational age -> due windows from the clinician spec.

No Django imports, so it can be tested without a database.
"""

import re
from datetime import date, timedelta
from pathlib import Path

import yaml

SPEC_PATH = Path(__file__).resolve().parent.parent / "spec" / "maternal_pathway.yaml"
EDD_DAYS = 280  # Naegele's rule: LMP + 280 days
_GA = re.compile(r"^(\d+)(?:\+([0-6]))?$")


def parse_ga(text) -> int:
    """'13+6' -> 97 days, '36' -> 252 days."""
    m = _GA.match(str(text).strip())
    if not m:
        raise ValueError(f"Invalid gestational age: {text!r}")
    return int(m.group(1)) * 7 + int(m.group(2) or 0)


def ga_date(lmp: date, text) -> date:
    return lmp + timedelta(days=parse_ga(text))


def edd(lmp: date) -> date:
    return lmp + timedelta(days=EDD_DAYS)


def gestational_age(lmp: date, on: date) -> tuple[int, int]:
    """(completed weeks, extra days) on a given date."""
    weeks, days = divmod((on - lmp).days, 7)
    return weeks, days


def load_spec(path: Path = SPEC_PATH) -> dict:
    return yaml.safe_load(path.read_text())


# Items whose due date depends on another event or a clinician decision.
# They are created without dates; the service fills them in later.
RELATIVE_ITEMS = {
    "V-TD2": "four weeks after Td-1 is recorded",
    "V-TDBOOST": "clinician decision (depends on previous pregnancy history)",
}


def build_items(lmp: date, spec: dict | None = None) -> list[dict]:
    """One dict per spec item, with its due window computed from the LMP."""
    spec = spec or load_spec()
    items = []
    for block in spec["schedule"]:
        window = block["window"]
        start = ga_date(lmp, window["from_weeks"])
        end = ga_date(lmp, window["to_weeks"])
        for item in block["items"]:
            relative = item["id"] in RELATIVE_ITEMS
            items.append(
                {
                    "spec_id": item["id"],
                    "kind": item["type"],
                    "label": item["text"],
                    "due_from": None if relative else start,
                    "due_to": None if relative else end,
                    "waiting_on": RELATIVE_ITEMS.get(item["id"], ""),
                }
            )
    return items


def items_from_templates(lmp: date, templates: list[dict]) -> list[dict]:
    """One dict per check template, with its due window computed from the LMP.

    A template with relative_to has no dates yet: it becomes due after another check is recorded.
    """
    items = []
    for t in templates:
        relative = bool(t.get("relative_to")) or not t.get("from_weeks")
        items.append(
            {
                "spec_id": t["spec_id"],
                "kind": t["kind"],
                "label": t["label"],
                "due_from": None if relative else ga_date(lmp, t["from_weeks"]),
                "due_to": None if relative else ga_date(lmp, t["to_weeks"]),
                "waiting_on": (t.get("waiting_note") or f"after {t['relative_to']} is recorded")
                if t.get("relative_to") else (t.get("waiting_note") or ("clinician sets the date" if relative else "")),
            }
        )
    return items


def templates_from_spec(spec: dict | None = None) -> list[dict]:
    """The clinician spec as check templates. Used once, to seed a hospital's check list."""
    spec = spec or load_spec()
    rows = []
    for block in spec["schedule"]:
        window = block["window"]
        for item in block["items"]:
            row = {
                "spec_id": item["id"],
                "label": item["text"],
                "kind": item["type"],
                "from_weeks": str(window["from_weeks"]),
                "to_weeks": str(window["to_weeks"]),
                "relative_to": "",
                "after_days": None,
                "waiting_note": "",
            }
            if item["id"] == "V-TD2":
                row.update(relative_to="V-TD1", after_days=28, waiting_note=RELATIVE_ITEMS["V-TD2"])
            elif item["id"] == "V-TDBOOST":
                row.update(from_weeks="", to_weeks="", waiting_note=RELATIVE_ITEMS["V-TDBOOST"])
            rows.append(row)
    return rows


def item_state(due_from: date | None, due_to: date | None, done_on, today: date, resolution: str = "") -> str:
    if done_on:
        return "done"
    if resolution == "elsewhere":
        return "elsewhere"
    if resolution == "not_needed":
        return "waived"
    if due_from is None:
        return "waiting"
    if today < due_from:
        return "upcoming"
    if due_to and today > due_to:
        return "overdue"
    return "due"
