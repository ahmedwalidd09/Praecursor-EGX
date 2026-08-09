# Orchestrator Plan — Praecursor-EGX HTML & Pipeline Stability

## Overview
Audit and fix HTML generation logic in `src/praecursor/reporting/dashboard.py` and `src/praecursor/cli/dashboard.py`, and ensure pipeline stability across `tools/regenerate_dashboard.py` and `tools/run_autonomous_pipeline.py`.

## Phases & Milestones

### Phase 0: Technical Survey (Parallel Exploration)
- **Explorer 1**: Survey `src/praecursor/reporting/dashboard.py` and `src/praecursor/cli/dashboard.py` for malformed HTML tags, missing closing tags, unescaped strings, and syntax errors.
- **Explorer 2**: Survey `tools/regenerate_dashboard.py` and `tools/run_autonomous_pipeline.py --date 2026-08-01` to identify crash triggers, unhandled exceptions, missing imports/variables, or runtime errors.
- **Explorer 3**: Survey existing test suites and design an automated HTML validation check for `reports/dashboard.html`.

### Phase 1: Implementation & Iteration
- **Milestone 1: HTML Generation Logic Fixes (R1)**
  - Dispatch Worker to fix malformed HTML elements, missing tags, and broken string injections in dashboard generators while maintaining black/blue/red theme aesthetics.
- **Milestone 2: Pipeline Execution Stability (R2)**
  - Dispatch Worker to fix bugs in `tools/regenerate_dashboard.py` and `tools/run_autonomous_pipeline.py` to ensure clean exit code 0 execution.

### Phase 2: Verification & Forensic Audit
- **Reviewers**: 2 independent reviewers checking HTML structure, pipeline stability, code quality, and low credit usage.
- **Challengers**: 2 independent challengers testing `tools/regenerate_dashboard.py`, `tools/run_autonomous_pipeline.py --date 2026-08-01`, and programmatically validating `reports/dashboard.html`.
- **Auditor**: 1 Forensic Auditor (`teamwork_preview_auditor`) performing integrity audit.
