# OpenJarvis architecture review — 2026-11-19

Personal Codex remains the product and native runtime. OpenJarvis is a source-only architectural reference, not a runtime dependency. Audit baseline: Personal Codex `24014bf12097fb38c9908bac97f8fb120542b4b5`, branch `personal-codex/stabilization`, clean tracked tree. Preserve the protected untracked diagnostic without reading it.

Inspected OpenJarvis revision: **`427c2dd11d180ac254a03e92c5fb01189fb4b23b`** (2026-11-19T06:11:29Z). README and all supplied architecture/user-guide paths existed. No upstream code, install scripts or test suite were executed. Observations below concern inspected source, not certification or benchmark results.

| Area | Actual reference source | Personal Codex comparison and decision |
|---|---|---|
| Model intelligence | `intelligence/model_catalog.py`, `core/types.py` model/quantization/context/engine metadata | Existing offline allowlist and model-name discovery are safer than automatic engine fallback but less descriptive. Add installed-model descriptors with observed metadata and explicit unknowns; hardware estimates must not silently select or download models |
| Inference | `engine/_stubs.py` generate/stream/list/health contract, rich `StreamChunk`; `engine/ollama.py` options and usage | Adopt typed transport/results and measured usage incrementally. Retain current no-redirect/proxy behavior, worker-only/offline policy, per-call transmission consent, stop and deadlines. Do not import its engine/dependency tree |
| Agents | `agents/orchestrator.py` structured/native calls; `agents/loop_guard.py` identical-call/cycle/poll/context guards | Extend existing task/round/full-task engines, rather than another parallel orchestrator. Add evidence-based cycle detection and stable failure classes; native tool support must be verified per model |
| Tools | `tools/_stubs.py` tool metadata, capabilities, bounded dispatch | Typed closed descriptors are useful; dynamic imported tools cannot gain permission. Thread timeouts do not kill tool authority. Preserve process boundaries and exact operation review |
| Memory | `tools/storage/sqlite.py`, `memory/service.py`, attributed results | FTS5 and attributed retrieval are useful future increments after correcting existing memory policy. The inspected SQLite wrapper requires the Rust extension, despite the zero-dependency wording. Do not add it to the stdlib backend |
| Learning | `learning/routing/learned_router.py`, traces/analysis/benchmark gates | Start with offline outcome measurement; no private-data training, automatic self-modification, cloud judges or automatic learned routing. Five samples in a reference policy are not a general reliability guarantee |
| Sandboxing | `sandbox/mount_security.py`, `sandbox/runner.py` | Keep stricter Personal Codex constraints: default empty root allowlist there permits non-blocked paths, and checking a mount's name does not inspect sensitive descendants. Runner network-none and read-only binds alone do not meet our nonroot/userns/LSM/cgroup/read-only-rootfs requirements |
| Observability | `traces/collector.py`, telemetry and analytics modules | Use local timings/correlation with content-minimal defaults. Full prompts/tool args/messages in traces create retention/privacy obligations. External PostHog module is default disabled; exclude it from Personal Codex entirely |
| Engineering | Fake engines, malformed-stream/loop/mount tests, CI security/lint/Python matrix and Rust extension build | Adopt deterministic failure scenarios and reproducible evidence. No claim that those upstream tests pass here; importing all dependencies merely to run them is not justified |

The source declares Python `>=3.11,<3.14`, Rust-backed memory and broad default dependencies including external-service integrations. Historical server Python was 3.14. Those are practical coupling/compatibility reasons to keep this reference outside the runtime. Apache-2.0 is declared upstream; no upstream implementation was copied into this change.

Implementation priority from this review is correcting existing memory integrity first: shared admission policy, truthful provenance and transactional promotion. Search indexing or new agents would otherwise amplify inconsistent stored authority. See [roadmap](MASTER_MISSION_ROADMAP.md), [decision](decisions/0001-openjarvis-reference.md) and [test report](MASTER_MISSION_TEST_REPORT.md).

Pinned primary sources:

- [Engine interface](https://github.com/open-jarvis/OpenJarvis/blob/427c2dd11d180ac254a03e92c5fb01189fb4b23b/src/openjarvis/engine/_stubs.py)
- [Loop guard](https://github.com/open-jarvis/OpenJarvis/blob/427c2dd11d180ac254a03e92c5fb01189fb4b23b/src/openjarvis/agents/loop_guard.py)
- [SQLite memory implementation](https://github.com/open-jarvis/OpenJarvis/blob/427c2dd11d180ac254a03e92c5fb01189fb4b23b/src/openjarvis/tools/storage/sqlite.py)
- [Mount validation](https://github.com/open-jarvis/OpenJarvis/blob/427c2dd11d180ac254a03e92c5fb01189fb4b23b/src/openjarvis/sandbox/mount_security.py)
- [Container runner](https://github.com/open-jarvis/OpenJarvis/blob/427c2dd11d180ac254a03e92c5fb01189fb4b23b/src/openjarvis/sandbox/runner.py)
- [Dependency declarations](https://github.com/open-jarvis/OpenJarvis/blob/427c2dd11d180ac254a03e92c5fb01189fb4b23b/pyproject.toml)

Detailed private device/policy/storage/access evidence stays outside Git in the current audit package. None of these reference patterns authorizes a deployment, model download, network change or private-data transfer.
