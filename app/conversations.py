"""Conversations, message history and genuine provider-to-UI streaming.

This module is the first stable API surface for a desktop client that is not the
task-oriented agent loop. Three rules keep it honest:

- An assistant message is stored as ``streaming`` and only becomes ``complete``
  after the provider stream ends with its terminal marker. Partial text is kept
  for display but is marked ``stopped``/``error`` and is never used as agent
  input.
- Tokens are persisted as rows in ``message_chunks`` with an AUTOINCREMENT
  sequence, so a reconnecting client resumes after the last sequence number it
  saw instead of receiving duplicated text.
- A conversation is only a beginning. Turning it into work goes through the
  existing approval-gated task flow; chat itself cannot edit files.

Standard library only, and no secret value ever reaches this module: a provider
row carries only an environment-variable *name*.
"""
from __future__ import annotations

import threading
import time
import uuid

try:
    import providers  # script execution puts app/ on sys.path
except ImportError:  # imported as app.conversations
    from app import providers

MAX_TITLE = 120
MAX_MESSAGE_CHARS = 20_000
MAX_HISTORY_MESSAGES = 200
MAX_PROMPT_MESSAGES = 20
MAX_PROMPT_CHARS = 24_000
MAX_CHUNK_CHARS = 4_000
MAX_SEARCH_LIMIT = 50
SEARCHABLE_ROLES = ("user", "assistant")
ACTIVE_STATUSES = ("queued", "streaming")

# Injectable factory: tests set this to a deterministic transport so no socket is used.
TRANSPORT = None
# message_id -> threading.Event used by stop requests and by the streaming adapters.
GENERATIONS: dict[str, threading.Event] = {}
_LOCK = threading.Lock()


def stamp() -> int:
    return int(time.time())


def uid() -> str:
    return str(uuid.uuid4())


def transport_for(provider: dict):
    """Return the streaming adapter for one provider; chat never uses a non-streaming call."""
    if TRANSPORT is not None:
        return TRANSPORT
    if provider.get("kind") == "ollama":
        return providers.OllamaStreamTransport()
    if provider.get("kind") == "openai-compatible":
        return providers.OpenAIStreamTransport(provider.get("secret_ref") or "")
    raise providers.ProviderTransportError("No chat transport is available for this provider kind")


def clean_title(value) -> str:
    text = " ".join(str(value or "").split())
    return text[:MAX_TITLE]


def derived_title(content: str) -> str:
    """A conversation needs a stable name before the model has said anything."""
    first = " ".join(str(content or "").split())
    if not first:
        return "New conversation"
    return (first[:57] + "…") if len(first) > 60 else first


def list_conversations(store, archived: bool = False, query: str = "", limit: int = 100) -> list[dict]:
    sql = ("SELECT c.*, (SELECT COUNT(*) FROM messages m WHERE m.conversation_id=c.id) AS message_count "
           "FROM conversations c WHERE c.deleted_at IS NULL AND c.archived=?")
    args: list = [int(bool(archived))]
    text = str(query or "").strip()
    if text:
        sql += " AND (c.title LIKE ? ESCAPE '\\' OR EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id=c.id AND m.content LIKE ? ESCAPE '\\'))"
        needle = f"%{text.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')}%"
        args += [needle, needle]
    sql += " ORDER BY c.pinned DESC, c.updated_at DESC LIMIT ?"
    args.append(max(1, min(200, int(limit))))
    rows = store.rows(sql, tuple(args))
    for row in rows:
        row["pinned"] = bool(row["pinned"])
        row["archived"] = bool(row["archived"])
        last = store.one("SELECT role,substr(content,1,160) AS preview FROM messages WHERE conversation_id=? "
                         "AND status IN ('complete','stopped','error') ORDER BY created_at DESC, rowid DESC LIMIT 1", (row["id"],))
        row["last_message"] = last
    return rows


def create_conversation(store, *, title: str = "", project_id: str | None = None,
                        provider_id: str | None = None, model: str = "") -> dict:
    if project_id and not store.one("SELECT id FROM projects WHERE id=?", (project_id,)):
        raise LookupError("project not found")
    if provider_id and not store.one("SELECT id FROM providers WHERE id=?", (provider_id,)):
        raise LookupError("provider not found")
    cid, at = uid(), stamp()
    store.write("INSERT INTO conversations (id,title,project_id,provider_id,model,pinned,archived,created_at,updated_at) "
                "VALUES (?,?,?,?,?,0,0,?,?)",
                (cid, clean_title(title) or "New conversation", project_id, provider_id, str(model or "")[:120], at, at))
    return store.one("SELECT * FROM conversations WHERE id=?", (cid,))


