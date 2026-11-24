# Next Right Thing (NRT)

## Overview

Next Right Thing (NRT) is a professional decision-support application that helps knowledge workers make effective use of short periods of available time. Rather than asking users to decide what to do next, NRT curates and prioritizes professional activities based on their goals, interests, obligations, and current context.

The initial target users are:

1. Psychologists
2. Machine Learning / Software Engineers

## Repository Structure

```text
apps/web/   Next.js frontend
backend/    Python APIs, services, ingestion workers, migrations and tests
packages/   Shared/UI package placeholders
infra/      Infrastructure-as-code (CloudFormation)
docs/       Product, architecture, and feature documentation
```

## Key Documentation

Read these documents before making significant changes:

1. `docs/vision.md` — Product vision and design principles
2. `docs/domain-model.md` — Core business concepts
3. `docs/architecture.md` — System architecture
4. `ENGINEERING.md` — Engineering workflow
5. `AGENTS.md` — Guidance for AI coding agents

For current work, verification evidence, and planning continuity, start with
[Project status](docs/planning/PROJECT_STATUS.md), then the
[decision log](docs/planning/DECISIONS.md) and
[feature backlog](docs/features/backlog.md).

## Development Philosophy

NRT is developed incrementally through small, end-to-end vertical slices.

Every feature should:

* deliver observable user value;
* include appropriate tests;
* update documentation when behavior changes; and
* preserve architectural boundaries.

## Current Status

The committed application includes Goals, RSS Content Sources and fetch health,
Content Items, recommendations and disposition/history controls, plus podcast
ingestion and external listening. Semantic relevance is deployed but not yet
operational due to AWS throttling, per the user on 2026-11-20. Content Items
pagination is merged on main and deployed per the user on
2026-11-24. Compact navigation and adjustable page size are committed as
`555ca6a` (deployment unverified). Synchronized top/bottom controls and numbered
visited/next-page links are included in the current follow-up (deployment unverified).
Obsolete worktrees/branches have been
archived and retired; recovery and remaining validation evidence live in the
project status snapshot.
