"""In-process Respan Gateway as an approved provider transport.

Personal Codex keeps one hardened provider boundary in ``app/providers.py``: bounded bytes, no
redirects, no proxy environment, no shared connection state, credential redaction. The Respan
Gateway (``respan-gateway==0.3.0``) is served by this module on a loopback port it picks itself and
routes each chat request to the developer's own provider keys (``OPENAI_API_KEY``,
``ANTHROPIC_API_KEY``, ``GEMINI_API_KEY``, or a local ``gateway.toml``). A provider registered with
kind ``respan-gateway`` therefore still travels through that one boundary, and gains the gateway's
routing, retry and fallback rules for its model.

Nothing here reads, stores or logs a credential: the gateway resolves its provider secrets itself,
and Personal Codex sends it no Authorization header. The listener is loopback only, and a provider
record keeps no gateway port, because the port is chosen per process at first use.
"""
from __future__ import annotations

import threading

try:
    import providers
except ImportError:  # imported as app.gateway
    from app import providers

GATEWAY_KIND = "respan-gateway"
GATEWAY_PACKAGE = "respan-gateway==0.3.0"
INSTALL_COMMAND = f"pip install --only-binary=:all: {GATEWAY_PACKAGE}"
MAX_GATEWAY_ERROR_TEXT = 240


class GatewayUnavailable(providers.ProviderTransportError):
    """The pinned gateway package is missing or unconfigured; the message is safe to show."""


class LocalGateway:
    """One gateway serving loopback only, used by every ``respan-gateway`` provider in the process."""

    def __init__(self, config=None):
        try:
            import respan_gateway as rg
        except ImportError as error:
            raise GatewayUnavailable(f"Respan Gateway is not installed; run `{INSTALL_COMMAND}`") from error
        try:
            self._gateway = rg.Gateway() if config is None else rg.Gateway(config=config)
            self._server = self._gateway.serve(host="127.0.0.1", port=0)
        except rg.ConfigError as error:
            # The gateway has no provider key yet; its own message names the variables, never a value.
            detail = providers.redact_provider_text(" ".join(str(error).split()))[:MAX_GATEWAY_ERROR_TEXT]
            raise GatewayUnavailable(f"Respan Gateway has no provider configured: {detail}") from error
        except rg.GatewayError as error:
            raise GatewayUnavailable(f"Respan Gateway failed to start: {type(error).__name__}") from error
        self.url = self._server.url.rstrip("/")

    @property
    def endpoint(self) -> str:
        """The gateway's OpenAI-compatible base URL, for the app's existing adapter."""
        return f"{self.url}/v1"

    def close(self) -> None:
        self._server.stop()
        self._gateway.close()

    def transport(self):
        """Non-streaming adapter: the hardened OpenAI-compatible client, pointed at the gateway."""
        client = providers.openai_transport("")
        return lambda request: client({**request, "endpoint": self.endpoint, "cloud_allowed": False})

    def stream_transport(self):
        """Streaming adapter: same boundary, SSE frames, still bounded and terminal-marker checked."""
        streamer = providers.OpenAIStreamTransport("")
        return lambda request: streamer({**request, "endpoint": self.endpoint, "cloud_allowed": False})


_LOCK = threading.Lock()
_ACTIVE: LocalGateway | None = None


def active_gateway() -> LocalGateway:
    """The process-wide gateway, started on first use; no network call leaves loopback."""

    global _ACTIVE
    with _LOCK:
        if _ACTIVE is None:
            _ACTIVE = LocalGateway()
        return _ACTIVE


def start_gateway(config=None) -> LocalGateway:
    """Replace any running gateway (a test or fixture seam); production code uses `active_gateway`."""

    global _ACTIVE
    stop_gateway()
    with _LOCK:
        _ACTIVE = LocalGateway(config)
        return _ACTIVE


def stop_gateway() -> None:
    """Stop the gateway this process started; the next use starts a fresh one."""

    global _ACTIVE
    with _LOCK:
        gateway, _ACTIVE = _ACTIVE, None
    if gateway is not None:
        gateway.close()


def transport():
    """The approved non-streaming transport for a ``respan-gateway`` provider."""
    return active_gateway().transport()


def stream_transport():
    """The approved streaming transport for a ``respan-gateway`` provider."""
    return active_gateway().stream_transport()
