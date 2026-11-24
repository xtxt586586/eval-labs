# Judge Prompt Comparison

This isolated experiment compares two actual prompt configurations through Eval Labs' `numeric` metric and `OpenAIJudgeClient`. It does not touch the project database or replace the existing demo reports.

## Data and labels

`samples.json` contains five synthetic RAG examples, proposed reference scores, and scoring rationales. They are **illustrative rubric labels, not human-annotated labels**. Human calibration evidence remains incomplete until a person reviews and records these scores.

The score scale is continuous from 0 to 1. A score of 1 means all required facts are correct and supported by retrieved evidence; 0.75 means correct with a minor omission; 0.5 means materially partial; 0 means a core contradiction or unsupported assertion. The labels are diagnostic targets only.

## Reproduction

From the repository root, run the no-cost check first:

```powershell
.\.venv\Scripts\python.exe demo\experiments\2026-11-24-judge-prompt-comparison\run_comparison.py
```

After explicit cost approval, execute the external Judge comparison:

```powershell
.\.venv\Scripts\python.exe demo\experiments\2026-11-24-judge-prompt-comparison\run_comparison.py --execute --repeats 2
```

The run uses the existing `backend/.env` configuration but never prints the API key. Five samples, two prompt variants, and two repeats plan 20 logical scoring calls. The SDK can retry requests, and JSON-mode fallback can send an additional request. The resulting `latest_run.json` keeps each score, Judge reason, reference score, elapsed time, SDK create calls visible to the wrapper, token usage, hashes, per-sample MAE, and within-sample repeat variance/range. SDK-internal HTTP retry counts are not exposed. It excludes raw sample text from the result artifact; the experiment inputs remain in this directory.

The current DeepSeek price page lists `deepseek-flash` and `deepseek-v4-pro`, but does not list the configured legacy alias `deepseek-chat`. The report calculates cost scenarios using observed token usage at the published cache-miss rates and explicitly marks the alias-to-model billing route as unverified. Before execution, the conservative planning estimate is about US$0.121 for 20 calls, assuming 1,500 input tokens and the configured 1,024 output-token limit per call at the listed V4 Pro peak rates. This is a budget estimate, not a confirmed quote for the configured alias.

## Metric definitions

For each fully successful sample, the script calculates the mean of its repeated Judge scores, then its absolute error against the proposed reference score. Variant MAE is the arithmetic mean of those per-sample absolute errors over fully successful samples. A sample with any failed repeat is counted as failed and omitted from that MAE denominator, matching the calibration API's complete-sample behavior. Repeat stability is population variance and range within each same sample; the aggregate is the arithmetic mean across complete samples. It does not use variance across different samples as a stability measure.

The comparison hashes the canonical dataset JSON, each prompt, and the model/metric configuration. The model snapshot omits secrets. This experiment is diagnostic only, is based on five proposed labels, and is not a production accuracy claim or CI release threshold.
