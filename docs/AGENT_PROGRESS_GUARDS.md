# Bounded agent progress guards

Native autonomous and full-task runs share the same guard in project_agent. A canonical SHA256 identity covers the model's operations, ignoring cosmetic summary wording and JSON key order; invalid proposals are fingerprinted before parsing/binding. It stores no additional raw proposal text.

Before execution, the recent proposal sequence is checked for an exact suffix repeated twice with periods1,2or3. For example A,B,A,B stops before the final B executes. At most96recent evidence rows and six proposal identities participate, ignoring inference/timing rows. A successfully written file with different before/after bytes resets multi-step history. A no-op write does not. Older saved tool records with changed paths and hashes but no explicit progress bit conservatively reset history. A long evidence gap can age old proposals out of the bounded window. Hash identity is not semantic equivalence.

The rejection records the period and preserves the worktree, evidence and ordinary explicit-resume controls. It does not deliver unverified work. Different proposals, changed test output, periods beyond3, semantic equivalents and oscillating edits that change content are not generally detected. Existing exact bound-proposal digests and round/time/lifetime limits still apply. Completion still requires real changes, independent planned checks and final review; this guard does not certify project correctness.

Acceptance on2026-11-20: six focused additions first failed against the missing guard and then passed, including periods2/3, near-cycle negative, progress/legacy/no-op boundaries and bounded history. The complete backend suite passed372with5skipped(377discovered). Deterministic authenticated HTTP/macOS-sandbox tasks stopped invalid two-/three-step cycles after4/6calls, retaining zero delivered files; immediate repetition stopped after2. A normal multi-round repair still delivered passing calculator code. These are injected-provider acceptance tests, not live-model or general semantic-loop benchmarks.

Reproduce in separate fresh disposable output directories:

```sh
python3 -m unittest discover -s tests -p test_proposal_progress.py -v
python3 scripts/full_task_acceptance.py --output /private/tmp/pc-cycle-two-UNUSED --proposal-cycle 2
python3 scripts/full_task_acceptance.py --output /private/tmp/pc-cycle-three-UNUSED --proposal-cycle 3
python3 scripts/full_task_acceptance.py --output /private/tmp/pc-repeat-UNUSED --repeat-proposal
```

No model download, JARVIS access, approval bypass, new dependency, migration or frontend build is required for this backend-only change.
