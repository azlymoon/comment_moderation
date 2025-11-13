#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def parse_radon_cc(data: Dict[str, List[Dict[str, Any]]]) -> Tuple[List[Dict[str, Any]], float]:
    """Return list of all code blocks with complexity and the average CC."""
    blocks: List[Dict[str, Any]] = []
    total = 0.0
    count = 0
    if not data:
        return blocks, 0.0
    for filename, items in data.items():
        for it in items or []:
            it = dict(it)
            it["filename"] = filename
            blocks.append(it)
            total += float(it.get("complexity", 0.0))
            count += 1
    avg = total / count if count else 0.0
    blocks.sort(key=lambda x: float(x.get("complexity", 0.0)), reverse=True)
    return blocks, avg


def parse_radon_mi(data: Dict[str, Any]) -> List[Tuple[str, float, str]]:
    items: List[Tuple[str, float, str]] = []
    if not data:
        return items
    for filename, obj in data.items():
        mi = obj.get("mi") if isinstance(obj, dict) else None
        rank = obj.get("rank") if isinstance(obj, dict) else None
        if mi is not None:
            items.append((filename, float(mi), str(rank or "")))
    items.sort(key=lambda x: x[1])  # lowest first
    return items


def parse_pylint(data: Any) -> Tuple[Dict[str, int], List[Dict[str, Any]]]:
    counts: Dict[str, int] = {"error": 0, "warning": 0, "refactor": 0, "convention": 0, "fatal": 0, "info": 0}
    messages: List[Dict[str, Any]] = []
    if isinstance(data, list):
        for msg in data:
            mtype = msg.get("type", "info")
            counts[mtype] = counts.get(mtype, 0) + 1
            messages.append(msg)
    messages.sort(key=lambda m: (m.get("type", "z"), m.get("path", ""), m.get("line", 0)))
    return counts, messages


def parse_radon_hal(data: Any) -> Tuple[List[Dict[str, Any]], float]:
    """Parse radon hal JSON to list of function entries and average volume.

    Supports both dict {filename: {functions:[...]}} and list variants.
    """
    entries: List[Dict[str, Any]] = []
    volumes: List[float] = []
    if isinstance(data, dict):
        items = list(data.items())
    elif isinstance(data, list):
        items = []
        for item in data:
            if isinstance(item, dict):
                items.extend(item.items())
    else:
        items = []

    for filename, val in items:
        funcs = []
        if isinstance(val, dict):
            if isinstance(val.get("functions"), list):
                funcs = val["functions"]
            elif isinstance(val.get("all"), list):
                funcs = val["all"]
        elif isinstance(val, list):
            funcs = val
        for f in funcs:
            name = f.get("name") or f.get("fullname") or ""
            vol = f.get("volume") or f.get("vol") or 0.0
            diff = f.get("difficulty") or f.get("diff") or None
            effort = f.get("effort") or None
            try:
                v = float(vol)
            except Exception:
                v = 0.0
            d = None
            if diff is not None:
                try:
                    d = float(diff)
                except Exception:
                    d = None
            e = None
            if effort is not None:
                try:
                    e = float(effort)
                except Exception:
                    e = None
            entries.append({
                "filename": filename,
                "name": name,
                "volume": v,
                "difficulty": d,
                "effort": e,
            })
            volumes.append(v)
    avg_vol = sum(volumes) / len(volumes) if volumes else 0.0
    entries.sort(key=lambda x: x.get("volume", 0.0), reverse=True)
    return entries, avg_vol


def html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")
    )


def _cell(value: Any, tag: str = "td") -> str:
    """Render a table cell.

    Accepts:
    - plain string/number
    - tuple (text, tooltip)
    - dict {"text": str, "tip": str}
    """
    tip = None
    text = value
    if isinstance(value, tuple) and len(value) >= 2:
        text, tip = value[0], value[1]
    elif isinstance(value, dict):
        text = value.get("text", "")
        tip = value.get("tip")

    text_s = html_escape(str(text))
    if tip:
        tip_s = html_escape(str(tip))
        inner = f'<span class="tip" title="{tip_s}" data-tip="{tip_s}">{text_s}</span>'
    else:
        inner = text_s
    return f"<{tag}>{inner}</{tag}>"


