"""Approval-gated provider HTTP adapters.

Standard library only. Every adapter is a callable taking one request object of
``kind``, ``endpoint``, ``model``, ``prompt``, and ``cloud_allowed``. The secret
reference and its value never appear in that request: an OpenAI-compatible
adapter resolves its credential lazily, per call, from the named environment
variable, and never logs or persists it.

Hardening rules shared by both adapters:
- only absolute http(s) endpoints without embedded credentials
- a non-loopback endpoint is refused unless the provider is cloud-consented
- redirects are never followed (``http.client`` does not follow them); a 3xx is an error
- proxy environment variables are ignored (no ``urllib`` opener is used)
- bounded response bytes, bounded error text, per-call connection timeout
- no shared connection state, so concurrent invocations cannot cross responses
"""
from __future__ import annotations

import json
import os
from http.client import HTTPConnection, HTTPSConnection
from urllib.parse import urlsplit

DEFAULT_TIMEOUT_SECONDS = 60.0
MAX_PROVIDER_RESPONSE_BYTES = 1_000_000
MAX_ERROR_TEXT = 240
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
SUPPORTED_KINDS = {"ollama", "openai-compatible"}


class ProviderTransportError(ValueError):
    """Failure that is safe to show to the operator; never contains credentials."""


def _endpoint(endpoint: str):
    if not isinstance(endpoint, str) or not endpoint:
        raise ProviderTransportError("Provider endpoint is required")
    parts = urlsplit(endpoint)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ProviderTransportError("Provider endpoint must be an absolute http(s) URL without embedded credentials")
    try:
        port = parts.port
    except ValueError:
        raise ProviderTransportError("Provider endpoint has an invalid port")
    return parts, parts.hostname.lower(), port


def _safe_error(status: int, body: bytes) -> str:
    text = body[:MAX_ERROR_TEXT].decode("utf-8", errors="replace")
    text = " ".join(text.split())
    return f"Provider returned HTTP {status}: {text}" if text else f"Provider returned HTTP {status}"


def post_json(endpoint: str, path: str, payload: dict, *, headers=None, timeout: float = DEFAULT_TIMEOUT_SECONDS,
              max_bytes: int = MAX_PROVIDER_RESPONSE_BYTES, cloud_allowed: bool = False) -> dict:
    """POST a JSON body to an approved endpoint and return bounded parsed JSON."""
    parts, host, port = _endpoint(endpoint)
    if host not in LOOPBACK_HOSTS and not cloud_allowed:
        raise ProviderTransportError("Non-cloud provider transport refuses a non-loopback endpoint")
    if timeout <= 0:
        raise ProviderTransportError("Provider timeout must be positive")
    body = json.dumps(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/json", "Accept": "application/json", "Connection": "close"}
    request_headers.update(headers or {})
    connection_class = HTTPSConnection if parts.scheme == "https" else HTTPConnection
    connection = connection_class(host, port, timeout=timeout)
    try:
        connection.request("POST", path, body=body, headers=request_headers)
        response = connection.getresponse()
        status = response.status
        data = response.read(max_bytes + 1)
    except (OSError, TimeoutError) as error:
        raise ProviderTransportError(f"Provider connection failed: {type(error).__name__}")
    finally:
        connection.close()
    if len(data) > max_bytes:
        raise ProviderTransportError("Provider response exceeded the size limit")
    if 300 <= status < 400:
        raise ProviderTransportError("Provider redirects are not permitted")
    if status != 200:
        raise ProviderTransportError(_safe_error(status, data))
    try:
        parsed = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ProviderTransportError("Provider returned malformed JSON")
    if not isinstance(parsed, dict):
        raise ProviderTransportError("Provider returned an unexpected response structure")
    return parsed


def _assistant_text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [part.get("text", "") for part in value if isinstance(part, dict)]
        return "".join(part for part in parts if isinstance(part, str))
    return ""


class OllamaTransport:
    """Ollama ``/api/chat`` adapter (falls back to the ``/api/generate`` reply shape)."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT_SECONDS, max_bytes: int = MAX_PROVIDER_RESPONSE_BYTES):
        self.timeout, self.max_bytes = timeout, max_bytes

    def path(self, endpoint: str) -> str:
        path = urlsplit(endpoint).path.rstrip("/")
        if path.endswith("/api/chat") or path.endswith("/api/generate"):
            return path
        return f"{path}/api/chat"

    def __call__(self, request: dict) -> dict:
        endpoint = request.get("endpoint")
        parts, _, _ = _endpoint(endpoint)
        payload = {"model": request.get("model"), "messages": [{"role": "user", "content": request.get("prompt")}], "stream": False}
        if parts.path.rstrip("/").endswith("/api/generate"):
            payload = {"model": request.get("model"), "prompt": request.get("prompt"), "stream": False}
        reply = post_json(endpoint, self.path(endpoint), payload, timeout=self.timeout,
                          max_bytes=self.max_bytes, cloud_allowed=bool(request.get("cloud_allowed")))
        if reply.get("error"):
            raise ProviderTransportError("Ollama reported an error for this model or request")
        message = reply.get("message")
        text = _assistant_text(message.get("content") if isinstance(message, dict) else reply.get("response"))
        if not text.strip():
            raise ProviderTransportError("Ollama response did not contain assistant text")
        return {"text": text, "model": request.get("model")}


def openai_transport(secret_ref: str = "", *, secret_reader=None, timeout: float = DEFAULT_TIMEOUT_SECONDS,
                     max_bytes: int = MAX_PROVIDER_RESPONSE_BYTES):
    """Build an OpenAI-compatible chat-completions adapter bound to one env-var name.

    The credential is read at call time through ``secret_reader`` and is placed only
    in the outgoing Authorization header; it is never returned, logged, or stored.
    """
    reader = secret_reader or (lambda name: os.environ.get(name))

    def transport(request: dict) -> dict:
        endpoint = request.get("endpoint")
        parts, _, _ = _endpoint(endpoint)
        cloud_allowed = bool(request.get("cloud_allowed"))
        headers = {}
        if secret_ref:
            credential = reader(secret_ref)
            if not credential:
                raise ProviderTransportError("Provider credential is unavailable: set the referenced environment variable")
            headers["Authorization"] = f"Bearer {credential}"
        elif cloud_allowed:
            raise ProviderTransportError("A cloud provider requires an environment-variable secret reference")
        path = parts.path.rstrip("/")
        if not path.endswith("/chat/completions"):
            path = f"{path}/chat/completions"
        payload = {"model": request.get("model"), "messages": [{"role": "user", "content": request.get("prompt")}], "stream": False}
        reply = post_json(endpoint, path, payload, headers=headers, timeout=timeout,
                          max_bytes=max_bytes, cloud_allowed=cloud_allowed)
        choices = reply.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ProviderTransportError("Provider response did not contain a completion choice")
        message = choices[0].get("message")
        text = _assistant_text(message.get("content") if isinstance(message, dict) else None)
        if not text.strip():
            raise ProviderTransportError("Provider response did not contain assistant text")
        return {"text": text, "model": request.get("model")}

    return transport


def transport_for(provider: dict, secret_ref: str = ""):
    """Select the built-in adapter for a validated provider record."""
    kind = provider.get("kind")
    if kind == "ollama":
        return OllamaTransport()
    if kind == "openai-compatible":
        return openai_transport(secret_ref)
    raise ProviderTransportError("No provider transport is available for this provider kind")
