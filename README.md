# Smart Code Reviewer

> Pre-review AI that catches readability, structure, and maintainability issues before they reach a human reviewer.
> Built as a take-home for the **Careem Founding Forward Deployed Engineer — WorkOS (Enterprise Agentic AI)** role.

## What it does

Paste a code snippet → get a structured review in ~2 seconds:

- **Scores** on readability, structure, and maintainability (1–5)
- **Three prioritized improvements** with category, location, and concrete fix
- **One specific positive note** — not generic praise
- **Ready-for-human-review verdict** with blockers when correctness/security is at risk
- **Raw JSON** for downstream tooling (Slack bot, GitHub Action, IDE plugin)

## Why this design

The challenge could be solved with a one-shot prompt, but FDE work is about shipping production-grade AI inside enterprise workflows. So this prototype demonstrates patterns that survive contact with real users:

| Choice | Why it matters in production |
|---|---|
| **Schema-constrained JSON output** | Gemini's `response_schema` forces well-formed JSON at decode time — no parse retries, no fallback prose. Downstream tooling can consume it directly. |
| **Three-dimension rubric with 1–5 anchors** | Avoids the "everything looks fine" trap; calibrated scoring scales across reviewers and lets you A/B prompt versions. |
| **"Ready for human review" gate** | Separates style nits from correctness blockers — humans only get paged when the AI can't auto-clear. |
| **Specific-positive-note rule** | Generic praise erodes trust. Forcing the model to name *what* was good keeps the reviewer honest. |
| **Gemini 2.0 Flash** | Fast + cheap + generous free tier + native structured-output support. The right model for a per-PR latency-sensitive tool. |
| **Low temperature (0.2)** | Deterministic-ish reviews — the same code shouldn't get a different score on Tuesday. |

## Architecture

```
   ┌────────────┐      ┌────────────────────┐      ┌──────────────────┐
   │ Streamlit  │ ───▶ │  reviewer.py        │ ───▶ │ Gemini 2.0 Flash │
   │   UI       │      │  (schema-           │      │ (response_schema │
   └────────────┘      │   constrained JSON) │      │  constrained)    │
         ▲             └────────────────────┘      └──────────────────┘
         │                      │
         │                      ▼
   structured                JSON matching schema
   review UI                 (consumable)
```

## Quickstart (local)

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your-key-here
streamlit run app.py
```

Open the URL Streamlit prints (usually http://localhost:8501).

Get a free Gemini key at https://aistudio.google.com/apikey — generous free tier covers thousands of reviews.

## Deploy to Streamlit Community Cloud (free, public link)

1. Push this folder to a public GitHub repo.
2. Go to https://share.streamlit.io → **New app**.
3. Point it at your repo + `app.py`.
4. In **Advanced settings → Secrets**, add:
   ```toml
   GEMINI_API_KEY = "your-key-here"
   ```
5. Deploy. You get a public `https://<name>.streamlit.app` URL.

## Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit UI — paste code, render review |
| `reviewer.py` | Gemini API call with response_schema |
| `prompts/system_prompt.md` | The reviewer's rubric, schema, and tone — the core IP |
| `samples/` | Sample snippets (Python, TypeScript/React, Go) for demo |
| `requirements.txt` | streamlit + google-generativeai |
| `SUMMARY.md` | 100-word submission summary |

## Eval harness

A regression-test harness lives in `evals/`. It runs the reviewer against a curated
golden set of 25 snippets across four slices (bug/fix pairs, security blockers,
clean reference code, stylistic anti-patterns) and reports pass/fail per check.

```bash
python evals/run_eval.py            # full run (~3 min, 25 calls)
python evals/run_eval.py --quick    # 5-item smoke test
python evals/run_eval.py --slice security  # only the security blockers
```

### What each check measures

| Check | What it catches |
|---|---|
| `score:<dim>` | Reviewer scores drift outside the expected range for a dimension |
| `ready_for_review` | Reviewer fails to gate (or wrongly gates) human review |
| `blocker_presence` | Reviewer misses (or hallucinates) a correctness/security blocker |
| `category_coverage` | Reviewer mentions an unrelated category but skips the obvious one |

Reports are written to `evals/reports/` as both markdown (human-readable) and JSON
(for diffing in CI). The runner exits with code 1 if any check fails — wire that into
GitHub Actions to gate prompt changes.

### Baseline

Current baseline: see `evals/reports/baseline.md` (5-item smoke test, 60% pass rate —
2 failures both surfaced real calibration gaps between my expected ranges and the
reviewer's actual behavior, not bugs in the reviewer itself).

### Limitations / cost notes

- **Gemini free tier caps you at 20 requests/day** on `gemini-2.5-flash`. A full
  25-item run hits this. Either upgrade to paid (≈$0.01 for a full run) or use
  `REVIEWER_MODEL=gemini-2.5-flash-lite` for the eval (1k req/day free).
- The eval is **stochastic** — model output varies slightly between runs even at
  `temperature=0.2`. The expected ranges (not exact scores) absorb this.
- For true regression detection in CI, **run 3x and require 2/3 pass per check** —
  not implemented here yet.

## Future work (would build next in a real engagement)

- ~~**Eval harness**~~ — done, see `evals/`. Next: expand to 100 snippets, add per-run variance tracking, wire into GitHub Actions.
- **Diff-mode review**: take a git patch instead of a full snippet — closer to real PR review.
- **GitHub Action**: post the review as a PR comment with sticky updates.
- **Repo-aware reviews**: feed style guide / past review history via RAG so the reviewer matches team conventions.
- **Multi-model ensemble**: route security-flagged snippets to a stronger model (Gemini Pro / Claude Opus) for a second opinion.