def render_table(headers: List[Any], rows: List[List[Any]]) -> str:
    head = "".join(_cell(h, tag="th") for h in headers)
    body_rows = []
    for r in rows:
        cells = "".join(_cell(c) for c in r)
        body_rows.append(f"<tr>{cells}</tr>")
    body = "\n".join(body_rows)
    return f"<table>\n<thead><tr>{head}</tr></thead>\n<tbody>{body}</tbody>\n</table>"


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("reports")
    out_dir.mkdir(parents=True, exist_ok=True)

    cc_path = out_dir / "radon-cc.json"
    mi_path = out_dir / "radon-mi.json"
    hal_path = out_dir / "radon-hal.json"
    pylint_path = out_dir / "pylint.json"

    cc_data = load_json(cc_path) or {}
    mi_data = load_json(mi_path) or {}
    hal_data = load_json(hal_path) or {}
    pylint_data = load_json(pylint_path) or []

    blocks, cc_avg = parse_radon_cc(cc_data)
    mi_items = parse_radon_mi(mi_data)
    hal_entries, hal_avg_volume = parse_radon_hal(hal_data)
    pylint_counts, pylint_messages = parse_pylint(pylint_data)

    worst_blocks = blocks[:10]
    worst_mi = mi_items[:10]
    worst_hal = hal_entries[:10]
    top_messages = pylint_messages[:100]

    # Aggregates and extra metrics
    mi_values = [mi for _, mi, _ in mi_items]
    mi_avg = sum(mi_values) / len(mi_values) if mi_values else 0.0
    mi_min = min(mi_values) if mi_values else 0.0

    def count_symbol(sym: str) -> int:
        return sum(1 for m in pylint_messages if m.get("symbol") == sym)

    too_many_ancestors = count_symbol("too-many-ancestors")
    cyclic_import = count_symbol("cyclic-import")
    too_many_imports = count_symbol("too-many-imports")

    summary_rows = [
        [
            ("Средняя цикломатическая сложность (radon cc)",
             "Cyclomatic Complexity — число независимых путей в коде.\n"
             "Меньше — проще; рассчитывается radon по функциям/методам."),
            f"{cc_avg:.2f}",
        ],
        [
            ("Средний Maintainability Index (radon mi)",
             "Среднее по проекту значение MI. Больше — лучше."),
            f"{mi_avg:.2f}",
        ],
        [
            ("Минимальный MI (radon mi)",
             "Наихудшее значение MI — кандидаты на рефакторинг."),
            f"{mi_min:.2f}",
        ],
        [
            ("Средний Halstead Volume (radon hal)",
             "Среднее значение объёма Halstead. Характеризует информационный объём."),
            f"{hal_avg_volume:.2f}",
        ],
        [
            ("Количество проанализированных блоков",
             "Сколько функций/методов/классов radon рассмотрел при вычислении CC."),
            str(len(blocks)),
        ],
        [
            ("Файлов с MI (radon mi)",
             "MI — Maintainability Index. Чем больше, тем лучше сопровождаемость файла."),
            str(len(mi_items)),
        ],
        [
            ("Pylint: F/E/W/R/C (fatal,error,warning,refactor,convention)",
             "Сводка типов сообщений Pylint: F — критические, E — ошибки,\n"
             "W — предупреждения, R — рефакторинг, C — соглашения."),
            f"{pylint_counts.get('fatal',0)}/{pylint_counts.get('error',0)}/{pylint_counts.get('warning',0)}/"
            f"{pylint_counts.get('refactor',0)}/{pylint_counts.get('convention',0)}",
        ],
        [
            ("Pylint: too-many-ancestors", "Индикатор глубокой/сложной иерархии наследования."),
            str(too_many_ancestors),
        ],
        [
            ("Pylint: cyclic-import", "Циклические импорты — повышают сцепление модулей."),
            str(cyclic_import),
        ],
        [
            ("Pylint: too-many-imports", "Слишком много импортов на модуль — признак сцепления."),
            str(too_many_imports),
        ],
    ]

    cc_rows = [
        [
            b.get("filename", ""),
            (f"{b.get('name','')} ({b.get('type','')})", "Имя объекта и его тип (function, method, class)."),
            (str(b.get("lineno", "")), "Номер строки, с которой начинается объект."),
            (f"{float(b.get('complexity',0)):.2f}", "Cyclomatic Complexity — сложность управления потоком."),
            (str(b.get("rank", "")), "Ранг radon: A (лучше) … F (хуже)."),
        ]
        for b in worst_blocks
    ]

    mi_rows = [[f, (f"{mi:.2f}", "Maintainability Index — чем выше, тем лучше."), (r, "Ранг radon по MI.")]
               for (f, mi, r) in worst_mi]

    msg_rows = [
        [m.get("type", ""), m.get("message-id", ""), m.get("symbol", ""), m.get("path", ""), str(m.get("line", "")), m.get("message", "")]
        for m in top_messages
    ]

    css = """
    body { font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; padding: 24px; }
    h1, h2 { margin: 0.6em 0 0.3em; }
    table { border-collapse: collapse; width: 100%; margin: 12px 0 24px; }
    th, td { border: 1px solid #ddd; padding: 6px 8px; font-size: 14px; }
    th { background: #f3f3f3; text-align: left; }
    caption { text-align: left; font-weight: 600; margin: 8px 0; }
    .muted { color: #666; font-size: 12px; }
    .tip { border-bottom: 1px dotted #888; cursor: help; position: relative; }
    .tip::after {
        content: attr(data-tip);
        position: absolute;
        left: 0;
        bottom: 125%;
        background: rgba(0,0,0,0.85);
        color: #fff;
        padding: 6px 8px;
        border-radius: 4px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.25);
        white-space: pre-line;
        min-width: 160px;
        max-width: 520px;
        pointer-events: none;
        opacity: 0;
        transform: translateY(-4px);
        transition: opacity .15s ease, transform .15s ease;
        z-index: 9999;
    }
    .tip::before {
        content: '';
        position: absolute;
        left: 10px;
        bottom: 115%;
        border: 6px solid transparent;
        border-top-color: rgba(0,0,0,0.85);
        opacity: 0;
        transition: opacity .15s ease;
    }
    .tip:hover::after, .tip:focus::after { opacity: 1; transform: translateY(-6px); }
    .tip:hover::before, .tip:focus::before { opacity: 1; }
    """

    html = f"""
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <title>Отчёт по метрикам кода</title>
  <style>{css}</style>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta http-equiv="x-ua-compatible" content="ie=edge" />
  <meta name="generator" content="generate_metrics_html.py" />
  <meta name="generated" content="{datetime.utcnow().isoformat()}" />
  <meta name="description" content="Сводный отчёт radon/pylint" />
  <meta name="robots" content="noindex" />
  <meta name="color-scheme" content="light dark" />
</head>
<body>
  <h1>Сводный отчёт по метрикам</h1>
  <div class="muted">Сгенерировано: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div>
  {render_table([("Метрика", "Наведите, чтобы увидеть пояснение"), "Значение"], summary_rows)}

  <h2>Самые сложные фрагменты (Cyclomatic Complexity)</h2>
  {render_table([
      ("Файл", "Путь к файлу."),
      ("Объект", "Имя и тип анализируемого элемента."),
      ("Строка", "Первая строка объекта."),
      ("CC", "Cyclomatic Complexity — сложность кода."),
      ("Ранг", "Ранг radon A..F (A лучше).")
    ], cc_rows)}

  <h2>Файлы с наименьшей сопровождаемостью (Maintainability Index)</h2>
  {render_table([
      ("Файл", "Путь к файлу."),
      ("MI", "Maintainability Index — показатель сопровождаемости."),
      ("Ранг", "Ранг radon по MI.")
    ], mi_rows)}

  <h2>Halstead (наиболее объёмные функции)</h2>
  {render_table([
      ("Файл", "Путь к файлу."),
      ("Объект", "Имя функции/метода."),
      ("Volume", "Halstead Volume — информационный объём."),
      ("Difficulty", "Halstead Difficulty — оценка трудности."),
      ("Effort", "Halstead Effort — усилия.")
    ], [[h.get('filename',''), h.get('name',''), f"{h.get('volume',0):.2f}",
         ("" if h.get('difficulty') is None else f"{h.get('difficulty'):.2f}"),
         ("" if h.get('effort') is None else f"{h.get('effort'):.2f}")]
        for h in worst_hal])}

  <h2>Сообщения Pylint (первые 100)</h2>
  {render_table([
      ("Тип", "Тип сообщения Pylint (fatal/error/warning/refactor/convention)."),
      ("ID", "Идентификатор правила, например R0912."),
      ("Символ", "Короткое имя правила."),
      ("Файл", "Путь к файлу с проблемой."),
      ("Строка", "Номер строки."),
      ("Сообщение", "Текст замечания.")
    ], msg_rows)}
</body>
</html>
"""

    (out_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"Wrote {out_dir / 'index.html'}")


if __name__ == "__main__":
    main()
