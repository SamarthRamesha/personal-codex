# Model metadata and inference observations

The existing per-provider model endpoint retains its `models` list and adds a bounded `catalog` of whitelisted Ollama tag properties: name, digest, stored bytes, format, family, parameter-size label and quantization. Unknown context, native tool/vision support and hardware fit remain explicitly unknown/unmeasured. Stored bytes are not RAM/VRAM requirements. No model is downloaded or automatically selected. Offline mode filters both lists to its existing installed-model allowlist; worker-only policy remains authoritative.

Model discovery remains a read-only `/api/tags` request through the current no-proxy/no-redirect transport and network consent policy. It does not invoke a model or read credentials. Invalid catalogue shapes fail closed. Names are bounded, distinct and free of control/bidirectional formatting characters. Arbitrary response fields are not forwarded.

Built-in Ollama and OpenAI-compatible adapters measure monotonic call duration and, for streams, the first nonempty text-fragment arrival. That is **first-text latency**, not per-token instrumentation. Non-streaming or worker transports do not invent an unavailable first-text time. Ollama terminal token counts/durations and compatible-provider usage are explicitly provider-reported; throughput is calculated only when output count and nonzero generation duration exist. Caller duration can include metadata/queue/transport overhead and is not used to invent token throughput.

Native coding runs persist content-minimal inference records in their existing evidence: attempt, selected model, timing and whitelisted numeric usage. They contain no extra prompt/response, endpoint, credential or arbitrary provider payload. Existing tool feedback/history retains its prior bounded policy. Resume finds the most recent actual feedback rather than mistaking a timing record for feedback. These observations do not authorize a tool, declare correctness, trigger learning, transmit telemetry or change routing. Legacy chats/manual-round ledgers retain their existing latency/history behavior; this increment is not a universal trace collector or learned router.

The native app shows selected-model properties in settings and model-call observations in task evidence. Missing counts/rates remain Unknown/Unavailable. It distinguishes configured context from an unverified model maximum, stored size from memory fit, and observed call time from a provider-reported token rate. Old backends without the optional fields remain supported. No cloud fallback or external analytics dependency is introduced.

Verification on 2026-11-19:

- 16 new backend cases passed; full335discovered/330passed/5skipped,63.144s.
- 10 frontend tests passed, including3missing-data/compatibility/provenance render cases; TypeScript/Vite build passed.
- Four actual HTTP/macOS-sandbox deterministic native task scenarios passed: new/existing1.378s each, conflict refusal1.318s, cancel/resume1.586s. Inference records survived inspection in each case.
- Optimized Tauri bundle built from cached dependencies in21.57s Rust compilation;13.15MiB bundle. Strict ad-hoc signature verification passed; not notarized.
- Separate disposable native profile manually connected with owner authentication. Settings showed the actual installed Qwen tag, reported stored size,8K configured context and unknown quantization/unverified native tools. Initial automation connection expired; resetting the UI connection recovered. No normal user profile/browser tab was used.

Actual Linux guard testing also passed13cases, including real seccomp installation/accepted HTTP/descendant denial, on a **separate disposable x86_64 Debian guest**, kernel6.12.117/Python3.13.5. This is not JARVIS runtime, Docker image or private HTTPS certification. The guest's original saved firmware state stalled; a separate simpler PC/CPU overlay booted successfully, preserving the old snapshot. Docker/base-image availability in this guest does not confer Docker authority on JARVIS.

Private raw logs, source hashes, native bundles and runtime receipts remain outside Git in the resumed mission package. Real-model benchmark, native task-metrics visual acceptance, final container behavior and target deployment are recorded separately when actually run.

Primary format references: [Ollama model listing](https://docs.ollama.com/api/tags) and [Ollama chat usage/duration fields](https://docs.ollama.com/api/chat). Unknown metrics are never filled from catalogue estimates.
