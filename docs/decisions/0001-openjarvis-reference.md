# ADR 0001: keep the native runtime; use OpenJarvis as a reference

Date: 2026-11-19. Status: accepted for local engineering; no infrastructure authorization.

Personal Codex already has authenticated persistence, approvals, task/round evidence, durable inference workers and a native Mac coding workflow. Replacing it would discard stronger product-specific constraints and create competing state/permission systems. The inspected reference revision is `427c2dd11d180ac254a03e92c5fb01189fb4b23b`.

Use explicit provider/model contracts, bounded loop detection, attributed retrieval, content-minimal local traces and deterministic evaluation as design inputs. Preserve Personal Codex identity, APIs, history, offline/worker-only policies and explicit approval boundary. Fix existing memory provenance/admission/transaction defects before introducing retrieval or more agent execution paths.

Do not add OpenJarvis as a mandatory dependency, copy its broad mount defaults, enable external analytics, import cloud/training tools or run upstream install scripts. Its SQLite wrapper requires Rust, its package excludes Python3.14, and its trace collector can retain sensitive content. These create unnecessary deployment and privacy review scope for the present architecture.

A future optional adapter must implement the same scoped plan/execute/inspect/resume lifecycle and pass existing permission/cancellation/restart regressions through real application routes. It must justify each dependency and prove no silent data transfer. No adapter is implemented in this increment.

Consequences: fewer engines/features initially; greater continuity and narrower runtime dependencies. FTS5, model metadata, richer traces, full ML evaluation and remote coding remain explicit roadmap items. See [source comparison](../OPENJARVIS_REVIEW.md).
