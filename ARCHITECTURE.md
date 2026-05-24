# Architecture & Code Walkthrough

Three modules, one external dependency. Whole thing is ~250 lines of code.

```
┌────────────────────────────────────────────────────────────────────┐
│                          User's Browser                             │
│                    (Streamlit-rendered HTML)                        │
└─────────────────────────────┬──────────────────────────────────────┘
                              │  HTTP (Streamlit websocket)
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  app.py — Streamlit UI                                              │
│  ─────────────────────                                              │
│  • Sidebar: API key, language hint, sample picker                   │
│  • Main: code textarea + Review button                              │
│  • Result panel: scores, improvements, positive note, raw JSON      │
│  • State: per-session env vars, no persistence                      │
└─────────────────────────────┬──────────────────────────────────────┘
                              │  review_code(code, language_hint)
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  reviewer.py — Business logic                                       │
│  ──────────────────────────                                         │
│  • Loads system_prompt.md (rubric + schema + tone)                  │
│  • Builds GenerateContentConfig with response_schema                │
│  • Calls Gemini with up-to-3 retries on 503/429                     │
│  • Parses JSON, returns dict (or error dict on failure)             │
└─────────────────────────────┬──────────────────────────────────────┘
                              │  google-genai SDK
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  Google Generative Language API                                     │
│  ───────────────────────────────                                    │
│  model: gemini-2.5-flash                                            │
│  constraint: response_mime_type=application/json                    │
│              response_schema=RESPONSE_SCHEMA                        │
│  → JSON is structurally guaranteed at decode time                   │
└────────────────────────────────────────────────────────────────────┘
```

## Module by module

### `prompts/system_prompt.md` — The IP

This is the most important file. Everything else is plumbing. It defines:

- **Role**: "senior staff engineer, polyglot, runs before human review"
- **Three dimensions**: readability, structure, maintainability — each scored 1–5
- **Rubric anchors** for each score (5 = production-ready, 1 = reject) — without anchors, models cluster at 3 ("everything looks fine")
- **Output schema** (also enforced by `response_schema` in code, but stating it in the prompt helps the model self-correct)
- **Rules**: exactly 3 improvements, specific positive note (no generic praise), ready-for-review gate only blocks on correctness/security
- **Tone**: direct, kind, technical — no hedging

The prompt is loaded fresh from disk on every call so it can be hot-swapped without restarting the app — useful for iterating on the rubric in production.

### `reviewer.py` — The LLM client

```python
def review_code(code, language_hint=None) -> dict:
    # 1. Get API key
    # 2. Initialize Gemini client
    # 3. Load system prompt from disk
    # 4. Build user message (code + optional language hint)
    # 5. Configure: response_schema, temperature=0.2, max_tokens=4096
    # 6. Try up to 3 times, exponential backoff on 503/429
    # 7. Parse JSON → return dict
```

**Three production patterns worth noting:**

1. **Schema-constrained output**: `response_schema=RESPONSE_SCHEMA` forces Gemini to emit JSON that matches the schema *at decode time*. No "please return JSON" in the prompt — the model is structurally constrained. This eliminates the most common LLM failure mode in production (malformed JSON → downstream crash).

2. **Temperature 0.2**: Reviews should be deterministic-ish. Same code on Tuesday and Wednesday should not get different scores. Low temperature trades creativity for consistency, which is what you want from a reviewer.

3. **Retry only on transient errors**: Loop retries on 503 (overloaded) and 429 (rate limit) with exponential backoff (1s, 2s, 4s), but fails fast on actual bugs (auth, malformed request). Distinguishing transient vs. terminal errors is a hallmark of production code.

### `app.py` — The UI

Pure Streamlit, ~130 lines. Three responsibilities:

1. **Settings sidebar**: API key (password input, session-only), language hint dropdown, sample picker
2. **Code input pane**: textarea, "Review code" button
3. **Result pane**: summary line → color-coded score badges → ready/blocked banner → expandable improvements with priority emoji + category + fix + code example → positive note → collapsed raw JSON

The presentation is intentional: humans glance at the badges to decide whether to bother reading further, then dive into the high-priority improvement if scores are low. The raw JSON is there so a power user (or downstream tool) can grab the structured data.

### `samples/` and `sample_output.json`

Three demo snippets across Python / TypeScript+React / Go and the cached review outputs. Lets a reviewer who skims the repo see what the model actually produces without running anything.

---

