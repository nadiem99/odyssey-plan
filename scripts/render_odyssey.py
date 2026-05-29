#!/usr/bin/env python3
"""Render an Odyssey Planning JSON file into portable JSON and HTML artifacts."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
from pathlib import Path
from typing import Any


EXPECTED_PROMPTS = {
    "life-1": "expected_path",
    "life-2": "alternative_path",
    "life-3": "wildcard",
}
REQUIRED_YEARS = set(range(6))
GAUGE_KEYS = ("resources", "likeIt", "confidence", "coherence")


class OdysseyValidationError(ValueError):
    """Raised when Odyssey JSON cannot be rendered safely."""


def _path_label(parts: list[str]) -> str:
    return ".".join(parts)


def _require_dict(value: Any, path: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OdysseyValidationError(f"{_path_label(path)} must be an object")
    return value


def _require_non_empty_string(value: Any, path: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OdysseyValidationError(f"{_path_label(path)} must be a non-empty string")
    return value.strip()


def _string_list(value: Any, path: list[str]) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    if not isinstance(value, list):
        raise OdysseyValidationError(f"{_path_label(path)} must be a list of strings")
    output: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise OdysseyValidationError(f"{_path_label(path + [str(index)])} must be a string")
        if item.strip():
            output.append(item.strip())
    return output


def _gauge_value(value: Any, path: list[str]) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OdysseyValidationError(f"{_path_label(path)} must be a number from 0 to 100")
    if value < 0 or value > 100:
        raise OdysseyValidationError(f"{_path_label(path)} must be between 0 and 100")
    return int(round(value))


def _normalize_timeline(value: Any, path: list[str]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise OdysseyValidationError(f"{_path_label(path)} must be a list of year/milestone objects")
    entries: list[dict[str, Any]] = []
    seen: set[int] = set()
    for index, item in enumerate(value):
        item_path = path + [str(index)]
        row = _require_dict(item, item_path)
        year = row.get("year")
        if isinstance(year, bool) or not isinstance(year, int):
            raise OdysseyValidationError(f"{_path_label(item_path + ['year'])} must be an integer year")
        if year not in REQUIRED_YEARS:
            raise OdysseyValidationError(f"{_path_label(item_path + ['year'])} must be one of 0, 1, 2, 3, 4, 5")
        if year in seen:
            raise OdysseyValidationError(f"{_path_label(path)} contains duplicate year {year}")
        seen.add(year)
        entries.append(
            {
                "year": year,
                "milestone": _require_non_empty_string(row.get("milestone"), item_path + ["milestone"]),
            }
        )
    if seen != REQUIRED_YEARS:
        missing = ", ".join(str(year) for year in sorted(REQUIRED_YEARS - seen))
        raise OdysseyValidationError(f"{_path_label(path)} is missing year(s): {missing}")
    return sorted(entries, key=lambda row: row["year"])


def _normalize_prototype_steps(value: Any, path: list[str]) -> dict[str, list[str]]:
    steps = _require_dict(value or {}, path)
    return {
        "people": _string_list(steps.get("people"), path + ["people"]),
        "experiments": _string_list(steps.get("experiments"), path + ["experiments"]),
        "reflections": _string_list(steps.get("reflections"), path + ["reflections"]),
    }


def normalize_odyssey(raw: dict[str, Any]) -> dict[str, Any]:
    data = _require_dict(raw, ["root"])
    exercise = data.get("exercise", "odyssey-planning")
    if exercise != "odyssey-planning":
        raise OdysseyValidationError("exercise must be odyssey-planning")

    participant_raw = data.get("participant") or {}
    if isinstance(participant_raw, str):
        participant = {"name": participant_raw.strip()}
    else:
        participant = _require_dict(participant_raw, ["participant"])
    participant = {
        "name": str(participant.get("name", "")).strip(),
        "context": str(participant.get("context", "")).strip(),
    }

    plans_raw = data.get("plans")
    if not isinstance(plans_raw, list):
        raise OdysseyValidationError("plans must be a list")
    if len(plans_raw) != 3:
        raise OdysseyValidationError("plans must contain exactly three plans")

    normalized_plans: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, plan_raw in enumerate(plans_raw):
        path = ["plans", str(index)]
        plan = _require_dict(plan_raw, path)
        plan_id = _require_non_empty_string(plan.get("id"), path + ["id"])
        if plan_id not in EXPECTED_PROMPTS:
            raise OdysseyValidationError(f"{_path_label(path + ['id'])} must be life-1, life-2, or life-3")
        if plan_id in seen_ids:
            raise OdysseyValidationError(f"plans contains duplicate id {plan_id}")
        seen_ids.add(plan_id)

        prompt_type = _require_non_empty_string(plan.get("promptType"), path + ["promptType"])
        if prompt_type != EXPECTED_PROMPTS[plan_id]:
            raise OdysseyValidationError(f"{_path_label(path + ['promptType'])} must be {EXPECTED_PROMPTS[plan_id]}")

        gauges = _require_dict(plan.get("gauges"), path + ["gauges"])
        normalized_plans.append(
            {
                "id": plan_id,
                "promptType": prompt_type,
                "titleSixWords": _require_non_empty_string(plan.get("titleSixWords"), path + ["titleSixWords"]),
                "summary": str(plan.get("summary", "")).strip(),
                "timeline": _normalize_timeline(plan.get("timeline"), path + ["timeline"]),
                "gauges": {key: _gauge_value(gauges.get(key), path + ["gauges", key]) for key in GAUGE_KEYS},
                "questionsRaised": _string_list(plan.get("questionsRaised"), path + ["questionsRaised"]),
                "prototypeSteps": _normalize_prototype_steps(plan.get("prototypeSteps"), path + ["prototypeSteps"]),
            }
        )

    expected_ids = set(EXPECTED_PROMPTS)
    if seen_ids != expected_ids:
        missing = ", ".join(sorted(expected_ids - seen_ids))
        raise OdysseyValidationError(f"plans is missing required plan id(s): {missing}")

    synthesis_raw = data.get("synthesis") or {}
    synthesis = _require_dict(synthesis_raw, ["synthesis"])
    return {
        "schemaVersion": str(data.get("schemaVersion", "1.0")),
        "exercise": "odyssey-planning",
        "createdAt": str(data.get("createdAt") or dt.datetime.now(dt.UTC).isoformat()),
        "participant": participant,
        "plans": sorted(normalized_plans, key=lambda plan: plan["id"]),
        "synthesis": {
            "commonThreads": _string_list(synthesis.get("commonThreads"), ["synthesis", "commonThreads"]),
            "tensions": _string_list(synthesis.get("tensions"), ["synthesis", "tensions"]),
            "nextExperiments": _string_list(synthesis.get("nextExperiments"), ["synthesis", "nextExperiments"]),
            "reflectionPrompts": _string_list(synthesis.get("reflectionPrompts"), ["synthesis", "reflectionPrompts"]),
        },
    }


def _json_for_script(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2).replace("<", "\\u003c")


def _render_html(data: dict[str, Any]) -> str:
    title = "Odyssey Plan"
    participant = data["participant"].get("name")
    if participant:
        title = f"{participant}'s Odyssey Plan"
    safe_title = html.escape(title)
    embedded_json = _json_for_script(data)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  <link rel="icon" href="data:,">
  <style>
    :root {{
      color-scheme: light;
      --ink: #16202a;
      --muted: #65717f;
      --paper: #f7f4ee;
      --surface: #fffdf8;
      --line: #d9d1c4;
      --teal: #1d9a93;
      --coral: #e35d4f;
      --gold: #d99b2b;
      --blue: #3467a8;
      --shadow: 0 18px 50px rgba(22, 32, 42, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: var(--paper);
      color: var(--ink);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }}
    button, input, textarea {{ font: inherit; }}
    button {{
      border: 1px solid var(--ink);
      background: var(--ink);
      color: #fffdf8;
      border-radius: 7px;
      padding: 0.68rem 0.9rem;
      cursor: pointer;
      min-height: 42px;
    }}
    button.secondary {{
      background: transparent;
      color: var(--ink);
    }}
    button:hover {{ transform: translateY(-1px); }}
    textarea, input[type="text"] {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--surface);
      color: var(--ink);
      padding: 0.72rem 0.78rem;
      resize: vertical;
      min-height: 42px;
    }}
    textarea:focus, input:focus {{
      outline: 2px solid rgba(29, 154, 147, 0.24);
      border-color: var(--teal);
    }}
    .shell {{ max-width: 1180px; margin: 0 auto; padding: 32px 18px 56px; }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 24px;
      align-items: end;
      padding: 26px 0 28px;
      border-bottom: 2px solid var(--ink);
    }}
    .eyebrow {{
      font-size: 0.75rem;
      font-weight: 800;
      text-transform: uppercase;
      color: var(--teal);
      letter-spacing: 0.08em;
      margin-bottom: 8px;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(2.1rem, 5vw, 4.8rem);
      line-height: 0.96;
      letter-spacing: 0;
      max-width: 780px;
    }}
    .context {{
      margin-top: 16px;
      color: var(--muted);
      max-width: 720px;
      line-height: 1.55;
    }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 10px;
      max-width: 420px;
    }}
    .status {{ min-height: 22px; color: var(--teal); font-size: 0.92rem; margin-top: 10px; text-align: right; }}
    .meta-grid {{
      display: grid;
      grid-template-columns: minmax(0, 280px) minmax(0, 1fr);
      gap: 14px;
      margin: 22px 0;
    }}
    .label {{
      display: block;
      font-size: 0.73rem;
      font-weight: 800;
      text-transform: uppercase;
      color: var(--muted);
      margin: 0 0 6px;
      letter-spacing: 0.06em;
    }}
    .plans {{
      display: grid;
      gap: 18px;
    }}
    .plan {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .plan-header {{
      display: grid;
      grid-template-columns: minmax(0, 180px) minmax(0, 1fr);
      gap: 16px;
      align-items: start;
      padding: 18px;
      border-top: 7px solid var(--teal);
      border-bottom: 1px solid var(--line);
    }}
    .plan:nth-child(2) .plan-header {{ border-top-color: var(--coral); }}
    .plan:nth-child(3) .plan-header {{ border-top-color: var(--blue); }}
    .plan-kicker {{
      font-size: 0.78rem;
      font-weight: 900;
      text-transform: uppercase;
      color: var(--muted);
      letter-spacing: 0.07em;
    }}
    .plan-title input {{
      font-size: clamp(1.25rem, 2vw, 1.85rem);
      font-weight: 800;
      line-height: 1.05;
    }}
    .plan-body {{
      padding: 18px;
      display: grid;
      gap: 18px;
    }}
    .timeline {{
      display: grid;
      grid-template-columns: repeat(6, minmax(145px, 1fr));
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow-x: auto;
      background: #fbf7ef;
    }}
    .year {{
      min-width: 145px;
      padding: 14px;
      border-right: 1px solid var(--line);
    }}
    .year:last-child {{ border-right: 0; }}
    .year-number {{
      width: 34px;
      height: 34px;
      display: grid;
      place-items: center;
      border: 1px solid currentColor;
      border-radius: 999px;
      color: var(--teal);
      font-weight: 900;
      margin-bottom: 10px;
    }}
    .plan:nth-child(2) .year-number {{ color: var(--coral); }}
    .plan:nth-child(3) .year-number {{ color: var(--blue); }}
    .year textarea {{ min-height: 132px; }}
    .split {{
      display: grid;
      grid-template-columns: minmax(0, 360px) minmax(0, 1fr);
      gap: 18px;
    }}
    .gauges {{
      display: grid;
      gap: 12px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbf7ef;
    }}
    .gauge-row {{
      display: grid;
      grid-template-columns: 96px minmax(0, 1fr) 40px;
      gap: 10px;
      align-items: center;
    }}
    input[type="range"] {{ width: 100%; accent-color: var(--teal); }}
    .plan:nth-child(2) input[type="range"] {{ accent-color: var(--coral); }}
    .plan:nth-child(3) input[type="range"] {{ accent-color: var(--blue); }}
    .gauge-value {{ font-weight: 900; text-align: right; }}
    .field-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }}
    .field-grid textarea {{ min-height: 128px; }}
    .synthesis {{
      margin-top: 22px;
      padding: 18px;
      border: 2px solid var(--ink);
      border-radius: 8px;
      background: var(--surface);
      box-shadow: var(--shadow);
    }}
    .synthesis h2 {{ margin: 0 0 14px; font-size: 1.35rem; }}
    .synthesis-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
    }}
    .footer {{
      margin-top: 24px;
      color: var(--muted);
      font-size: 0.86rem;
      line-height: 1.45;
    }}
    .hidden {{ display: none; }}
    @media (max-width: 860px) {{
      .hero, .meta-grid, .plan-header, .split, .field-grid, .synthesis-grid {{
        grid-template-columns: 1fr;
      }}
      .actions {{ justify-content: flex-start; }}
      .status {{ text-align: left; }}
      .shell {{ padding-inline: 14px; }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div>
        <div class="eyebrow">Odyssey Planning</div>
        <h1>{safe_title}</h1>
        <p class="context">Three different five-year futures, made concrete enough to test. Edit directly in this page; your browser autosaves changes locally.</p>
      </div>
      <div>
        <div class="actions">
          <button id="export-json" type="button">Export JSON</button>
          <button id="import-json" class="secondary" type="button">Import JSON</button>
          <button id="reset-data" class="secondary" type="button">Reset</button>
          <button id="clear-save" class="secondary" type="button">Clear saved edits</button>
          <input id="file-input" class="hidden" type="file" accept="application/json,.json">
        </div>
        <div id="status" class="status" aria-live="polite"></div>
      </div>
    </section>
    <section class="meta-grid">
      <label>
        <span class="label">Name</span>
        <input type="text" data-field="participant.name">
      </label>
      <label>
        <span class="label">Current context</span>
        <textarea data-field="participant.context"></textarea>
      </label>
    </section>
    <section id="plans" class="plans"></section>
    <section id="synthesis" class="synthesis"></section>
    <p class="footer">Built as a private local artifact inspired by Odyssey Planning from Designing Your Life. This page has no network dependencies; use Export JSON to keep a portable copy of your answers.</p>
  </main>
  <script id="initial-data" type="application/json">{embedded_json}</script>
  <script>
    const initialData = JSON.parse(document.getElementById("initial-data").textContent);
    const storageKey = "life-design-frameworks:" + initialData.exercise + ":" + initialData.createdAt;
    const planLabels = {{
      "expected_path": "Life #1: Current story",
      "alternative_path": "Life #2: Alternative path",
      "wildcard": "Life #3: Wildcard"
    }};
    const gaugeLabels = {{
      "resources": "Resources",
      "likeIt": "I like it",
      "confidence": "Confidence",
      "coherence": "Coherence"
    }};
    const stepLabels = {{
      "people": "People to talk to",
      "experiments": "Small experiments",
      "reflections": "Reflection prompts"
    }};
    const synthesisLabels = {{
      "commonThreads": "Common threads",
      "tensions": "Tensions",
      "nextExperiments": "Next experiments",
      "reflectionPrompts": "Reflection prompts"
    }};
    let state = loadState();

    function clone(value) {{
      return JSON.parse(JSON.stringify(value));
    }}
    function escapeHtml(value) {{
      return String(value ?? "").replace(/[&<>"']/g, char => ({{
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }}[char]));
    }}
    function lines(value) {{
      return Array.isArray(value) ? value.join("\\n") : "";
    }}
    function listFromText(value) {{
      return String(value).split(/\\r?\\n/).map(item => item.trim()).filter(Boolean);
    }}
    function loadState() {{
      try {{
        const saved = localStorage.getItem(storageKey);
        return saved ? JSON.parse(saved) : clone(initialData);
      }} catch {{
        return clone(initialData);
      }}
    }}
    function saveState(message = "Saved locally") {{
      localStorage.setItem(storageKey, JSON.stringify(state));
      const status = document.getElementById("status");
      status.textContent = message;
      clearTimeout(saveState.timer);
      saveState.timer = setTimeout(() => {{ status.textContent = ""; }}, 1800);
    }}
    function render() {{
      document.querySelector('[data-field="participant.name"]').value = state.participant?.name || "";
      document.querySelector('[data-field="participant.context"]').value = state.participant?.context || "";
      document.getElementById("plans").innerHTML = state.plans.map(renderPlan).join("");
      document.getElementById("synthesis").innerHTML = renderSynthesis();
      bindInputs();
    }}
    function renderPlan(plan) {{
      const timeline = [...plan.timeline].sort((a, b) => a.year - b.year).map(item => `
        <div class="year">
          <div class="year-number">${{item.year}}</div>
          <textarea data-plan="${{plan.id}}" data-timeline-year="${{item.year}}">${{escapeHtml(item.milestone)}}</textarea>
        </div>
      `).join("");
      const gauges = Object.keys(gaugeLabels).map(key => `
        <label class="gauge-row">
          <span>${{gaugeLabels[key]}}</span>
          <input type="range" min="0" max="100" value="${{Number(plan.gauges[key] || 0)}}" data-plan="${{plan.id}}" data-gauge="${{key}}">
          <span class="gauge-value" data-gauge-value="${{plan.id}}:${{key}}">${{Number(plan.gauges[key] || 0)}}</span>
        </label>
      `).join("");
      const steps = Object.keys(stepLabels).map(key => `
        <label>
          <span class="label">${{stepLabels[key]}}</span>
          <textarea data-plan="${{plan.id}}" data-step="${{key}}">${{escapeHtml(lines(plan.prototypeSteps[key]))}}</textarea>
        </label>
      `).join("");
      return `
        <article class="plan">
          <div class="plan-header">
            <div>
              <div class="plan-kicker">${{escapeHtml(planLabels[plan.promptType] || plan.promptType)}}</div>
            </div>
            <label class="plan-title">
              <span class="label">Six-word title</span>
              <input type="text" value="${{escapeHtml(plan.titleSixWords)}}" data-plan="${{plan.id}}" data-plan-field="titleSixWords">
            </label>
          </div>
          <div class="plan-body">
            <label>
              <span class="label">Story</span>
              <textarea data-plan="${{plan.id}}" data-plan-field="summary">${{escapeHtml(plan.summary || "")}}</textarea>
            </label>
            <div class="timeline">${{timeline}}</div>
            <div class="split">
              <div class="gauges">${{gauges}}</div>
              <label>
                <span class="label">Questions this plan raises</span>
                <textarea data-plan="${{plan.id}}" data-list="questionsRaised">${{escapeHtml(lines(plan.questionsRaised))}}</textarea>
              </label>
            </div>
            <div class="field-grid">${{steps}}</div>
          </div>
        </article>
      `;
    }}
    function renderSynthesis() {{
      const body = Object.keys(synthesisLabels).map(key => `
        <label>
          <span class="label">${{synthesisLabels[key]}}</span>
          <textarea data-synthesis="${{key}}">${{escapeHtml(lines(state.synthesis[key]))}}</textarea>
        </label>
      `).join("");
      return `<h2>Synthesis</h2><div class="synthesis-grid">${{body}}</div>`;
    }}
    function planById(id) {{
      return state.plans.find(plan => plan.id === id);
    }}
    function bindInputs() {{
      document.querySelectorAll("[data-field]").forEach(input => {{
        input.addEventListener("input", event => {{
          const field = event.target.dataset.field;
          if (field === "participant.name") state.participant.name = event.target.value;
          if (field === "participant.context") state.participant.context = event.target.value;
          saveState();
        }});
      }});
      document.querySelectorAll("[data-plan-field]").forEach(input => {{
        input.addEventListener("input", event => {{
          planById(event.target.dataset.plan)[event.target.dataset.planField] = event.target.value;
          saveState();
        }});
      }});
      document.querySelectorAll("[data-timeline-year]").forEach(input => {{
        input.addEventListener("input", event => {{
          const plan = planById(event.target.dataset.plan);
          const year = Number(event.target.dataset.timelineYear);
          plan.timeline.find(item => item.year === year).milestone = event.target.value;
          saveState();
        }});
      }});
      document.querySelectorAll("[data-gauge]").forEach(input => {{
        input.addEventListener("input", event => {{
          const plan = planById(event.target.dataset.plan);
          const key = event.target.dataset.gauge;
          plan.gauges[key] = Number(event.target.value);
          document.querySelector(`[data-gauge-value="${{plan.id}}:${{key}}"]`).textContent = event.target.value;
          saveState();
        }});
      }});
      document.querySelectorAll("[data-list]").forEach(input => {{
        input.addEventListener("input", event => {{
          planById(event.target.dataset.plan)[event.target.dataset.list] = listFromText(event.target.value);
          saveState();
        }});
      }});
      document.querySelectorAll("[data-step]").forEach(input => {{
        input.addEventListener("input", event => {{
          planById(event.target.dataset.plan).prototypeSteps[event.target.dataset.step] = listFromText(event.target.value);
          saveState();
        }});
      }});
      document.querySelectorAll("[data-synthesis]").forEach(input => {{
        input.addEventListener("input", event => {{
          state.synthesis[event.target.dataset.synthesis] = listFromText(event.target.value);
          saveState();
        }});
      }});
    }}
    function exportJson() {{
      const blob = new Blob([JSON.stringify(state, null, 2)], {{ type: "application/json" }});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "odyssey-plan.json";
      link.click();
      URL.revokeObjectURL(url);
      saveState("Exported JSON");
    }}
    function importJson(file) {{
      const reader = new FileReader();
      reader.onload = () => {{
        try {{
          const imported = JSON.parse(reader.result);
          if (imported.exercise !== "odyssey-planning" || !Array.isArray(imported.plans)) {{
            throw new Error("Not an Odyssey Planning JSON file");
          }}
          state = imported;
          render();
          saveState("Imported JSON");
        }} catch (error) {{
          document.getElementById("status").textContent = "Import failed: " + error.message;
        }}
      }};
      reader.readAsText(file);
    }}
    document.getElementById("export-json").addEventListener("click", exportJson);
    document.getElementById("import-json").addEventListener("click", () => document.getElementById("file-input").click());
    document.getElementById("file-input").addEventListener("change", event => {{
      const file = event.target.files[0];
      if (file) importJson(file);
      event.target.value = "";
    }});
    document.getElementById("reset-data").addEventListener("click", () => {{
      state = clone(initialData);
      render();
      saveState("Reset to embedded plan");
    }});
    document.getElementById("clear-save").addEventListener("click", () => {{
      localStorage.removeItem(storageKey);
      document.getElementById("status").textContent = "Saved edits cleared";
    }});
    render();
  </script>
</body>
</html>
"""


def render_artifacts(input_path: Path, output_dir: Path, basename: str = "odyssey-plan") -> tuple[Path, Path]:
    raw = json.loads(input_path.read_text(encoding="utf-8"))
    data = normalize_odyssey(raw)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{basename}.json"
    html_path = output_dir / f"{basename}.html"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html_path.write_text(_render_html(data), encoding="utf-8")
    return json_path, html_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Odyssey Planning JSON to local artifacts.")
    parser.add_argument("input_json", type=Path, help="Path to Odyssey Planning JSON")
    parser.add_argument("--out", type=Path, default=Path("out"), help="Output directory")
    parser.add_argument("--name", default="odyssey-plan", help="Output file basename")
    args = parser.parse_args()

    try:
      json_path, html_path = render_artifacts(args.input_json, args.out, args.name)
    except (json.JSONDecodeError, OdysseyValidationError) as error:
      parser.exit(2, f"error: {error}\n")

    print(f"Wrote {json_path}")
    print(f"Wrote {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
