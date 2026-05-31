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


PLAN_LABELS = {
    "expected_path": "Current path",
    "alternative_path": "Alternative path",
    "wildcard": "Wildcard path",
}
SHORT_LABELS = {"life-1": "Life 1", "life-2": "Life 2", "life-3": "Life 3"}
ROUTE_COLORS = {"life-1": "#137f79", "life-2": "#cb5b4d", "life-3": "#365f9f"}
GAUGE_LABELS = {
    "resources": "Resources",
    "likeIt": "I like it",
    "confidence": "Confidence",
    "coherence": "Coherence",
}
STEP_LABELS = {"people": "People", "experiments": "Experiments", "reflections": "Reflections"}
SYNTHESIS_LABELS = {
    "commonThreads": "Common threads",
    "tensions": "Tensions",
    "nextExperiments": "Next experiments",
    "reflectionPrompts": "Reflection prompts",
}


def _e(value: Any) -> str:
    return html.escape(str(value or ""))


def _list_markup(items: list[str]) -> str:
    if not items:
        return '<p class="empty">Nothing captured yet.</p>'
    return "<ul>" + "".join(f"<li>{_e(item)}</li>" for item in items) + "</ul>"


def _truncate(value: str, length: int = 220) -> str:
    text = str(value or "").strip()
    if len(text) <= length:
        return text
    return text[: length - 1].strip() + "..."


def _score_rows(plan: dict[str, Any]) -> str:
    rows = []
    for key, label in GAUGE_LABELS.items():
        value = int(plan["gauges"].get(key, 0))
        rows.append(
            f"""<div class="score-row">
          <span>{_e(label)}</span>
          <div class="score-track"><i class="score-fill" data-gauge-bar="{_e(plan['id'])}:{_e(key)}" style="--score:{value}"></i></div>
          <strong>{value}</strong>
        </div>"""
        )
    return '<div class="score-set">' + "".join(rows) + "</div>"


def _render_static_atlas(data: dict[str, Any], title: str) -> str:
    hero_stops = []
    route_cards = []
    route_plans = []
    for plan in data["plans"]:
        plan_id = plan["id"]
        color = ROUTE_COLORS.get(plan_id, "#137f79")
        label = PLAN_LABELS.get(plan["promptType"], plan["promptType"])
        short_label = SHORT_LABELS.get(plan_id, plan_id)
        hero_stops.append(
            f"""<div class="map-stop" style="--accent:{color}">
          <span>{_e(short_label)} / {_e(label)}</span>
          <strong>{_e(plan["titleSixWords"])}</strong>
        </div>"""
        )
        route_cards.append(
            f"""<article class="route-card" style="--accent:{color}">
        <span class="route-label">{_e(short_label)} / {_e(label)}</span>
        <h3>{_e(plan["titleSixWords"])}</h3>
        <p>{_e(_truncate(plan.get("summary", "")))}</p>
        {_score_rows(plan)}
      </article>"""
        )
        signals = "".join(
            f'<span class="signal-chip">{_e(gauge_label)} <b>{int(plan["gauges"].get(key, 0))}</b></span>'
            for key, gauge_label in GAUGE_LABELS.items()
        )
        waypoints = "".join(
            f"""<div class="waypoint">
          <div class="waypoint-marker">{int(item["year"])}</div>
          <p>{_e(item["milestone"])}</p>
        </div>"""
            for item in sorted(plan["timeline"], key=lambda row: row["year"])
        )
        steps = plan["prototypeSteps"]
        route_plans.append(
            f"""<article class="route-plan" id="{_e(plan_id)}" style="--accent:{color}">
        <aside class="route-rail">
          <strong>{_e(short_label)}</strong>
          <span>{_e(label)}</span>
          <a href="#{_e(plan_id)}">Route {_e(plan_id[-1])}</a>
        </aside>
        <div>
          <div class="route-title">
            <div>
              <h2>{_e(plan["titleSixWords"])}</h2>
              <p>{_e(plan.get("summary", ""))}</p>
            </div>
            <div class="route-signal" aria-label="Route scores">{signals}</div>
          </div>
          <div class="route-waypoints">{waypoints}</div>
          <div class="detail-grid">
            <section class="detail-block"><h3>Questions</h3>{_list_markup(plan["questionsRaised"])}</section>
            <section class="detail-block"><h3>{STEP_LABELS["people"]}</h3>{_list_markup(steps["people"])}</section>
            <section class="detail-block"><h3>{STEP_LABELS["experiments"]}</h3>{_list_markup(steps["experiments"])}</section>
            <section class="detail-block"><h3>{STEP_LABELS["reflections"]}</h3>{_list_markup(steps["reflections"])}</section>
          </div>
        </div>
      </article>"""
        )

    synthesis_blocks = "".join(
        f"""<section class="synthesis-block">
          <h3>{_e(label)}</h3>
          {_list_markup(data["synthesis"].get(key, []))}
        </section>"""
        for key, label in SYNTHESIS_LABELS.items()
    )
    context = data["participant"].get("context") or "Three different five-year futures, made concrete enough to compare, test, and revise."
    return f"""
      <section class="hero">
        <div>
          <p class="eyebrow">Odyssey Planning / Future Atlas</p>
          <h1>{_e(title)}</h1>
          <p class="context">{_e(context)}</p>
        </div>
        <aside class="hero-map" aria-label="Future routes">{''.join(hero_stops)}</aside>
      </section>
      <section class="comparison" aria-labelledby="compare-heading">
        <div class="section-head">
          <div><h2 id="compare-heading">Compare the routes</h2></div>
          <p>Each path has a different kind of gravity. The scores make the tradeoffs visible without flattening the story.</p>
        </div>
        <div class="route-grid">{''.join(route_cards)}</div>
      </section>
      <section class="routes" aria-label="Future routes">{''.join(route_plans)}</section>
      <section class="synthesis">
        <div class="section-head"><div><h2>Synthesis</h2></div><p>The useful part is not choosing immediately. It is seeing the repeated signals, the tradeoffs, and the next tests.</p></div>
        <div class="synthesis-grid">{synthesis_blocks}</div>
      </section>
    """