## Sequence diagrams

### 1. Happy path — single review

```mermaid
sequenceDiagram
    actor User
    participant UI as app.py (Streamlit)
    participant R as reviewer.py
    participant FS as prompts/system_prompt.md
    participant G as Gemini 2.5 Flash

    User->>UI: paste code, click "Review code"
    UI->>UI: validate (API key set? code non-empty?)
    UI->>R: review_code(code, language_hint)

    R->>R: read API key from env
    R->>FS: load_system_prompt()
    FS-->>R: system prompt text
    R->>R: build GenerateContentConfig<br/>(schema, temp=0.2, max=4096)

    R->>G: generate_content(model, contents, config)
    Note over G: constrained decode<br/>output must match RESPONSE_SCHEMA
    G-->>R: response.text (valid JSON)

    R->>R: json.loads(response.text)
    R-->>UI: dict (scores, improvements, positive, …)

    UI->>UI: render badges, expanders, JSON
    UI-->>User: structured review (~2s)
```

### 2. Retry path — Gemini overloaded

```mermaid
sequenceDiagram
    participant R as reviewer.py
    participant G as Gemini API

    R->>G: generate_content (attempt 1)
    G-->>R: 503 UNAVAILABLE
    Note over R: matches retry condition<br/>sleep(2^0 = 1s)

    R->>G: generate_content (attempt 2)
    G-->>R: 429 RATE LIMITED
    Note over R: matches retry condition<br/>sleep(2^1 = 2s)

    R->>G: generate_content (attempt 3)
    G-->>R: 200 OK + JSON
    Note over R: success — parse and return
```

Failure modes that bypass retry: `401` (bad API key), `400` (malformed request), `JSONDecodeError` (model returned non-JSON despite schema — rare, returns an `error` dict immediately so the UI can surface the raw output).

### 3. Production extension — GitHub Action wiring

This isn't built yet, but it's the obvious next step and reviewers will ask. The schema-first design is what makes it cheap to add:

```mermaid
sequenceDiagram
    actor Dev
    participant GH as GitHub
    participant CI as GitHub Action
    participant R as reviewer.py
    participant G as Gemini
    participant PR as PR Comment Bot

    Dev->>GH: push commit to PR branch
    GH->>CI: trigger workflow on pull_request
    CI->>CI: extract diff (changed files)
    loop for each changed file
        CI->>R: review_code(file_contents, lang)
        R->>G: generate_content
        G-->>R: JSON review
        R-->>CI: dict
    end
    CI->>CI: aggregate reviews,<br/>collect blockers
    CI->>PR: post sticky comment with summary
    PR-->>Dev: notification
    alt has blockers
        CI->>GH: set check status = failure
    else clean
        CI->>GH: set check status = success
    end
```

---

## Design trade-offs (the parts a reviewer will push on)

| Trade-off | Choice | Why |
|---|---|---|
| Schema enforcement: prompt-only vs. response_schema | `response_schema` | Eliminates parse errors at decode time, not "ask nicely" |
| Model: Flash vs. Pro | Flash | Per-PR latency matters; 4–5x faster, 10x cheaper, quality is sufficient for style review |
| Temperature: 0 vs. 0.2 | 0.2 | Pure-0 can collapse to template-y outputs; 0.2 keeps tiny variation in phrasing without scoring drift |
| Reviewer-as-prompt vs. reviewer-as-agent | Prompt | One-shot review needs no tool calls or memory; agent overhead would add latency without value |
| State: session vs. persistent | Session-only | Reviews are stateless. No DB needed. Move to persistence only when you want history/eval. |
| Sync vs. streaming | Sync | UI is already fast (~2s). Streaming would add complexity for negligible UX gain. |

## What I'd build next (in priority order)

1. **Eval harness**: 50-snippet golden set with expected score ranges. Run it in CI on every prompt change to catch regressions. Without this, every prompt edit is a gamble.
2. **Diff-mode review**: take a `git diff` instead of a full file — closer to real PR review, and avoids re-reviewing unchanged code.
3. **GitHub Action**: post the review as a sticky PR comment, set check status based on blockers (diagram above).
4. **Repo-aware reviews**: feed the team's style guide and past accepted/rejected reviews via RAG so the reviewer matches local conventions instead of generic best-practice.
5. **Multi-model ensemble**: route security-flagged snippets to Gemini Pro (or Claude Opus) for a second opinion before blocking a PR.
