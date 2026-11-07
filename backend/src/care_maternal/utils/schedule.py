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


def item_state(due_from: date | None, due_to: date | None, done_on, today: date) -> str:
    if done_on:
        return "done"
    if due_from is None:
        return "waiting"
    if today < due_from:
        return "upcoming"
    if due_to and today > due_to:
        return "overdue"
    return "due"
