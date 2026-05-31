# Odyssey Plan Skill

Odyssey Plan Skill is a Codex skill for guiding someone through the Odyssey Plan exercise from the book Designing Your Life and turning their answers into a private, portable Future Atlas.

Odyssey Planning is useful because it breaks the illusion that there is one correct path to find. Instead, it asks you to make three meaningfully different five-year futures concrete enough to compare, discuss, test, and revise.

## Why This Exists

Most reflective exercises feel powerful while you are doing them and then disappear into a notebook, PDF, chat thread, or forgotten document. That makes the work hard to revisit. It also makes it harder to notice patterns across time.

This skill is meant to make Odyssey Planning durable. Codex coaches the conversation, captures the answers as structured JSON, and creates a polished HTML artifact that someone can keep locally, share with trusted people, print, and edit later.

The point is not to choose the perfect life immediately. The point is to turn possible futures into something visible enough to prototype.

## What It Produces

The output is a self-contained Future Atlas HTML file plus a portable JSON file.

The Future Atlas includes:

- three distinct five-year futures
- year `0` through `5` route-style timelines
- a six-word title and short story for each future
- comparison bars for resources, like-it, confidence, and coherence
- questions each path raises
- people to talk to, small experiments, and reflection prompts
- a synthesis of common threads, tensions, and next experiments

The HTML file works without a server or network connection. It includes the full atlas as static HTML first, then adds an optional editor drawer for local edits, JSON import/export, reset, and print.

## Install In Codex

Install the skill from this repo:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo nadiem99/life-design-frameworks \
  --path .
```

Restart Codex after installation so the skill is picked up.

Then ask Codex:

```text
Guide me through Odyssey Planning and generate a Future Atlas HTML artifact.
```

## Use Locally

You can also render an Odyssey JSON file directly:

```bash
python3 scripts/render_odyssey.py scripts/sample_odyssey.json --out ./out
```

This writes:

- `odyssey-plan.json`
- `odyssey-plan.html`

Open the HTML file in a browser to view, print, edit locally, or export the updated JSON.

## Privacy

The skill is local-first. It does not require accounts, a backend, or cloud storage. The generated HTML stores edits in the browser when available and always lets you export a portable JSON copy.

Do not include private generated outputs in the repo. The `out/` directory is ignored by git.

## Validation

Run:

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py /path/to/this/repo
python3 scripts/test_render_odyssey.py
```

