- Read vision.md, domain-model.md, and architecture.md before making significant changes.
- Prefer modifying existing abstractions over introducing new ones.
- Create an ADR for architectural changes.
- Keep domain terminology consistent with domain-model.md.
- Update documentation when behavior changes.
- Do not introduce new dependencies without justification.
- Favor simple deterministic implementations over AI-based solutions unless the feature explicitly requires them.
- When in doubt, **ask rather than invent**.
- Favor evolving existing abstractions over introducing new ones.

When making implementation decisions, follow this precedence order:

1. vision.md
2. domain-model.md
3. architecture.md
4. Feature specification (docs/features/...)
5. ENGINEERING.md
6. Existing code

## Standard Implementation loop

- Read the relevant design documents.
- Produce an implementation plan and identify ambiguities.
- Wait for approval before major architectural changes.
- Implement the smallest coherent task.
- Run tests and fix failures.
- Update documentation.
- Summarize what changed and what remains.

## Planning continuity

- Planning sessions start with `docs/planning/PROJECT_STATUS.md` and
  `docs/planning/DECISIONS.md`, then inspect Git status and registered worktrees.
- Use `docs/features/backlog.md` for candidate slices; feature specifications and
  test plans stay under `docs/features/`, and architectural decisions in `docs/adr/`.
- Update the status snapshot after substantial planning/review. Record the date,
  commit, evidence and uncertainty; distinguish implemented, committed/integrated,
  deployed and manually validated work. Index material decisions in the log.
- Planning work does not authorize feature implementation. Do not commit, merge,
  push or deploy without user approval, or alter another session's work without
  approval. Coordinate ownership before changing shared files or worktrees.

## AWS CLI

Do not execute AWS CLI (`aws`) commands from Codex.

The user's AWS SSO credentials work in their normal PowerShell environment, but AWS CLI calls from Codex fail TLS certificate validation.

If an AWS CLI operation is required:
1. Do not attempt to run it.
2. Provide the exact command for the user to run in PowerShell.
3. State what output/result you need back.
4. Continue with other work that does not require the AWS CLI.
