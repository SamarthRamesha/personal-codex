# Security policy and current boundaries

Personal Codex is a single-owner local-first development workspace. This policy describes implemented controls and limits, not a claim of complete security or a deployed JARVIS service. Do not post credentials or private incident details in a public issue.

## Authority and transport

The backend defaults to loopback. Private remote profiles require authentication and verified TLS at the explicitly reviewed origin. The native bridge rejects public/insecure remote URLs, embedded credentials, redirects, proxy-environment fallback and certificate overrides. Owner tokens stay in native process memory or their original owner-only offline files, not browser storage. Server cookie sessions are bounded/HttpOnly and browser requests have origin/header protections.

Owner and inference-worker tokens grant different authority. The worker opens outbound connections only to the approved backend and fixed local Ollama; it does not open an inbound Mac listener. Leases, acknowledgments, replay journal, rotation/revocation and bounded requests prevent ambiguous jobs from being silently replayed. No silent cloud fallback or unrequested model download is part of the local-first profiles.

## Coding and data

Tasks bind to approved project/directory identity and Git baseline. Mutations occur in isolated task worktrees with exact review, stale-file checks, bounded command allowlists, cancellation and explicit resume. Partial work and conflicting user edits are preserved. Completion requires actual checked changes and verification; proposal-cycle guards are exact bounded heuristics, not semantic correctness proof.

Imported excerpts and model outputs remain untrusted. Memory promotion is evidence-bound and explicitly approved; selected-document search is opt-in, scoped, attributed and bounded, with stale/tampered omission and transactional index updates. No server-wide file scan or automatic memory training is enabled. Removing an index does not erase the original attachment, history or backups.

Default additional model metrics contain timings/counts rather than new prompt/credential payloads. Runtime profiles, keys, private server inventory, personal documents and model caches stay outside source control. Logs, requests, clients, context, command output and snapshots have bounds; these do not constitute a complete data-loss-prevention system.

## Mac actions

Named native-local commands can search standard application directories, accept Finder selections and prepare one-use app/document/Finder opening reviews. Confirmation expires, consumes its preview, and revalidates canonical path/identity. Scripts, credential/configuration paths and symlink/stale selections are refused. The fixed opener receives separate arguments and a filtered environment; no arbitrary shell or AppleScript is provided. No backend HTTP route or automatic model dispatch can exercise this capability.

This capability does not grant Accessibility, Automation, screen capture, system-wide reading or arbitrary cross-app control. It assumes the owner trusts local processes and chosen applications; identity revalidation is not race-free application-code integrity against a hostile same-user process. New panel visual acceptance is still blocked despite passing native tests/build.

## Server and operating system

The prepared production API keeps repository execution disabled, inference worker-only and an additive Linux no-connect filter enabled. The reviewed container profile requires nonroot identity, read-only root, dropped capabilities, no-new-privileges, actual CPU/memory/swap/PID bounds and dedicated mounts. Host networking is not network isolation. The syscall filter is defense in depth, not a complete sandbox; independent Docker exec/healthcheck processes do not inherit it.

The operator-only executor prototype is not accepted or wired as production coding. The API must never gain Docker authority. JARVIS installer/importer behavior, user mapping, live runtime controls, HTTPS/Serve/access restrictions and family-service preservation remain unresolved and approval-gated. Do not use sudo/group/socket/credential workarounds, broad reset/cleanup or previously declined probes.

## Recovery and residual gaps

Storage admission and SQLite page caps are not a whole-filesystem quota. The encrypted recovery envelope is limited to 64 MiB and does not cover a production-sized installation. Whole-volume limits, large streaming recovery, key custody/off-device schedules, signed/notarized distribution, trusted updates, broader UI regression and general cross-app automation remain unfinished.

Latest local evidence: 372 backend passes / 5 skips, 14 frontend tests, 7 native tests and 17 exact-source disposable-Linux container checks. These do not establish remote deployment or universal safety. Read the [threat model](docs/THREAT_MODEL.md), [current matrix](docs/IMPLEMENTATION_MATRIX.md), [Mac actions](docs/MAC_ACTIONS.md) and [deployment gates](DEPLOYMENT.md). Older detailed security milestones remain in Git history.
