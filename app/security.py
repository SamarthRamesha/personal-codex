"""Owner authentication and private-listener policy. No discovery or configuration changes."""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os
import secrets
import stat
import threading
import time
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlsplit

MAX_BODY_BYTES = 1_000_000
COOKIE = "pc_session"


def is_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host == "localhost"


def private_bind(host: str, authenticated: bool, tls: bool) -> None:
    if is_loopback(host):
        return
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        raise ValueError("Bind to an explicit loopback or Tailscale IP address") from None
    tailnet = (address in ipaddress.ip_network("100.64.0.0/10") if address.version == 4 else
               address in ipaddress.ip_network("fd7a:115c:a1e0::/48"))
    if not tailnet or not authenticated or not tls:
        raise ValueError("Remote binding requires a Tailscale IP, an owner token file and TLS certificate/key")


class OwnerAuth:
    """One owner, bounded in-memory sessions; restarting or logging out revokes sessions."""
    def __init__(self, token: str = "", *, ttl: int = 3600, clock=time.monotonic):
        if token and (len(token) < 32 or len(token) > 512 or not token.isascii() or any(c.isspace() for c in token)):
            raise ValueError("Owner token must be 32–512 non-whitespace ASCII characters")
        self.digest = self._digest(token) if token else None
        self.ttl = ttl
        self.clock = clock
        self.sessions: dict[str, float] = {}
        self.failures: dict[str, tuple[int, float]] = {}
        self.lock = threading.RLock()

    @staticmethod
    def _digest(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    @property
    def enabled(self) -> bool:
        return self.digest is not None

    @classmethod
    def from_env(cls, variable="PERSONAL_CODEX_TOKEN_FILE"):
        filename = os.getenv(variable, "")
        if not filename:
            return cls()
        path = Path(filename).expanduser()
        try: fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        except OSError: raise ValueError("Owner token file is unavailable or is a symlink") from None
        with os.fdopen(fd, "r") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid():
                raise ValueError("Owner token file must be an owner-only regular file (mode 0600)")
            if info.st_size > 1024:
                raise ValueError("Owner token file is too large")
            token = stream.read(1025).strip()
        if not token: raise ValueError("Owner token file must not be empty")
        return cls(token)

    def valid_token(self, token: str) -> bool:
        return bool(self.digest and hmac.compare_digest(self._digest(token), self.digest))

    def _prune(self):
        now = self.clock()
        self.sessions = {key: expiry for key, expiry in self.sessions.items() if expiry > now}
        self.failures = {key: row for key, row in self.failures.items() if row[1] > now}

    def login(self, token: str, peer: str) -> str:
        with self.lock:
            self._prune()
            count, until = self.failures.get(peer, (0, self.clock() + 60))
            if count >= 5:
                raise PermissionError("Too many authentication attempts; wait one minute")
            if not self.valid_token(token):
                # Bounded even when an unauthenticated peer supplies many source addresses.
                if len(self.failures) >= 256:
                    self.failures.pop(next(iter(self.failures)))
                self.failures[peer] = (count + 1, until)
                raise PermissionError("Invalid owner token")
            self.failures.pop(peer, None)
            value = secrets.token_urlsafe(32)
            if len(self.sessions) >= 32:
                self.sessions.pop(next(iter(self.sessions)))
            self.sessions[self._digest(value)] = self.clock() + self.ttl
            return value

    def authorized(self, headers) -> bool:
        if not self.enabled:
            return True
        auth = headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return self.valid_token(auth[7:])
        value = self.cookie_value(headers)
        with self.lock:
            self._prune()
            return bool(value and self._digest(value) in self.sessions)

    @staticmethod
    def cookie_value(headers) -> str:
        cookies = SimpleCookie()
        try:
            cookies.load(headers.get("Cookie", ""))
        except Exception:
            return ""
        return cookies[COOKIE].value if COOKIE in cookies else ""

    def logout(self, headers):
        with self.lock:
            self.sessions.pop(self._digest(self.cookie_value(headers)), None)


def request_origin_error(headers, addresses: set[str], *, tls: bool = False) -> str | None:
    """Reject DNS rebinding and browser cross-origin requests before reading a body."""
    if hasattr(headers, "get_all") and len(headers.get_all("Host", [])) != 1:
        return "Exactly one Host header is required"
    host = headers.get("Host", "").lower()
    if host not in addresses:
        return "Unrecognized Host header"
    origin = headers.get("Origin")
    if origin:
        expected = ("https://" if tls else "http://") + host
        if origin.lower() != expected:
            return "Cross-origin requests are not allowed"
    if headers.get("Sec-Fetch-Site") == "cross-site":
        return "Cross-site requests are not allowed"
    return None


def public_origin(value: str) -> str:
    """One explicit private HTTPS authority; no URL forwarding or wildcard trust."""
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ValueError("Invalid public origin") from None
    host = (parsed.hostname or "").lower()
    if (parsed.scheme != "https" or not host.endswith(".ts.net") or len(host) <= 7
            or parsed.username or parsed.password or parsed.path not in {"", "/"}
            or parsed.query or parsed.fragment or any(c.isspace() for c in value)):
        raise ValueError("Public origin must be an explicit HTTPS Tailscale hostname with no path or credentials")
    return "https://" + host + (f":{port}" if port and port != 443 else "")


def validate_proxy_config(host: str, authenticated: bool, tls: bool, origin: str = "") -> None:
    if not origin:
        return
    public_origin(origin)
    if not is_loopback(host) or not authenticated or tls:
        raise ValueError("Serve mode requires a loopback HTTP listener and configured owner authentication")


def request_boundary(headers, bound: str, port: int, peer: str, *, tls=False, origin="") -> tuple[bool, str | None]:
    """Trust exact Serve metadata only from loopback and only after explicit configuration.

    Forwarded identity never authenticates a request. The owner/worker token is still required.
    Local diagnostics remain HTTP and cannot acquire HTTPS cookie semantics accidentally.
    """
    authority = f"{'['+bound+']' if ':' in bound else bound}:{port}"
    addresses = {authority}
    if is_loopback(bound):
        addresses.update({f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"})
    configured = os.getenv("PERSONAL_CODEX_SERVER_NAME", "").lower()
    if configured:
        addresses.add(f"{configured}:{port}")
    if port == (443 if tls else 80):
        addresses.update({host.rsplit(":", 1)[0] for host in list(addresses)})
    forwarded = any(headers.get(name) is not None for name in
                    ("Forwarded", "X-Forwarded-Host", "X-Forwarded-Proto", "X-Forwarded-For"))
    if forwarded:
        if not origin or not is_loopback(peer) or not is_loopback(bound) or tls:
            return tls, "Untrusted proxy metadata"
        expected = public_origin(origin)
        host = expected.removeprefix("https://")
        for name in ("X-Forwarded-Host", "X-Forwarded-Proto"):
            if hasattr(headers, "get_all") and len(headers.get_all(name, [])) != 1:
                return tls, "Exactly one proxy authority and scheme are required"
        if (headers.get("Forwarded") is not None or headers.get("X-Forwarded-Host", "").lower() != host
                or headers.get("Host", "").lower() != host or headers.get("X-Forwarded-Proto") != "https"):
            return tls, "Proxy authority or scheme does not match configured HTTPS origin"
        return True, request_origin_error(headers, {host}, tls=True)
    return tls, request_origin_error(headers, addresses, tls=tls)
