# Eval Report — 2026-05-24T18:37:55

**Model:** `gemini-2.5-flash`  
**Golden set:** 5 items  
**Result:** 3/5 pass (**60.0%**) · 2 fail

## Pass rate by slice

| Slice | Pass | Fail | Total | Rate |
|---|---:|---:|---:|---:|
| `bug-fix` | 3 | 2 | 5 | 60.0% |

## Score distribution (across all items)

| Dimension | n | mean | stdev | min | max |
|---|---:|---:|---:|---:|---:|
| readability | 5 | 3.6 | 0.89 | 3 | 5 |
| structure | 5 | 4 | 0.71 | 3 | 5 |
| maintainability | 5 | 3 | 1.41 | 2 | 5 |

## ❌ Failed items (2)

### `bug-001-mutable-default-arg` — slice: `bug-fix`
_Mutable default argument — classic Python anti-pattern._

- **ready_for_review** — expected `True`, got `False`

### `bug-001-mutable-default-arg-fix` — slice: `bug-fix`
- **score:readability** — expected `4–5`, got `3`

## ✅ Passed items (3)

<details><summary>Click to expand</summary>

- `bug-002-bare-except` — R=3 · S=4 · M=2
- `bug-002-bare-except-fix` — R=5 · S=5 · M=5
- `bug-003-resource-leak` — R=4 · S=4 · M=2

</details>
