# Life Design Frameworks

Life Design Frameworks is a Codex skill for turning reflective book and article exercises into private, portable artifacts people can actually revisit.

The first supported exercise is Odyssey Planning from *Designing Your Life*. The skill guides someone through three possible five-year futures, captures their answers as structured JSON, and renders a polished self-contained HTML artifact called a Future Atlas.

## Why This Exists

Many reflective exercises are powerful in the moment and then disappear into a notebook, PDF, chat thread, or forgotten document. That makes them hard to update, compare, share, or build on later.

This skill is meant to make those exercises more durable. It gives people a way to turn messy thinking into a living artifact they can keep locally, edit over time, and use as a source of self-knowledge.

The goal is not to pick the one correct life path. It is to make multiple plausible futures concrete enough to discuss, test, and revise.

## What It Produces

For Odyssey Planning, the output is a Future Atlas:

- three distinct five-year futures
- year `0` through `5` route-style timelines
- a six-word title and short story for each future
- comparison bars for resources, like-it, confidence, and coherence
- questions each path raises
- people to talk to, small experiments, and reflection prompts
- a synthesis of common threads, tensions, and next experiments

The generated HTML is self-contained and works without a server or network connection. It includes the full atlas as static HTML first, then adds an optional editor drawer for local edits, JSON import/export, reset, and print.

## Install In Codex

Install the skill from this repo:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo nadiem99/life-design-frameworks \
  --path .
```

Restart Codex after installation so the skill is picked up.

Then ask Codex something like:

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

## Validate

Run:

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
python3 scripts/test_render_odyssey.py
```