def _render_html(data: dict[str, Any]) -> str:
    title = "Odyssey Plan"
    participant = data["participant"].get("name")
    if participant:
        title = f"{participant}'s Odyssey Plan"
    safe_title = html.escape(title)
    embedded_json = _json_for_script(data)
    static_atlas = _render_static_atlas(data, title)
    template = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__SAFE_TITLE__</title>
  <link rel="icon" href="data:,">
  <style>
    :root {
      color-scheme: light;
      --ink: #151b22;
      --muted: #66707f;
      --paper: #f6f1e7;
      --paper-deep: #ebe0cf;
      --surface: #fffdf7;
      --line: #d7cbb8;
      --line-strong: #211b15;
      --route-1: #137f79;
      --route-2: #cb5b4d;
      --route-3: #365f9f;
      --gold: #c38b2c;
      --shadow: 0 22px 70px rgba(25, 29, 35, 0.13);
      --radius: 8px;
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        linear-gradient(115deg, rgba(19, 127, 121, 0.09), transparent 30rem),
        linear-gradient(245deg, rgba(195, 139, 44, 0.1), transparent 28rem),
        var(--paper);
      color: var(--ink);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }
    button, input, textarea { font: inherit; }
    button, .button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 42px;
      border: 1px solid var(--ink);
      border-radius: var(--radius);
      padding: 0.64rem 0.86rem;
      background: var(--ink);
      color: var(--surface);
      text-decoration: none;
      cursor: pointer;
      transition: transform 160ms ease, background 160ms ease, color 160ms ease, border-color 160ms ease;
    }
    button:hover, .button:hover { transform: translateY(-1px); }
    button.secondary, .button.secondary { background: transparent; color: var(--ink); }
    button.subtle { background: rgba(255, 253, 247, 0.76); color: var(--ink); border-color: var(--line); }
    button.danger { background: transparent; color: #9b2d24; border-color: rgba(155, 45, 36, 0.45); }
    input[type="text"], textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--surface);
      color: var(--ink);
      padding: 0.72rem 0.78rem;
      resize: vertical;
    }
    textarea { min-height: 104px; line-height: 1.45; }
    input[type="range"] { width: 100%; accent-color: var(--accent, var(--route-1)); }
    input:focus, textarea:focus, button:focus-visible, a:focus-visible {
      outline: 2px solid color-mix(in srgb, var(--accent, var(--route-1)) 40%, transparent);
      outline-offset: 2px;
    }
    .page-shell { max-width: 1240px; margin: 0 auto; padding: 20px 18px 60px; }
    .topbar {
      position: sticky;
      top: 0;
      z-index: 20;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 18px;
      padding: 12px 0;
      background: color-mix(in srgb, var(--paper) 88%, transparent);
      border-bottom: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
      backdrop-filter: blur(18px);
    }
    .brand-mark { font-weight: 900; text-transform: uppercase; letter-spacing: 0.04em; }
    .top-actions { display: flex; flex-wrap: wrap; gap: 10px; justify-content: flex-end; }
    .hero {
      min-height: min(680px, calc(100svh - 70px));
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(270px, 0.34fr);
      gap: clamp(28px, 6vw, 72px);
      align-items: center;
      padding: clamp(42px, 8vw, 88px) 0 clamp(34px, 7vw, 72px);
    }
    .eyebrow {
      margin: 0 0 14px;
      color: var(--route-1);
      font-size: 0.76rem;
      font-weight: 900;
      letter-spacing: 0.11em;
      text-transform: uppercase;
    }
    h1 {
      margin: 0;
      max-width: 850px;
      font-family: ui-serif, Georgia, "Times New Roman", serif;
      font-size: clamp(3.2rem, 9vw, 8rem);
      line-height: 0.9;
      letter-spacing: 0;
    }
    .context {
      max-width: 760px;
      margin: 24px 0 0;
      color: #3a4653;
      font-size: clamp(1.02rem, 1.8vw, 1.28rem);
      line-height: 1.55;
    }
    .hero-map {
      position: relative;
      min-height: 360px;
      border-left: 2px solid var(--line-strong);
      padding-left: 28px;
    }
    .hero-map::before {
      content: "";
      position: absolute;
      left: -7px;
      top: 18px;
      bottom: 18px;
      width: 12px;
      border-radius: 999px;
      background: linear-gradient(var(--route-1), var(--route-2), var(--route-3));
    }
    .map-stop {
      position: relative;
      margin: 0 0 28px;
      padding: 0 0 0 12px;
    }
    .map-stop::before {
      content: "";
      position: absolute;
      left: -38px;
      top: 7px;
      width: 12px;
      height: 12px;
      border: 3px solid var(--surface);
      border-radius: 50%;
      background: var(--accent);
      box-shadow: 0 0 0 2px var(--accent);
    }
    .map-stop span { display: block; color: var(--muted); font-size: 0.75rem; font-weight: 850; text-transform: uppercase; letter-spacing: 0.08em; }
    .map-stop strong { display: block; margin-top: 5px; font-size: clamp(1.05rem, 1.8vw, 1.35rem); line-height: 1.1; }
    .section-head {
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 18px;
      margin: 0 0 20px;
      border-top: 2px solid var(--line-strong);
      padding-top: 22px;
    }
    .section-head h2, .route-title h2, .synthesis h2 {
      margin: 0;
      font-family: ui-serif, Georgia, "Times New Roman", serif;
      font-size: clamp(1.7rem, 3vw, 3rem);
      line-height: 1;
    }
    .section-head p { max-width: 540px; margin: 0; color: var(--muted); line-height: 1.5; }
    .comparison { margin-bottom: clamp(34px, 7vw, 78px); }
    .route-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
    .route-card {
      --accent: var(--route-1);
      min-width: 0;
      padding: 18px;
      border-top: 7px solid var(--accent);
      border-radius: var(--radius);
      background: rgba(255, 253, 247, 0.74);
      box-shadow: 0 1px 0 rgba(21, 27, 34, 0.08);
    }
    .route-card h3 { margin: 8px 0 10px; font-size: 1.18rem; line-height: 1.12; }
    .route-card p { margin: 0 0 16px; color: #465160; line-height: 1.42; }
    .route-label, .label {
      display: block;
      color: var(--muted);
      font-size: 0.72rem;
      font-weight: 900;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .score-set { display: grid; gap: 9px; }
    .score-row { display: grid; grid-template-columns: 88px minmax(0, 1fr) 34px; gap: 10px; align-items: center; font-size: 0.9rem; }
    .score-track { height: 8px; overflow: hidden; border-radius: 999px; background: color-mix(in srgb, var(--accent) 14%, var(--paper-deep)); }
    .score-fill { display: block; width: calc(var(--score) * 1%); height: 100%; border-radius: inherit; background: var(--accent); }
    .score-row strong { text-align: right; font-size: 0.86rem; }
    .routes { display: grid; gap: clamp(34px, 7vw, 80px); }
    .route-plan > *, .route-title > *, .detail-grid > *, .synthesis-grid > *, .route-card { min-width: 0; }
    .route-plan {
      --accent: var(--route-1);
      position: relative;
      display: grid;
      grid-template-columns: minmax(190px, 0.26fr) minmax(0, 1fr);
      gap: clamp(22px, 4vw, 48px);
      padding-top: 28px;
      border-top: 2px solid var(--line-strong);
    }
    .route-rail { position: sticky; top: 78px; align-self: start; color: var(--muted); }
    .route-rail strong { display: block; color: var(--ink); font-size: 1.02rem; margin-bottom: 10px; }
    .route-rail a { display: inline-flex; color: var(--accent); font-weight: 850; text-decoration: none; margin-top: 12px; }
    .route-title { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 20px; align-items: start; margin-bottom: 22px; }
    .route-title p { margin: 14px 0 0; color: #3f4b58; line-height: 1.55; max-width: 920px; }
    .route-signal { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
    .signal-chip { border: 1px solid var(--line); border-radius: 999px; padding: 6px 9px; background: rgba(255, 253, 247, 0.66); font-size: 0.82rem; white-space: nowrap; }
    .signal-chip b { color: var(--accent); }
    .route-waypoints {
      position: relative;
      display: grid;
      grid-template-columns: repeat(6, minmax(138px, 1fr));
      gap: 12px;
      margin: 0 0 18px;
      overflow-x: auto;
      max-width: 100%;
      min-width: 0;
      padding: 12px 2px 16px;
    }
    .route-waypoints::before {
      content: "";
      position: absolute;
      left: 32px;
      right: 32px;
      top: 44px;
      height: 2px;
      background: linear-gradient(90deg, color-mix(in srgb, var(--accent) 18%, transparent), var(--accent), color-mix(in srgb, var(--accent) 18%, transparent));
      pointer-events: none;
    }
    .waypoint {
      position: relative;
      min-width: 138px;
      padding-top: 58px;
    }
    .waypoint-marker {
      position: absolute;
      top: 19px;
      left: 0;
      width: 48px;
      height: 48px;
      display: grid;
      place-items: center;
      border: 2px solid var(--accent);
      border-radius: 50%;
      background: var(--surface);
      color: var(--accent);
      font-weight: 950;
      box-shadow: 0 0 0 6px var(--paper);
    }
    .waypoint p {
      margin: 0;
      min-height: 148px;
      padding: 14px;
      border: 1px solid color-mix(in srgb, var(--accent) 30%, var(--line));
      border-radius: var(--radius);
      background: rgba(255, 253, 247, 0.78);
      color: #3d4652;
      line-height: 1.38;
    }
    .detail-grid { display: grid; grid-template-columns: minmax(0, 1fr) repeat(3, minmax(0, 0.86fr)); gap: 14px; }
    .detail-block {
      min-width: 0;
      padding: 15px 0 0;
      border-top: 1px solid color-mix(in srgb, var(--accent) 36%, var(--line));
    }
    .detail-block h3 { margin: 0 0 10px; font-size: 0.96rem; }
    ul { margin: 0; padding-left: 1.1rem; }
    li { margin: 0.38rem 0; line-height: 1.4; }
    .synthesis { margin-top: clamp(36px, 8vw, 90px); padding-top: 28px; border-top: 2px solid var(--line-strong); }
    .synthesis-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 18px; margin-top: 22px; }
    .synthesis-block { min-width: 0; padding-top: 14px; border-top: 1px solid var(--line); }
    .footer { margin: 34px 0 0; color: var(--muted); font-size: 0.86rem; line-height: 1.45; }
    .overlay {
      position: fixed;
      inset: 0;
      z-index: 40;
      display: none;
      background: rgba(16, 20, 26, 0.34);
      backdrop-filter: blur(2px);
    }
    .drawer {
      position: fixed;
      z-index: 50;
      top: 0;
      right: 0;
      width: min(520px, 100vw);
      height: 100svh;
      display: flex;
      flex-direction: column;
      transform: translateX(104%);
      transition: transform 240ms ease;
      background: var(--surface);
      box-shadow: -24px 0 70px rgba(18, 22, 28, 0.18);
    }
    body.editor-open .overlay { display: block; }
    body.editor-open .drawer { transform: translateX(0); }
    .drawer-head { display: flex; align-items: start; justify-content: space-between; gap: 14px; padding: 18px; border-bottom: 1px solid var(--line); }
    .drawer-head h2 { margin: 0; font-family: ui-serif, Georgia, serif; font-size: 1.55rem; }
    .status { min-height: 20px; color: var(--route-1); font-size: 0.88rem; margin-top: 4px; }
    .tabs { display: flex; gap: 8px; overflow-x: auto; padding: 12px 18px; border-bottom: 1px solid var(--line); }
    .tabs button { flex: 0 0 auto; min-height: 36px; padding: 0.48rem 0.66rem; background: transparent; color: var(--muted); border-color: var(--line); }
    .tabs button[aria-selected="true"] { background: var(--ink); color: var(--surface); border-color: var(--ink); }
    .drawer-body { overflow: auto; padding: 18px; }
    .editor-fields { display: grid; gap: 14px; }
    .editor-fields label { display: grid; gap: 6px; }
    .editor-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-top: 4px; }
    .timeline-editor { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .range-row { display: grid; grid-template-columns: 92px minmax(0, 1fr) 36px; gap: 10px; align-items: center; }
    .hidden { display: none !important; }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; scroll-behavior: auto !important; }
    }
    @media (max-width: 980px) {
      .hero, .route-grid, .route-plan, .route-title, .detail-grid, .synthesis-grid { grid-template-columns: 1fr; }
      .hero { min-height: auto; }
      .hero-map { min-height: auto; }
      .route-rail { position: static; }
      .route-signal { justify-content: flex-start; }
    }
    @media (max-width: 640px) {
      .page-shell { padding-inline: 12px; }
      .topbar { align-items: stretch; flex-direction: column; }
      .top-actions { justify-content: flex-start; }
      .route-card { padding: 15px; }
      .section-head { display: block; }
      .section-head p { margin-top: 10px; }
      .drawer { top: auto; bottom: 0; width: 100vw; height: min(88svh, 760px); transform: translateY(104%); border-radius: 14px 14px 0 0; }
      body.editor-open .drawer { transform: translateY(0); }
      .timeline-editor, .editor-actions { grid-template-columns: 1fr; }
    }
    @media print {
      body { background: #fffdf7; }
      .topbar, .overlay, .drawer { display: none !important; }
      .page-shell { max-width: none; padding: 0; }
      .hero { min-height: 0; padding: 0 0 24px; }
      .route-plan, .synthesis, .comparison { break-inside: avoid; }
      button, .button { display: none; }
    }
  </style>
</head>
<body>
  <main class="page-shell">
    <header class="topbar">
      <div class="brand-mark">Future Atlas</div>
      <div class="top-actions">
        <button id="open-editor" type="button">Edit</button>
        <button class="secondary" type="button" onclick="window.print()">Print</button>
      </div>
    </header>
    <div id="atlas">__STATIC_ATLAS__</div>
    <p class="footer">Private local artifact inspired by Odyssey Planning from Designing Your Life. The page has no network dependencies; use the editor to export a portable JSON copy.</p>
  </main>
  <div id="overlay" class="overlay" aria-hidden="true"></div>
  <aside id="edit-drawer" class="drawer" aria-label="Edit Odyssey Plan" aria-hidden="true">
    <div class="drawer-head">
      <div>
        <span class="label">Edit Atlas</span>
        <h2>Your answers</h2>
        <div id="status" class="status" aria-live="polite"></div>
      </div>
      <button id="close-editor" class="subtle" type="button">Close</button>
    </div>
    <nav id="editor-tabs" class="tabs" aria-label="Editor sections"></nav>
    <div id="editor-body" class="drawer-body"></div>
  </aside>
  <input id="file-input" class="hidden" type="file" accept="application/json,.json">
  <script id="initial-data" type="application/json">__EMBEDDED_JSON__</script>
  <script>
    const initialData = JSON.parse(document.getElementById("initial-data").textContent);
    const storageKey = "life-design-frameworks:" + initialData.exercise + ":" + initialData.createdAt;
    const planLabels = {
      "expected_path": "Current path",
      "alternative_path": "Alternative path",
      "wildcard": "Wildcard path"
    };
    const shortLabels = { "life-1": "Life 1", "life-2": "Life 2", "life-3": "Life 3" };
    const routeColors = { "life-1": "#137f79", "life-2": "#cb5b4d", "life-3": "#365f9f" };
    const gaugeLabels = {
      "resources": "Resources",
      "likeIt": "I like it",
      "confidence": "Confidence",
      "coherence": "Coherence"
    };
    const stepLabels = {
      "people": "People",
      "experiments": "Experiments",
      "reflections": "Reflections"
    };
    const synthesisLabels = {
      "commonThreads": "Common threads",
      "tensions": "Tensions",
      "nextExperiments": "Next experiments",
      "reflectionPrompts": "Reflection prompts"
    };
    const editorTabs = ["Context", "Life 1", "Life 2", "Life 3", "Synthesis"];
    let state = loadState();
    let activeTab = "Context";

    function clone(value) { return JSON.parse(JSON.stringify(value)); }
    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[char]));
    }
    function lines(value) { return Array.isArray(value) ? value.join("\\n") : ""; }
    function listFromText(value) { return String(value).split(/\\r?\\n/).map(item => item.trim()).filter(Boolean); }
    function planById(id) { return state.plans.find(plan => plan.id === id); }
    function storageGet(key) {
      try { return window.localStorage.getItem(key); } catch { return null; }
    }
    function storageSet(key, value) {
      try { window.localStorage.setItem(key, value); return true; } catch { return false; }
    }
    function storageRemove(key) {
      try { window.localStorage.removeItem(key); } catch {}
    }
    function isRenderableState(value) {
      return !!(
        value &&
        value.exercise === "odyssey-planning" &&
        value.participant &&
        Array.isArray(value.plans) &&
        value.plans.length === 3 &&
        value.plans.every(plan =>
          plan &&
          typeof plan.id === "string" &&
          typeof plan.promptType === "string" &&
          Array.isArray(plan.timeline) &&
          plan.timeline.length === 6 &&
          plan.gauges &&
          plan.prototypeSteps
        ) &&
        value.synthesis
      );
    }
    function normalizedState(value) {
      const fallback = clone(initialData);
      if (!isRenderableState(value)) return fallback;
      return {
        ...fallback,
        ...value,
        participant: { ...fallback.participant, ...(value.participant || {}) },
        plans: value.plans,
        synthesis: { ...fallback.synthesis, ...(value.synthesis || {}) }
      };
    }
    function loadState() {
      try {
        const saved = storageGet(storageKey);
        if (!saved) return clone(initialData);
        const parsed = JSON.parse(saved);
        if (!isRenderableState(parsed)) {
          storageRemove(storageKey);
          return clone(initialData);
        }
        return normalizedState(parsed);
      } catch {
        storageRemove(storageKey);
        return clone(initialData);
      }
    }
    function saveState(message = "Saved locally") {
      const didSave = storageSet(storageKey, JSON.stringify(state));
      const status = document.getElementById("status");
      status.textContent = didSave ? message : "Edits held in this page; export JSON to keep a copy";
      clearTimeout(saveState.timer);
      saveState.timer = setTimeout(() => { status.textContent = ""; }, 1800);
    }
    function truncated(value, length = 220) {
      const text = String(value || "").trim();
      if (text.length <= length) return text;
      return text.slice(0, length - 1).trim() + "...";
    }
    function listMarkup(items) {
      if (!items || !items.length) return `<p class="empty">Nothing captured yet.</p>`;
      return `<ul>${items.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
    }
    function scoreRows(plan, attrs = "") {
      return `<div class="score-set">${Object.keys(gaugeLabels).map(key => {
        const value = Number(plan.gauges[key] || 0);
        return `<div class="score-row" ${attrs}>
          <span>${gaugeLabels[key]}</span>
          <div class="score-track"><i class="score-fill" data-gauge-bar="${plan.id}:${key}" style="--score:${value}"></i></div>
          <strong>${value}</strong>
        </div>`;
      }).join("")}</div>`;
    }
    function renderAtlas() {
      const participant = state.participant?.name || "Your";
      const title = participant === "Your" ? "Your Odyssey Plan" : `${participant}'s Odyssey Plan`;
      const heroStops = state.plans.map(plan => `
        <div class="map-stop" style="--accent:${routeColors[plan.id] || "#137f79"}">
          <span>${shortLabels[plan.id]} / ${planLabels[plan.promptType] || plan.promptType}</span>
          <strong>${escapeHtml(plan.titleSixWords)}</strong>
        </div>
      `).join("");
      document.getElementById("atlas").innerHTML = `
        <section class="hero">
          <div>
            <p class="eyebrow">Odyssey Planning / Future Atlas</p>
            <h1>${escapeHtml(title)}</h1>
            <p class="context">${escapeHtml(state.participant?.context || "Three different five-year futures, made concrete enough to compare, test, and revise.")}</p>
          </div>
          <aside class="hero-map" aria-label="Future routes">${heroStops}</aside>
        </section>
        <section class="comparison" aria-labelledby="compare-heading">
          <div class="section-head">
            <div><h2 id="compare-heading">Compare the routes</h2></div>
            <p>Each path has a different kind of gravity. The scores make the tradeoffs visible without flattening the story.</p>
          </div>
          <div class="route-grid">${state.plans.map(renderRouteCard).join("")}</div>
        </section>
        <section class="routes" aria-label="Future routes">${state.plans.map(renderRoutePlan).join("")}</section>
        ${renderSynthesis()}
      `;
    }
    function renderRouteCard(plan) {
      return `<article class="route-card" style="--accent:${routeColors[plan.id] || "#137f79"}">
        <span class="route-label">${shortLabels[plan.id]} / ${planLabels[plan.promptType] || plan.promptType}</span>
        <h3>${escapeHtml(plan.titleSixWords)}</h3>
        <p>${escapeHtml(truncated(plan.summary))}</p>
        ${scoreRows(plan)}
      </article>`;
    }
    function renderRoutePlan(plan) {
      const steps = plan.prototypeSteps || {};
      const signals = Object.keys(gaugeLabels).map(key => `<span class="signal-chip">${gaugeLabels[key]} <b>${Number(plan.gauges[key] || 0)}</b></span>`).join("");
      const waypoints = [...plan.timeline].sort((a, b) => a.year - b.year).map(item => `
        <div class="waypoint">
          <div class="waypoint-marker">${item.year}</div>
          <p>${escapeHtml(item.milestone)}</p>
        </div>
      `).join("");
      return `<article class="route-plan" id="${plan.id}" style="--accent:${routeColors[plan.id] || "#137f79"}">
        <aside class="route-rail">
          <strong>${shortLabels[plan.id]}</strong>
          <span>${planLabels[plan.promptType] || plan.promptType}</span>
          <a href="#${plan.id}">Route ${plan.id.slice(-1)}</a>
        </aside>
        <div>
          <div class="route-title">
            <div>
              <h2>${escapeHtml(plan.titleSixWords)}</h2>
              <p>${escapeHtml(plan.summary || "")}</p>
            </div>
            <div class="route-signal" aria-label="Route scores">${signals}</div>
          </div>
          <div class="route-waypoints">${waypoints}</div>
          <div class="detail-grid">
            <section class="detail-block"><h3>Questions</h3>${listMarkup(plan.questionsRaised)}</section>
            <section class="detail-block"><h3>${stepLabels.people}</h3>${listMarkup(steps.people)}</section>
            <section class="detail-block"><h3>${stepLabels.experiments}</h3>${listMarkup(steps.experiments)}</section>
            <section class="detail-block"><h3>${stepLabels.reflections}</h3>${listMarkup(steps.reflections)}</section>
          </div>
        </div>
      </article>`;
    }
    function renderSynthesis() {
      return `<section class="synthesis">
        <div class="section-head"><div><h2>Synthesis</h2></div><p>The useful part is not choosing immediately. It is seeing the repeated signals, the tradeoffs, and the next tests.</p></div>
        <div class="synthesis-grid">${Object.keys(synthesisLabels).map(key => `
          <section class="synthesis-block"><h3>${synthesisLabels[key]}</h3>${listMarkup(state.synthesis[key])}</section>
        `).join("")}</div>
      </section>`;
    }
    function renderEditor() {
      document.getElementById("editor-tabs").innerHTML = editorTabs.map(tab => `
        <button type="button" data-editor-tab="${tab}" aria-selected="${String(tab === activeTab)}">${tab}</button>
      `).join("");
      document.getElementById("editor-body").innerHTML = activeTab === "Context" ? renderContextEditor()
        : activeTab === "Synthesis" ? renderSynthesisEditor()
        : renderPlanEditor(state.plans[Number(activeTab.split(" ")[1]) - 1]);
      bindEditorInputs();
      autosizeTextareas();
    }
    function renderContextEditor() {
      return `<div class="editor-fields">
        <label><span class="label">Name</span><input type="text" data-field="participant.name" value="${escapeHtml(state.participant?.name || "")}"></label>
        <label><span class="label">Current context</span><textarea data-field="participant.context">${escapeHtml(state.participant?.context || "")}</textarea></label>
        <div class="editor-actions">
          <button id="export-json" type="button">Export JSON</button>
          <button id="import-json" class="secondary" type="button">Import JSON</button>
          <button id="reset-data" class="secondary" type="button">Reset</button>
          <button id="clear-save" class="danger" type="button">Clear saved edits</button>
        </div>
      </div>`;
    }
    function renderPlanEditor(plan) {
      const timeline = [...plan.timeline].sort((a, b) => a.year - b.year).map(item => `
        <label><span class="label">Year ${item.year}</span><textarea data-plan="${plan.id}" data-timeline-year="${item.year}">${escapeHtml(item.milestone)}</textarea></label>
      `).join("");
      const ranges = Object.keys(gaugeLabels).map(key => `
        <label class="range-row"><span>${gaugeLabels[key]}</span><input type="range" min="0" max="100" value="${Number(plan.gauges[key] || 0)}" data-plan="${plan.id}" data-gauge="${key}" style="--accent:${routeColors[plan.id]}"><strong data-range-value="${plan.id}:${key}">${Number(plan.gauges[key] || 0)}</strong></label>
      `).join("");
      return `<div class="editor-fields" style="--accent:${routeColors[plan.id]}">
        <label><span class="label">Six-word title</span><input type="text" data-plan="${plan.id}" data-plan-field="titleSixWords" value="${escapeHtml(plan.titleSixWords)}"></label>
        <label><span class="label">Story</span><textarea data-plan="${plan.id}" data-plan-field="summary">${escapeHtml(plan.summary || "")}</textarea></label>
        <div class="timeline-editor">${timeline}</div>
        <div class="editor-fields">${ranges}</div>
        <label><span class="label">Questions this plan raises</span><textarea data-plan="${plan.id}" data-list="questionsRaised">${escapeHtml(lines(plan.questionsRaised))}</textarea></label>
        <label><span class="label">People to talk to</span><textarea data-plan="${plan.id}" data-step="people">${escapeHtml(lines(plan.prototypeSteps.people))}</textarea></label>
        <label><span class="label">Small experiments</span><textarea data-plan="${plan.id}" data-step="experiments">${escapeHtml(lines(plan.prototypeSteps.experiments))}</textarea></label>
        <label><span class="label">Reflection prompts</span><textarea data-plan="${plan.id}" data-step="reflections">${escapeHtml(lines(plan.prototypeSteps.reflections))}</textarea></label>
      </div>`;
    }
    function renderSynthesisEditor() {
      return `<div class="editor-fields">${Object.keys(synthesisLabels).map(key => `
        <label><span class="label">${synthesisLabels[key]}</span><textarea data-synthesis="${key}">${escapeHtml(lines(state.synthesis[key]))}</textarea></label>
      `).join("")}</div>`;
    }
    function autosizeTextarea(textarea) {
      const minHeight = Number.parseFloat(getComputedStyle(textarea).minHeight) || 42;
      textarea.style.height = "auto";
      textarea.style.height = Math.max(textarea.scrollHeight + 2, minHeight) + "px";
    }
    function autosizeTextareas(root = document) { root.querySelectorAll("textarea").forEach(autosizeTextarea); }
    function updateAndSave(message) {
      renderAtlas();
      saveState(message);
    }
    function bindEditorInputs() {
      document.querySelectorAll("[data-editor-tab]").forEach(button => {
        button.addEventListener("click", () => {
          activeTab = button.dataset.editorTab;
          renderEditor();
        });
      });
      document.querySelectorAll("[data-field]").forEach(input => {
        input.addEventListener("input", event => {
          const field = event.target.dataset.field;
          if (field === "participant.name") state.participant.name = event.target.value;
          if (field === "participant.context") state.participant.context = event.target.value;
          if (event.target.tagName === "TEXTAREA") autosizeTextarea(event.target);
          updateAndSave();
        });
      });
      document.querySelectorAll("[data-plan-field]").forEach(input => {
        input.addEventListener("input", event => {
          planById(event.target.dataset.plan)[event.target.dataset.planField] = event.target.value;
          if (event.target.tagName === "TEXTAREA") autosizeTextarea(event.target);
          updateAndSave();
        });
      });
      document.querySelectorAll("[data-timeline-year]").forEach(input => {
        input.addEventListener("input", event => {
          const plan = planById(event.target.dataset.plan);
          const year = Number(event.target.dataset.timelineYear);
          plan.timeline.find(item => item.year === year).milestone = event.target.value;
          autosizeTextarea(event.target);
          updateAndSave();
        });
      });
      document.querySelectorAll("[data-gauge]").forEach(input => {
        input.addEventListener("input", event => {
          const plan = planById(event.target.dataset.plan);
          const key = event.target.dataset.gauge;
          plan.gauges[key] = Number(event.target.value);
          const value = document.querySelector(`[data-range-value="${plan.id}:${key}"]`);
          if (value) value.textContent = event.target.value;
          updateAndSave();
        });
      });
      document.querySelectorAll("[data-list]").forEach(input => {
        input.addEventListener("input", event => {
          planById(event.target.dataset.plan)[event.target.dataset.list] = listFromText(event.target.value);
          autosizeTextarea(event.target);
          updateAndSave();
        });
      });
      document.querySelectorAll("[data-step]").forEach(input => {
        input.addEventListener("input", event => {
          planById(event.target.dataset.plan).prototypeSteps[event.target.dataset.step] = listFromText(event.target.value);
          autosizeTextarea(event.target);
          updateAndSave();
        });
      });
      document.querySelectorAll("[data-synthesis]").forEach(input => {
        input.addEventListener("input", event => {
          state.synthesis[event.target.dataset.synthesis] = listFromText(event.target.value);
          autosizeTextarea(event.target);
          updateAndSave();
        });
      });
      const exportButton = document.getElementById("export-json");
      if (exportButton) exportButton.addEventListener("click", exportJson);
      const importButton = document.getElementById("import-json");
      if (importButton) importButton.addEventListener("click", () => document.getElementById("file-input").click());
      const resetButton = document.getElementById("reset-data");
      if (resetButton) resetButton.addEventListener("click", () => {
        state = clone(initialData);
        renderAll();
        saveState("Reset to embedded plan");
      });
      const clearButton = document.getElementById("clear-save");
      if (clearButton) clearButton.addEventListener("click", () => {
        storageRemove(storageKey);
        state = clone(initialData);
        renderAll();
        document.getElementById("status").textContent = "Saved edits cleared";
      });
    }
    function exportJson() {
      const blob = new Blob([JSON.stringify(state, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "odyssey-plan.json";
      link.click();
      URL.revokeObjectURL(url);
      saveState("Exported JSON");
    }
    function importJson(file) {
      const reader = new FileReader();
      reader.onload = () => {
        try {
          const imported = JSON.parse(reader.result);
          if (!isRenderableState(imported)) throw new Error("Not an Odyssey Planning JSON file");
          state = normalizedState(imported);
          renderAll();
          saveState("Imported JSON");
        } catch (error) {
          document.getElementById("status").textContent = "Import failed: " + error.message;
        }
      };
      reader.readAsText(file);
    }
    function openEditor() {
      document.body.classList.add("editor-open");
      document.getElementById("edit-drawer").setAttribute("aria-hidden", "false");
      renderEditor();
    }
    function closeEditor() {
      document.body.classList.remove("editor-open");
      document.getElementById("edit-drawer").setAttribute("aria-hidden", "true");
    }
    function renderAll() {
      renderAtlas();
      renderEditor();
    }
    document.getElementById("open-editor").addEventListener("click", openEditor);
    document.getElementById("close-editor").addEventListener("click", closeEditor);
    document.getElementById("overlay").addEventListener("click", closeEditor);
    document.getElementById("file-input").addEventListener("change", event => {
      const file = event.target.files[0];
      if (file) importJson(file);
      event.target.value = "";
    });
    window.addEventListener("keydown", event => { if (event.key === "Escape") closeEditor(); });
    window.addEventListener("resize", () => autosizeTextareas(document.getElementById("editor-body")));
    renderAll();
  </script>
</body>
</html>
"""
    return (
        template.replace("__SAFE_TITLE__", safe_title)
        .replace("__STATIC_ATLAS__", static_atlas)
        .replace("__EMBEDDED_JSON__", embedded_json)
    )


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
