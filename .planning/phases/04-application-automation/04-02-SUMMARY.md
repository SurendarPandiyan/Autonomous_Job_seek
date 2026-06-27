---
phase: "04"
plan: "02"
subsystem: applications
tags: [anthropic, llm, resume-tailoring, tenacity, config]
dependency_graph:
  requires: []
  provides: [anthropic-sdk, anthropic_api_key-config, tailor_resume-fn, extract_resume_text-fn]
  affects: [04-03]
tech_stack:
  added: [anthropic==0.112.0, docstring-parser==0.18.0]
  patterns: [tenacity-retry, structlog, pydantic-settings]
key_files:
  created:
    - src/jobplatform/applications/service.py
  modified:
    - pyproject.toml
    - uv.lock
    - src/jobplatform/config.py
decisions:
  - "Model ID is claude-haiku-4-5 (not claude-3-5-haiku-20241022 which is retired)"
  - "extract_resume_text returns empty string (not raise) on missing parsed_data to keep Celery tasks resilient"
  - "AsyncAnthropic client instantiated per-call to pick up api_key from settings at call time"
metrics:
  duration: "~5 minutes"
  completed: "2026-06-27"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 04 Plan 02: Anthropic SDK + Resume Tailoring Service Summary

## One-liner

Installed anthropic==0.112.0, added anthropic_api_key to Settings, and created service.py with TAILOR_PROMPT constant, tenacity-retried tailor_resume (claude-haiku-4-5), and extract_resume_text.

## What Was Built

### Task 1: Add anthropic dependency and settings key
- Ran `uv add "anthropic>=0.112.0"` — installed anthropic==0.112.0
- Added `anthropic_api_key: str = ""` to Settings class in config.py after openai_api_key
- Commits: fdca7fb

### Task 2: Create service.py with LLM-only functions
- Created `src/jobplatform/applications/service.py` with:
  - `TAILOR_PROMPT` — module-level string constant for resume tailoring prompt
  - `tailor_resume(resume_text, job_description) -> str` — async, @retry with tenacity (wait_exponential multiplier=1 min=2 max=60, stop_after_attempt(5), retry_if_exception_type(RateLimitError), reraise=True), calls claude-haiku-4-5
  - `extract_resume_text(resume: Resume) -> str` — returns str(resume.parsed_data) or "" with structlog warning if None
  - Patch target comment: `jobplatform.applications.service.AsyncAnthropic`
- Commits: 18b6f25

## Verification Results

- `import anthropic; print(anthropic.__version__)` → `0.112.0`
- `from jobplatform.config import settings; settings.anthropic_api_key` → `''`
- `from jobplatform.applications.service import tailor_resume, extract_resume_text, TAILOR_PROMPT` → OK
- `uv run pytest tests/ -q --tb=short` → 59 passed, 3 warnings

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None. service.py functions are real implementations. No hardcoded placeholders.

## Self-Check: PASSED

- [x] `from jobplatform.applications.service import tailor_resume, extract_resume_text, TAILOR_PROMPT` → OK
- [x] `hasattr(settings, 'anthropic_api_key')` → OK
- [x] `import anthropic; print(anthropic.__version__)` → 0.112.0
- [x] 59 tests passed
