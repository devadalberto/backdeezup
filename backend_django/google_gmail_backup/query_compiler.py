"""
Query compiler: translates RuleCondition rows into a Gmail q= search string.

Gmail search syntax reference:
  from:addr        to:addr         subject:word
  label:name       category:X      has:attachment
  older_than:Nd    newer_than:Nd
  "phrase"         -term (NOT)     (a OR b)

Design:
  - Conditions with the same logic operator are grouped together.
  - AND conditions are chained at the top level.
  - OR conditions within an AND group are wrapped in parentheses.

Example conditions:
  [sender contains linkedin.com,    AND]
  [subject contains job,            OR ]
  [subject contains recruiter,      OR ]
  [subject contains applied,        AND]
  [age older_than 30d,              AND]

Compiled:
  from:linkedin.com (subject:job OR subject:recruiter OR subject:applied) older_than:30d
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import RuleCondition


def _term(cond: "RuleCondition") -> str | None:
    """Convert a single condition to a Gmail query term. Returns None if not applicable."""
    f = cond.field
    op = cond.operator
    v = cond.value.strip()

    RC = cond.__class__

    # ── sender ────────────────────────────────────────────────────────────────
    if f == RC.FIELD_SENDER:
        if op == RC.OP_CONTAINS:     return f"from:{v}"
        if op == RC.OP_NOT_CONTAINS: return f"-from:{v}"
        if op == RC.OP_EQUALS:       return f"from:{v}"
        if op == RC.OP_NOT_EQUALS:   return f"-from:{v}"
        if op == RC.OP_STARTS_WITH:  return f"from:{v}"

    # ── recipient ─────────────────────────────────────────────────────────────
    elif f == RC.FIELD_TO:
        if op == RC.OP_CONTAINS:     return f"to:{v}"
        if op == RC.OP_NOT_CONTAINS: return f"-to:{v}"

    # ── subject ───────────────────────────────────────────────────────────────
    elif f == RC.FIELD_SUBJECT:
        quoted = f'"{v}"' if " " in v else v
        if op == RC.OP_CONTAINS:     return f"subject:{quoted}"
        if op == RC.OP_NOT_CONTAINS: return f"-subject:{quoted}"
        if op == RC.OP_EQUALS:       return f'subject:"{v}"'
        if op == RC.OP_STARTS_WITH:  return f"subject:{v}"

    # ── body ──────────────────────────────────────────────────────────────────
    elif f == RC.FIELD_BODY:
        quoted = f'"{v}"' if " " in v else v
        if op == RC.OP_CONTAINS:     return quoted
        if op == RC.OP_NOT_CONTAINS: return f"-{quoted}"

    # ── label ─────────────────────────────────────────────────────────────────
    elif f == RC.FIELD_LABEL:
        if op == RC.OP_EQUALS:       return f"label:{v}"
        if op == RC.OP_NOT_EQUALS:   return f"-label:{v}"
        if op == RC.OP_CONTAINS:     return f"label:{v}"
        if op == RC.OP_NOT_CONTAINS: return f"-label:{v}"

    # ── category ──────────────────────────────────────────────────────────────
    elif f == RC.FIELD_CATEGORY:
        cat = v.lower()
        if op == RC.OP_EQUALS:       return f"category:{cat}"
        if op == RC.OP_NOT_EQUALS:   return f"-category:{cat}"

    # ── has attachment ────────────────────────────────────────────────────────
    elif f == RC.FIELD_HAS_ATTACH:
        if op == RC.OP_IS_TRUE:      return "has:attachment"
        if op == RC.OP_NOT_EQUALS:   return "-has:attachment"

    # ── age ───────────────────────────────────────────────────────────────────
    elif f == RC.FIELD_AGE:
        try:
            days = int(v)
        except ValueError:
            return None
        if op == RC.OP_OLDER_THAN:   return f"older_than:{days}d"
        if op == RC.OP_NEWER_THAN:   return f"newer_than:{days}d"

    return None


def compile_conditions(conditions) -> str:
    """
    Takes a queryset/list of RuleCondition ordered by `order`.
    Returns a Gmail q= string.

    Algorithm:
    1. Walk conditions left to right.
    2. Collect consecutive OR conditions into a group.
    3. When we hit an AND (or end), emit the current OR-group (wrapped in parens if >1 term).
    4. Join top-level AND terms with spaces.
    """
    if not conditions:
        return ""

    and_parts: list[str] = []
    or_group: list[str] = []

    for cond in conditions:
        term = _term(cond)
        if not term:
            continue

        if cond.logic == "OR":
            or_group.append(term)
        else:
            # Flush current OR group first
            or_group.append(term)
            if len(or_group) == 1:
                and_parts.append(or_group[0])
            else:
                and_parts.append(f"({' OR '.join(or_group)})")
            or_group = []

    # Flush trailing OR group if last condition was OR
    if or_group:
        if len(or_group) == 1:
            and_parts.append(or_group[0])
        else:
            and_parts.append(f"({' OR '.join(or_group)})")

    return " ".join(and_parts)


def conditions_to_dict(conditions) -> list[dict]:
    """Serialize conditions for the frontend builder."""
    return [
        {
            "id": c.id if hasattr(c, "id") else None,
            "order": c.order,
            "field": c.field,
            "operator": c.operator,
            "value": c.value,
            "logic": c.logic,
        }
        for c in conditions
    ]


def preview_query(conditions_data: list[dict]) -> str:
    """
    Build a preview query from raw condition dicts (before saving).
    Used by the builder UI for real-time preview.
    """
    class FakeCond:
        pass

    from .models import RuleCondition

    fake = []
    for d in sorted(conditions_data, key=lambda x: x.get("order", 0)):
        c = FakeCond()
        c.__class__ = RuleCondition
        c.field    = d.get("field", "")
        c.operator = d.get("operator", "")
        c.value    = d.get("value", "")
        c.logic    = d.get("logic", "AND")
        fake.append(c)

    return compile_conditions(fake)
