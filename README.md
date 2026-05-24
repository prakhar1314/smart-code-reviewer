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

## Future work (would build next in a real engagement)

- **Eval harness**: golden set of 50 snippets with expected score ranges; CI gate on prompt changes.
- **Diff-mode review**: take a git patch instead of a full snippet — closer to real PR review.
- **GitHub Action**: post the review as a PR comment with sticky updates.
- **Repo-aware reviews**: feed style guide / past review history via RAG so the reviewer matches team conventions.
- **Multi-model ensemble**: route security-flagged snippets to a stronger model (Gemini Pro / Claude Opus) for a second opinion.
