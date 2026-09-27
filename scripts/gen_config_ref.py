#!/usr/bin/env python3
"""Regenerate the generated config reference in docs/configuration.md.

Reads every ``config(...)`` call (python-decouple) in backend_django/ and
every ``${VAR}`` / ``${VAR:-default}`` interpolation in docker-compose.yml,
and writes two markdown tables between the
``<!-- BEGIN GENERATED CONFIG REFERENCE -->`` / ``END`` markers in
docs/configuration.md. Nothing else in that file is touched.

This is the only place these variables should be listed by hand-maintained
text -- if a phase adds a new ``config(...)`` call or compose var, rerun this
script instead of editing the table. Deterministic output (sorted, no
timestamps) so a second run with no code changes produces an empty diff.

Usage: python3 scripts/gen_config_ref.py [--check]
  --check   exit 1 if regenerating would change the file (for CI), without writing.
"""
import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend_django"
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
CONFIG_DOC = REPO_ROOT / "docs" / "configuration.md"

BEGIN_MARKER = "<!-- BEGIN GENERATED CONFIG REFERENCE (scripts/gen_config_ref.py) -->"
END_MARKER = "<!-- END GENERATED CONFIG REFERENCE -->"

SKIP_DIR_NAMES = {"migrations", "tests", "__pycache__"}


def _iter_python_files():
    for path in sorted(BACKEND_DIR.rglob("*.py")):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.name.startswith("test_") or path.name == "tests.py":
            continue
        yield path


def _unparse(node):
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return "?"


def _find_config_calls(path):
    """Yields (var_name, cast_str_or_None, default_str_or_None, has_default, lineno)."""
    try:
        tree = ast.parse(path.read_text(), filename=str(path))
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Name) and func.id == "config"):
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
            continue
        var_name = node.args[0].value
        cast_node = None
        default_node = None
        has_default = False
        for kw in node.keywords:
            if kw.arg == "cast":
                cast_node = kw.value
            elif kw.arg == "default":
                default_node = kw.value
                has_default = True
        yield var_name, _unparse(cast_node), _unparse(default_node), has_default, node.lineno


def collect_django_vars():
    by_name = {}
    for path in _iter_python_files():
        rel = path.relative_to(REPO_ROOT)
        for var_name, cast_str, default_str, has_default, lineno in _find_config_calls(path):
            entry = by_name.setdefault(var_name, {"casts": set(), "defaults": set(), "required": False, "locations": []})
            entry["casts"].add(cast_str or "str")
            if has_default:
                entry["defaults"].add(default_str)
            else:
                entry["required"] = True
            entry["locations"].append(f"{rel}:{lineno}")
    return by_name


COMPOSE_VAR_RE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)(:-([^}]*))?\}")


def collect_compose_vars():
    by_name = {}
    text = COMPOSE_FILE.read_text()
    for match in COMPOSE_VAR_RE.finditer(text):
        name, _, default = match.groups()
        entry = by_name.setdefault(name, {"defaults": set(), "required": False})
        if default is None:
            entry["required"] = True
        else:
            entry["defaults"].add(default)
    return by_name


def render_django_table(by_name):
    lines = [
        "### Application (`backend_django/`, read via python-decouple)",
        "",
        "| Variable | Cast | Default | Required | Read in |",
        "|---|---|---|---|---|",
    ]
    for name in sorted(by_name):
        entry = by_name[name]
        cast = ", ".join(sorted(entry["casts"]))
        if entry["required"]:
            default = "*(none)*"
            required = "**yes**"
        else:
            defaults = sorted(d if d is not None else "*(none)*" for d in entry["defaults"])
            default = "; ".join(f"`{d}`" for d in defaults)
            required = "no"
        locations = ", ".join(f"`{loc}`" for loc in sorted(set(entry["locations"])))
        lines.append(f"| `{name}` | `{cast}` | {default} | {required} | {locations} |")
    return lines


def render_compose_table(by_name):
    lines = [
        "",
        "### Docker Compose (`docker-compose.yml` — read by containers directly, not Django)",
        "",
        "| Variable | Default | Required |",
        "|---|---|---|",
    ]
    for name in sorted(by_name):
        entry = by_name[name]
        if entry["required"]:
            default = "*(none)*"
            required = "**yes**"
        else:
            defaults = sorted(entry["defaults"])
            default = "; ".join(f"`{d}`" for d in defaults)
            required = "no"
        lines.append(f"| `{name}` | {default} | {required} |")
    return lines


def build_block():
    django_vars = collect_django_vars()
    compose_vars = collect_compose_vars()
    body = [
        BEGIN_MARKER,
        "",
        "Generated by `python3 scripts/gen_config_ref.py` — every `config(...)` call",
        "in `backend_django/` plus every `${VAR}` interpolation in `docker-compose.yml`.",
        "Do not hand-edit between these markers; rerun the script instead.",
        "",
        *render_django_table(django_vars),
        *render_compose_table(compose_vars),
        "",
        END_MARKER,
    ]
    return "\n".join(body)


def main():
    check_only = "--check" in sys.argv
    original = CONFIG_DOC.read_text()
    if BEGIN_MARKER not in original or END_MARKER not in original:
        print(f"ERROR: {CONFIG_DOC} is missing the generated-block markers.", file=sys.stderr)
        return 1
    before, rest = original.split(BEGIN_MARKER, 1)
    _, after = rest.split(END_MARKER, 1)
    updated = before + build_block() + after

    if check_only:
        if updated != original:
            print("Config reference is stale — run: python3 scripts/gen_config_ref.py")
            return 1
        print("Config reference is up to date.")
        return 0

    CONFIG_DOC.write_text(updated)
    print(f"Wrote {CONFIG_DOC}" if updated != original else f"{CONFIG_DOC} unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
