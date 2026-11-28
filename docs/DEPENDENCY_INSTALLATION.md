# Reviewed dependency installation

In an authenticated offline Mac task with an approved worktree, open Task worktree readiness and choose **Review locked npm install**. Inspect the destination, file hashes, exact packages, tarball URLs, network origin and command. Independently confirm installation and the listed registry downloads, then execute once. Review expires after ten minutes. A changed manifest, lockfile, directory, digest or spent proposal requires a new review.

Only npm lockfile v2/v3, at most 100 SHA512-pinned packages, and exact HTTPS registry.npmjs.org tarballs are supported. No credentials, proxy forwarding, redirects, Git/file dependencies or workspaces. Downloads are limited to 8 MiB each/64 MiB total; declared expansion is capped at 128 MiB. Archive links and traversal are refused. npm runs offline inside the Mac process boundary with lifecycle scripts disabled, clean configuration and a private cache. Scripts/native addon setup may therefore remain incomplete. Python/Rust/Go and replacement installs remain operator-managed.

Source and lockfiles are copied into private staging. Only a new node_modules is published after identity/hash revalidation. Existing dependency trees are preserved. Progress, final errors and restart interruption are persisted. Cancel closes the attempt without automatic retry; private staging is retained for inspection. It contributes to application storage usage and is not automatically pruned. Other task mutations wait while installation runs. This workflow does not grant arbitrary package-manager commands or server installation authority.

Tests use synthetic tarballs and an actual confined offline npm process. Opt-in real registry acceptance uses a new disposable profile:

```sh
python3 scripts/dependency_acceptance.py --registry --output /absolute/new/disposable-directory
```

The command downloads only public is-number@7.0.0 metadata/tarball and records nonsecret evidence. It is not a production project installation. JARVIS/server profiles reject the installer.
