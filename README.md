# Next Right Thing (NRT)

## Overview

Next Right Thing (NRT) is a professional decision-support application that helps knowledge workers make effective use of short periods of available time. Rather than asking users to decide what to do next, NRT curates and prioritizes professional activities based on their goals, interests, obligations, and current context.

The initial target users are:

1. Psychologists
2. Machine Learning / Software Engineers

## Repository Structure

```text
apps/       Application entry points (web, API, workers)
packages/   Shared libraries and domain code
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

## Development Philosophy

NRT is developed incrementally through small, end-to-end vertical slices.

Every feature should:

* deliver observable user value;
* include appropriate tests;
* update documentation when behavior changes; and
* preserve architectural boundaries.

## Current Status

The project is currently implementing its first end-to-end vertical slice: **Recommendations**.
