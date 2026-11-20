# Mac actions

The native application now has a local **Mac actions** panel. It works without backend authentication or a JARVIS connection and never sends its application catalogue, chosen path or document contents to a model/server.

## Supported actions

| Action | Selection | Effect |
|---|---|---|
| Launch installed application | Bounded search of standard system/user Applications directories | Ask macOS to launch that exact bundle |
| Open document | Native Finder picker; supported document/image formats | Ask the registered default app to open it |
| Reveal file/folder | Native Finder picker | Select the exact item in Finder |

Supported opening extensions: TXT, Markdown, PDF, PNG/JPEG/WebP/GIF, CSV/TSV, JSON, RTF and non-macro DOCX/XLSX/PPTX. Scripts, executables and credential/configuration paths are refused. Finder selection alone does not open an item.

## Review boundary

Each choice creates one native in-memory preview containing the exact canonical destination and filesystem identity. Confirmation consumes it once, including rejected/failed attempts; it expires after 120 seconds. A replacement selection invalidates the prior one. Modified/replaced/symlink items and changed app eligibility are refused at execution. Cancel clears the pending choice.

Only named native IPC commands can request an action. There is no backend HTTP endpoint, arbitrary command string, model-dispatched system tool, shell, AppleScript, automation-permission change or file-content reader. The fixed macOS opener receives separate arguments and a filtered environment, excluding backend credentials and the native capability. Opening does not close existing apps or disable Gatekeeper.

This is a trusted-local-user capability. Filesystem identity checks narrow stale selection risk; they are not a complete hostile-process or race-free application-code integrity boundary. The default document app can ask for its own permissions. The success receipt means the opener accepted the request, not that an entire UI workflow completed. An uncertain timeout must not be blindly retried.

## What is still missing

General screen interpretation, clicking/typing across apps, browser automation, natural-language multi-app workflows, a system-wide hotkey/voice mode and scoped Accessibility/Automation permission handling are not implemented. Remote JARVIS requests cannot operate the Mac through this panel. Project editing still goes through approved coding tasks.

## Evidence

Four native tests cover credential/control-path refusal, script/app-root boundaries, changed items and one-use confirmation, expiration, replacement and symlinks. Together with existing native connection/stream tests,7 Rust tests pass. Frontend14tests and TypeScript/Vite pass; the optimized13.35 MiB app builds and strict ad-hoc signature verification passes. Not notarized.

The native UI connector stalled during visual acceptance; no successful app/document/Finder opening through the actual new panel is claimed. Keep that acceptance gate visible rather than treating the build as UI proof.
