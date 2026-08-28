# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repository root.
- **`docs/adr/`** for ADRs relevant to the area being changed.
- Continue to follow the existing sources-of-truth rules in `AGENTS.md`, including `docs/STATUS.md`, `docs/KNOWN_ISSUES.md`, and relevant project documentation.

If `CONTEXT.md` or `docs/adr/` does not exist, proceed silently. Do not require either file to be created before work begins. Domain-modeling skills create them lazily when domain terms or durable decisions are resolved.

## File structure

This repository uses a single-context layout:

```text
/
├── CONTEXT.md
├── docs/
│   └── adr/
├── backend/
└── frontend/
```

## Use the glossary's vocabulary

When output names a domain concept—in an issue title, refactor proposal, hypothesis, or test name—use the term defined in `CONTEXT.md`. Do not drift to synonyms that the glossary explicitly avoids.

If a needed concept is absent, reconsider whether the new term matches the project. If it represents a genuine gap, note it for domain modeling.

## Flag ADR conflicts

If proposed work contradicts an existing ADR, surface the conflict explicitly rather than silently overriding it.