def conversation_detail(store, conversation_id: str) -> dict | None:
    row = store.one("SELECT * FROM conversations WHERE id=? AND deleted_at IS NULL", (conversation_id,))
    if not row:
        return None
    row["pinned"], row["archived"] = bool(row["pinned"]), bool(row["archived"])
    row["messages"] = message_history(store, conversation_id)
    # A chat only begins work here; every edit still passes through the approval-gated task flow.
    row["tasks"] = store.rows("SELECT t.id,t.status,t.prompt,t.updated_at FROM conversation_tasks ct "
                              "JOIN tasks t ON t.id=ct.task_id WHERE ct.conversation_id=? ORDER BY ct.created_at DESC",
                              (conversation_id,))
    return row


def message_history(store, conversation_id: str, limit: int = MAX_HISTORY_MESSAGES) -> list[dict]:
    rows = store.rows("SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at ASC, rowid ASC LIMIT ?",
                      (conversation_id, max(1, min(500, limit))))
    return rows


def update_conversation(store, conversation_id: str, fields: dict) -> dict | None:
    row = store.one("SELECT * FROM conversations WHERE id=? AND deleted_at IS NULL", (conversation_id,))
    if not row:
        return None
    changes, args = [], []
    if "title" in fields:
        title = clean_title(fields["title"])
        if not title:
            raise ValueError("title must contain visible characters")
        changes.append("title=?"), args.append(title)
    for key in ("pinned", "archived"):
        if key in fields:
            if not isinstance(fields[key], bool):
                raise ValueError(f"{key} must be a boolean")
            changes.append(f"{key}=?"), args.append(int(fields[key]))
    for key in ("project_id", "provider_id"):
        if key in fields:
            value = fields[key] or None
            table = "projects" if key == "project_id" else "providers"
            if value and not store.one(f"SELECT id FROM {table} WHERE id=?", (value,)):
                raise LookupError(f"{key.split('_')[0]} not found")
            changes.append(f"{key}=?"), args.append(value)
    if "model" in fields:
        changes.append("model=?"), args.append(str(fields["model"] or "")[:120])
    if not changes:
        return conversation_detail(store, conversation_id)
    args += [stamp(), conversation_id]
    store.write(f"UPDATE conversations SET {', '.join(changes)}, updated_at=? WHERE id=?", tuple(args))
    return conversation_detail(store, conversation_id)


def delete_conversation(store, conversation_id: str) -> dict | None:
    """Soft delete: hidden from every list, retained on disk so a mistake is recoverable.

    A running generation is stopped first; its partial text is never presented as a finished answer.
    """
    row = store.one("SELECT * FROM conversations WHERE id=? AND deleted_at IS NULL", (conversation_id,))
    if not row:
        return None
    stopped = stop_active_messages(store, conversation_id)
    store.write("UPDATE conversations SET deleted_at=?, updated_at=? WHERE id=?", (stamp(), stamp(), conversation_id))
    return {"id": conversation_id, "status": "deleted", "recoverable": True, "stopped_messages": stopped}


def stop_active_messages(store, conversation_id: str) -> int:
    rows = store.rows("SELECT id FROM messages WHERE conversation_id=? AND status IN ('queued','streaming')", (conversation_id,))
    for row in rows:
        request_stop(row["id"])
    return len(rows)


def search_messages(store, query: str, limit: int = 20) -> list[dict]:
    text = str(query or "").strip()
    if not text:
        raise ValueError("search query is required")
    needle = f"%{text.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')}%"
    rows = store.rows(
        "SELECT m.id AS message_id, m.conversation_id, m.role, substr(m.content,1,240) AS snippet, m.created_at, c.title "
        "FROM messages m JOIN conversations c ON c.id=m.conversation_id "
        "WHERE c.deleted_at IS NULL AND m.content LIKE ? ESCAPE '\\' ORDER BY m.created_at DESC LIMIT ?",
        (needle, max(1, min(MAX_SEARCH_LIMIT, int(limit)))))
    return rows


def resolve_provider(store, conversation: dict, provider_id: str | None) -> dict:
    chosen = provider_id or conversation.get("provider_id")
    if not chosen:
        raise ValueError("select a provider for this conversation")
    provider = store.one("SELECT id,kind,endpoint,model,secret_ref,cloud_allowed,enabled FROM providers WHERE id=?", (chosen,))
    if not provider:
        raise LookupError("provider not found")
    if not provider["enabled"]:
        raise ValueError("provider is disabled")
    return provider


