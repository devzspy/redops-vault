"""Output formatting shared by every command: a Rich table for list results,
a pretty-printed JSON blob for single-object results, or raw JSON for both
when --json is passed (for scripting/piping into jq).
"""

import json as _json

from rich.console import Console
from rich.table import Table

console = Console()


def _dig(row, dotted_key):
    value = row
    for part in dotted_key.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def _cell(row, key):
    value = key(row) if callable(key) else _dig(row, key)
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def emit(ctx, data, columns=None, list_key=None, empty_message="No results."):
    """Render `data`.

    columns: list of (header, key) pairs, where key is a dotted path
        ("client_name") or a callable(row) -> value, used to render `data`
        (or data[list_key]) as a table when it's a list of dicts.
    list_key: if `data` is a dict wrapping the list under this key (e.g.
        {"engagements": [...]}), unwrap it before applying `columns`.
    """
    if ctx.obj["json"]:
        console.print(_json.dumps(data, indent=2, default=str))
        return

    rows = data
    if list_key is not None and isinstance(data, dict):
        rows = data.get(list_key, [])

    if columns is not None and isinstance(rows, list):
        if not rows:
            console.print(empty_message)
            return
        table = Table(show_lines=False)
        for header, _ in columns:
            table.add_column(header)
        for row in rows:
            table.add_row(*[_cell(row, key) for _, key in columns])
        console.print(table)
        return

    if data is None:
        console.print(empty_message)
        return

    console.print_json(_json.dumps(data, default=str))


def success(message):
    console.print(f"[green]{message}[/green]")
