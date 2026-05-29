# Odyssey Planning Reference

Source inspiration: Designing Your Life's Odyssey Planning exercise, including the public article at `https://designingyour.life/insights/the-magic-of-odysseys-prototyping-your-future-with-designing-your-life/`. Use original wording in generated artifacts; do not reproduce the worksheet's logo, layout, or branded visuals.

## Exercise Intent

Help the user prototype three meaningfully different five-year futures so they stop treating their next path as a single correct answer. The output should make each life concrete enough to discuss, test, and revise.

## Three Plans

- `life-1` / `expected_path`: the path the user is already on if they keep going.
- `life-2` / `alternative_path`: what they would do if the current path disappeared or became unavailable.
- `life-3` / `wildcard`: what they would try if money, status, and outside expectations were less binding.

## Guided Conversation

Use a coach-like tone. Keep the user moving, but leave space for ambiguity.

1. Ask for the user's current context and the decision horizon.
2. For each life, ask for a rough story first, then years `0` through `5`.
3. Ask for the four gauges only after the story exists.
4. Ask what questions the plan raises.
5. Ask for prototypes: people, experiments, and reflection prompts.
6. After all three lives, synthesize patterns across the set.

Useful prompts:

- "What would make this life feel real twelve months from now?"
- "What are you assuming would need to be true?"
- "Which part gives you energy, and which part feels borrowed?"
- "Who is already living a version of this?"
- "What could you test in a weekend or a two-week sprint?"
- "What would you need to learn before taking this seriously?"

## JSON Schema

The renderer expects this shape:

```json
{
  "schemaVersion": "1.0",
  "exercise": "odyssey-planning",
  "createdAt": "2026-05-28T00:00:00Z",
  "participant": {
    "name": "Optional name",
    "context": "Optional situation or decision"
  },
  "plans": [
    {
      "id": "life-1",
      "promptType": "expected_path",
      "titleSixWords": "A six word title goes here",
      "summary": "A short description of this possible life.",
      "timeline": [
        { "year": 0, "milestone": "Current moment or starting scene." },
        { "year": 1, "milestone": "Year one scene." },
        { "year": 2, "milestone": "Year two scene." },
        { "year": 3, "milestone": "Year three scene." },
        { "year": 4, "milestone": "Year four scene." },
        { "year": 5, "milestone": "Year five scene." }
      ],
      "gauges": {
        "resources": 50,
        "likeIt": 50,
        "confidence": 50,
        "coherence": 50
      },
      "questionsRaised": [
        "What would I need to learn?"
      ],
      "prototypeSteps": {
        "people": ["Talk to someone living this path."],
        "experiments": ["Try a small test of this path."],
        "reflections": ["Notice what gives or drains energy."]
      }
    }
  ],
  "synthesis": {
    "commonThreads": ["Themes that appear in multiple plans."],
    "tensions": ["Tradeoffs or unresolved questions."],
    "nextExperiments": ["Concrete prototypes to run next."],
    "reflectionPrompts": ["Questions to revisit later."]
  }
}
```

## Validation Rules

- `exercise` must be `odyssey-planning`.
- `plans` must contain exactly `life-1`, `life-2`, and `life-3`.
- Each plan must have a non-empty `titleSixWords`.
- `promptType` must match the plan id.
- `timeline` must include each year `0`, `1`, `2`, `3`, `4`, and `5` exactly once.
- Gauge values must be numbers from `0` to `100`.
- `questionsRaised`, `prototypeSteps.people`, `prototypeSteps.experiments`, and `prototypeSteps.reflections` should be arrays of strings.

## Artifact Expectations

The generated HTML should:

- Render without network access.
- Embed the initial JSON.
- Save edits to localStorage.
- Offer JSON export and import.
- Show all three plans, a year-by-year timeline, four gauges, questions, prototype steps, and synthesis.