def build_prompt(history: list[dict]) -> str:
    """Render bounded history for a chat model; the newest user turn is last."""
    # Only finished turns are model input: a stopped or failed partial answer is display-only.
    usable = [m for m in history if m["role"] in ("user", "assistant") and m["status"] == "complete"]
    selected, total = [], 0
    for message in reversed(usable):
        text = str(message["content"] or "")
        if not text:
            continue
        cost = len(text) + 16
        if selected and (len(selected) >= MAX_PROMPT_MESSAGES or total + cost > MAX_PROMPT_CHARS):
            break
        selected.append(message)
        total += cost
    selected.reverse()
    header = ("You are Personal Codex, a private local coding assistant on the owner's machine. "
              "Answer the latest user message. You cannot run commands or edit files in a chat; file changes "
              "require an approval-gated agent task, so never claim you performed one.")
    lines = [header, "Conversation so far (oldest first, truncated if long):"]
    if not selected:
        lines.append("NO PRIOR TURNS")
    for message in selected:
        text = str(message["content"] or "")
        if len(text) > MAX_CHUNK_CHARS * 2:
            text = text[:MAX_CHUNK_CHARS * 2] + " …[truncated]"
        lines.append(f"{message['role'].upper()}: {text}")
    lines.append("ASSISTANT:")
    return "\n\n".join(lines)


def new_message(store, conversation_id: str, role: str, content: str, status: str = "complete", **extra) -> dict:
    if role not in ("user", "assistant", "system"):
        raise ValueError("unsupported message role")
    if len(content) > MAX_MESSAGE_CHARS:
        raise ValueError(f"message must be at most {MAX_MESSAGE_CHARS} characters")
    mid, at = uid(), stamp()
    store.write("INSERT INTO messages (id,conversation_id,role,content,status,provider_id,model,error,latency_ms,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (mid, conversation_id, role, content, status, extra.get("provider_id"), extra.get("model"),
                 extra.get("error"), extra.get("latency_ms"), at, at))
    store.write("UPDATE conversations SET updated_at=? WHERE id=?", (at, conversation_id))
    return store.one("SELECT * FROM messages WHERE id=?", (mid,))


def append_chunk(store, conversation_id: str, message_id: str, text: str) -> int:
    """Persist one streamed delta and return its resumable sequence number."""
    if not text:
        return 0
    if len(text) > MAX_CHUNK_CHARS:
        text = text[:MAX_CHUNK_CHARS]
    with _LOCK:
        store.write("INSERT INTO message_chunks (message_id,conversation_id,text,created_at) VALUES (?,?,?,?)",
                    (message_id, conversation_id, text, stamp()))
        row = store.one("SELECT last_insert_rowid() AS seq")
        store.write("UPDATE messages SET content=content||?, updated_at=? WHERE id=?", (text, stamp(), message_id))
    return int(row["seq"]) if row else 0


def request_stop(message_id: str) -> bool:
    event = GENERATIONS.get(message_id)
    if not event:
        return False
    event.set()
    return True


def start_turn(store, conversation: dict, content: str, *, provider: dict | None = None,
               regenerate: bool = False) -> dict:
    """Create the stored turns and start one provider call in a daemon thread.

    The HTTP handler returns immediately with the assistant message id; the client then follows
    ``/api/conversations/{id}/messages/{mid}/stream`` for incremental text.
    """
    text = str(content or "").strip()
    if not text and not regenerate:
        raise ValueError("message content is required")
    if len(text) > MAX_MESSAGE_CHARS:
        raise ValueError(f"message must be at most {MAX_MESSAGE_CHARS} characters")
    provider = provider or resolve_provider(store, conversation, None)
    if regenerate:
        last_user = store.one("SELECT content FROM messages WHERE conversation_id=? AND role='user' ORDER BY created_at DESC, rowid DESC LIMIT 1",
                              (conversation["id"],))
        if not last_user:
            raise ValueError("nothing to regenerate: this conversation has no user message")
        text = last_user["content"]
    else:
        new_message(store, conversation["id"], "user", text)
        if conversation["title"] == "New conversation":
            store.write("UPDATE conversations SET title=? WHERE id=?", (derived_title(text), conversation["id"]))

    history = message_history(store, conversation["id"])
    prompt = build_prompt(history)
    assistant = new_message(store, conversation["id"], "assistant", "", status="queued",
                            provider_id=provider["id"], model=provider["model"])
    if provider.get("cloud_allowed"):
        # A chat turn is an explicit send, but a cloud transmission still needs its own recorded consent.
        store.write("INSERT INTO approvals (id,project_id,kind,detail,status,created_at) VALUES (?,?,?,?,?,?)",
                    (uid(), conversation.get("project_id") or "", "network",
                     f"chat:{conversation['id']}:{assistant['id']}", "approved", stamp()))
    event = threading.Event()
    with _LOCK:
        GENERATIONS[assistant["id"]] = event
    thread = threading.Thread(target=_run_turn, args=(store, conversation, assistant["id"], provider, prompt, event),
                              name=f"chat-{assistant['id'][:8]}", daemon=True)
    thread.start()
    return {"conversation_id": conversation["id"], "user_message": text if not regenerate else None,
            "assistant_message_id": assistant["id"], "status": "queued", "model": provider["model"],
            "provider_id": provider["id"], "regenerated": bool(regenerate)}


