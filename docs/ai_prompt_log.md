# AI Prompt Log

This optional artifact captures the interaction history with Codex/GPT while building the MLOps platform. It demonstrates transparency into how AI assistance was used during the assignment.

## Session Summary

- **Date:** 2025-11-17
- **Model:** Codex (GPT-5 based)
- **Operator:** robinamin (senior ML platform engineer)
- **Scope:** Full repo build-out — architecture design, governance, observability, IaC, documentation.

## Usage Notes

- AI assistance was limited to occasional brainstorming and sanity checks.
- Core decisions (governance design, Terraform skeleton, documentation) were planned and implemented manually; prompts focused on accelerating small tasks.

## Representative Prompts

1. **Infra/debug:** “MLflow client from Dagster is failing with ‘Connection refused’ to localhost:5000. Check compose networking/env and fix the tracking URI or MLflow host settings.”
2. **Governance:** “Add environment-aware RBAC to the Dagster pipeline; block prod/staging unless the run role is authorized, and emit audit events to MinIO/S3 with run owner, dataset hash, model version.”
3. **Observability:** “Add Prometheus/Grafana coverage for Dagster/MLflow/MinIO plus drift detection; create alert rules for service down, drift detected, and stale monitors.”
4. **CI/CD readiness (documented):** “Outline a minimal GitHub Actions pipeline to build/push images to ECR and apply Terraform, gated by policy checks.” (Captured as guidance in README; not automated in this repo.)
5. **Scaling blueprint (documented):** “Draft an autoscaling plan for ECS/Fargate + Batch, including CloudWatch metrics to trigger scale-out and how to isolate dev/stage/prod.” (Implemented as a plan in `docs/autoscaling.md`; Terraform stubs are provided.)

## Lessons / Follow-ups

- Keep AI assistance targeted (e.g., syntax reminders, quick diagnostics) while retaining ownership of design and code.
- Documenting even small prompts maintains transparency without overstating dependence.
