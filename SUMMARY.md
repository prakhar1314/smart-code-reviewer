# 100-Word Summary

**Smart Code Reviewer** is a Streamlit prototype that pre-reviews code before it reaches a human, returning a structured JSON verdict: 1–5 scores on readability, structure, and maintainability; three prioritized improvements; one specific positive note; and a ready-for-human-review gate that flags correctness or security blockers. It runs on Gemini 2.0 Flash with schema-constrained output — JSON is guaranteed at decode time, so downstream tooling (GitHub Action, Slack bot, IDE plugin) consumes the review directly without retries. Built in the FDE spirit: ship a working AI workflow into a real team process in under an hour, with evals and observability as the obvious next step.

---

**Word count: ~100**