def _run_turn(store, conversation: dict, message_id: str, provider: dict, prompt: str, cancel: threading.Event) -> None:
    """One provider call. Final text comes from the adapter, never from the displayed chunks."""
    started = time.time()
    store.write("UPDATE messages SET status='streaming', updated_at=? WHERE id=?", (stamp(), message_id))
    streamed: list[str] = []

    def on_text(chunk: str) -> None:
        if not chunk or cancel.is_set():
            return
        append_chunk(store, conversation["id"], message_id, chunk)
        streamed.append(chunk)

    try:
        adapter = transport_for(provider)
        result = adapter({"endpoint": provider["endpoint"], "model": provider["model"], "prompt": prompt,
                          "cloud_allowed": bool(provider["cloud_allowed"]), "secret_ref": provider.get("secret_ref") or "",
                          "stop_check": cancel.is_set, "on_text": on_text, "on_chunk": lambda count: None})
        text = str((result or {}).get("text") or "").strip()
        if not text:
            raise providers.ProviderTransportError("Provider returned no assistant text")
        latency = int((time.time() - started) * 1000)
        store.write("UPDATE messages SET content=?, status='complete', error=NULL, latency_ms=?, updated_at=? WHERE id=?",
                    (text[:MAX_MESSAGE_CHARS], latency, stamp(), message_id))
        store.write("UPDATE providers SET last_latency_ms=?, last_checked_at=? WHERE id=?",
                    (latency, stamp(), provider["id"]))
    except Exception as error:  # a failing provider must never take the control plane down
        stopped = cancel.is_set()
        latency = int((time.time() - started) * 1000)
        detail = "Stopped by operator; partial text was retained for display only." if stopped else \
            providers.redact_provider_text(str(error))[:400] or "Provider call failed"
        status = "stopped" if stopped else "error"
        store.write("UPDATE messages SET status=?, error=?, latency_ms=?, updated_at=? WHERE id=?",
                    (status, detail, latency, stamp(), message_id))
    finally:
        with _LOCK:
            GENERATIONS.pop(message_id, None)


def wait_for_message(store, message_id: str, timeout: float = 10.0) -> dict | None:
    """Test and shutdown helper: block until a turn leaves the active states."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        row = store.one("SELECT * FROM messages WHERE id=?", (message_id,))
        if row and row["status"] not in ACTIVE_STATUSES:
            return row
        time.sleep(0.05)
    return store.one("SELECT * FROM messages WHERE id=?", (message_id,))


def stream_events(store, conversation_id: str, message_id: str, after: int = 0):
    """Yield ``(event, data)`` pairs for SSE, resuming after a chunk sequence number."""
    message = store.one("SELECT * FROM messages WHERE id=? AND conversation_id=?", (message_id, conversation_id))
    if not message:
        raise LookupError("message not found")
    last = max(0, int(after or 0))
    while True:
        rows = store.rows("SELECT seq,text FROM message_chunks WHERE message_id=? AND seq>? ORDER BY seq ASC LIMIT 100",
                          (message_id, last))
        for row in rows:
            last = int(row["seq"])
            yield "token", {"seq": last, "text": row["text"]}
        current = store.one("SELECT status,error,content,model,latency_ms FROM messages WHERE id=?", (message_id,))
        if current["status"] not in ACTIVE_STATUSES:
            if not rows:
                yield "done", {"status": current["status"], "error": current["error"], "bytes": len(current["content"] or ""),
                               "model": current["model"], "latency_ms": current["latency_ms"]}
                return
            continue
        if not rows:
            yield "ping", {"status": current["status"]}
            time.sleep(0.15)


def conversation_report(store, conversation_id: str) -> dict | None:
    conversation = conversation_detail(store, conversation_id)
    if not conversation:
        return None
    active = [m["id"] for m in conversation["messages"] if m["status"] in ACTIVE_STATUSES]
    return {"conversation": conversation, "active_messages": active,
            "streaming": bool(active), "limits": {"message_chars": MAX_MESSAGE_CHARS, "title_chars": MAX_TITLE}}
