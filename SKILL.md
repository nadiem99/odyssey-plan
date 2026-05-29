---
name: life-design-frameworks
description: Guide reflective life-design frameworks and reading exercises into private, portable artifacts. Use when the user wants to work through Odyssey Planning, Designing Your Life exercises, career/life reflection frameworks, or book/article exercises and generate structured JSON plus a self-contained HTML visualization they can save and revisit.
---

# Life Design Frameworks

## Overview

Use this skill to coach a user through a reflective exercise, capture their answers as structured data, and generate a private artifact they can keep locally. Start with Odyssey Planning; add future exercises by creating new references and renderer templates without changing the overall workflow.

## Workflow

1. Identify the exercise. For Odyssey Planning, read `references/odyssey-planning.md` before guiding the user.
2. Orient the user briefly: explain the exercise goal, the expected output, and that answers remain local unless they choose to share files.
3. Collect answers conversationally. Ask for one small set of answers at a time; do not demand a full schema up front.
4. Coach lightly. Reflect patterns back, ask one useful follow-up when an answer is thin, and help the user name concrete next experiments.
5. Build a JSON object matching the exercise schema in the reference file.
6. Run the renderer script to generate both JSON and HTML:

```bash
python3 scripts/render_odyssey.py input.json --out ./out
```

7. Open or inspect the generated HTML when possible. Verify it renders, autosaves edits in localStorage, and exports/imports JSON.
8. Return the generated file paths and a short note on how the user can continue the exercise.

## Odyssey Planning Rules

- Create three futures: expected path, alternative path, and wildcard path.
- Capture a six-word title for each plan, but do not block progress if the user needs a draft title first.
- Capture years `0` through `5` as milestones or scenes.
- Capture four gauges from `0` to `100`: resources, like-it, confidence, and coherence.
- Capture questions raised and prototype steps: people to talk to, small experiments, and reflection prompts.
- Synthesize common threads, tensions, and likely next experiments across all three plans.

## Privacy And Portability

- Prefer local files over cloud persistence.
- Generate a portable JSON file for reloading or editing later.
- Generate a self-contained HTML file with embedded data and no network dependencies.
- Do not include copyrighted worksheet visuals, third-party logos, or long verbatim source passages in generated artifacts.

## Resources

- `references/odyssey-planning.md`: exercise guidance, schema, and coaching prompts.
- `scripts/render_odyssey.py`: validates Odyssey JSON and renders `odyssey-plan.json` plus `odyssey-plan.html`.
- `scripts/sample_odyssey.json`: sample data for renderer testing or demos.
- `scripts/test_render_odyssey.py`: unit tests for validation and artifact generation.
