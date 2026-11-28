"""Inference policies and the additive Linux x86_64 no-connect seccomp filter.

No daemon/firewall change. Install before starting the HTTP server. This reduces
network authority of this process/descendants; it is not a coding sandbox.
"""
from __future__ import annotations
import ctypes
import errno
import os
import platform
import re
import socket
import sys

_INSTALLED=False
ALLOW=0x7fff0000
DENY=0x00050000|errno.EPERM
KILL=0x80000000


OLLAMA_ENDPOINT = "http://127.0.0.1:11434"
# Vetted for structured coding output. The owner may name any other installed tag
# explicitly; that never widens the network, secret or provider boundary below.
OFFLINE_MODELS = ("qwen3.5:9b", "qwen2.5-coder:14b")
MODEL_TAG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,120}$")


def inference_policy():
    value = os.getenv("PERSONAL_CODEX_INFERENCE_POLICY", "development")
    if value not in {"development", "worker-only", "offline"}:
        raise ValueError("Invalid inference policy")
    return value


def worker_only():
    return inference_policy() == "worker-only"


def offline_only():
    return inference_policy() == "offline"


def model_tag(value, label="Model tag"):
    """Accept only a plain Ollama tag; never pass arbitrary text into a launch or a provider row."""
    if not isinstance(value, str) or not MODEL_TAG.match(value):
        raise ValueError(f"{label} is not a valid Ollama model tag")
    return value


def offline_model_allowlist():
    """The vetted tags plus any tags the owner explicitly adds for an offline launch."""
    extra = os.getenv("PERSONAL_CODEX_OFFLINE_MODELS", "")
    tags = [tag.strip() for tag in extra.split(",") if tag.strip()]
    return tuple(dict.fromkeys((*OFFLINE_MODELS, *(model_tag(tag, "An added offline model") for tag in tags))))


def offline_models():
    preferred = model_tag(os.getenv("PERSONAL_CODEX_OFFLINE_MODEL", OFFLINE_MODELS[0]), "Offline default")
    allowed = offline_model_allowlist()
    if preferred not in allowed:
        # An explicitly named, installed model is usable even when it is not vetted.
        allowed = (*allowed, preferred)
    inventory = os.getenv("PERSONAL_CODEX_INSTALLED_OFFLINE_MODELS")
    available = set(inventory.split(",")) if inventory is not None else set(allowed)
    if preferred not in available:
        raise ValueError("Offline default is missing from the launcher’s installed-model inventory")
    return (preferred, *(model for model in allowed if model != preferred and model in available))


def provider_allowed(provider):
    policy = inference_policy()
    if policy == "worker-only":
        return (provider.get("kind") == "mac-worker"
                and not any(provider.get(key) for key in ("endpoint", "secret_ref", "cloud_allowed")))
    if policy == "offline":
        return (provider.get("kind") == "ollama" and provider.get("endpoint") == OLLAMA_ENDPOINT
                and provider.get("model") in offline_models()
                and not provider.get("secret_ref") and not provider.get("cloud_allowed"))
    return True


def require_provider(provider):
    if not provider_allowed(provider):
        if worker_only():
            raise ValueError("This deployment permits only endpoint-free Mac worker providers")
        raise ValueError("Offline mode permits only the configured local Qwen models at 127.0.0.1:11434")


def status():
    return {"inference_policy": inference_policy(), "outbound_connections_denied": _INSTALLED,
            "scope": "backend process and descendants; independent fixed Docker health check excluded"}


def filter_program():
    # struct seccomp_data: nr at0, audit arch at4, args[0..2] low words at16/24/32.
    # x32 and other ABIs are refused. Only INET/INET6 TCP stream sockets may be
    # created; connect and io_uring alternatives are denied. Server accept/send work.
    instructions=[(0x20,0,0,4),(0x15,1,0,0xc000003e),(0x06,0,0,KILL),
                  (0x20,0,0,0),(0x35,0,1,0x40000000),(0x06,0,0,DENY)]
    for number in (42,46,53,307,425,426,427,438,101,310,311):
        instructions.extend([(0x15,0,1,number),(0x06,0,0,DENY)])
    # TCP Fast Open can connect via sendto/sendmsg without connect(). Refuse
    # sendmsg/sendmmsg above; sendto is allowed only with no destination pointer
    # and no MSG_FASTOPEN. Plain TCP server send()/sendall() uses this safe form.
    instructions.extend([(0x15,0,11,44),
        (0x20,0,0,40),(0x54,0,0,0x20000000),(0x15,1,0,0),(0x06,0,0,DENY),
        (0x20,0,0,48),(0x15,1,0,0),(0x06,0,0,DENY),
        (0x20,0,0,52),(0x15,1,0,0),(0x06,0,0,DENY),(0x06,0,0,ALLOW)])
    instructions.extend([(0x15,1,0,41),(0x06,0,0,ALLOW),
        (0x20,0,0,16),(0x15,2,0,2),(0x15,1,0,10),(0x06,0,0,DENY),
        (0x20,0,0,24),(0x54,0,0,0xf),(0x15,1,0,1),(0x06,0,0,DENY),
        (0x20,0,0,32),(0x15,2,0,0),(0x15,1,0,6),(0x06,0,0,DENY),(0x06,0,0,ALLOW)])
    return instructions


def supported():
    return platform.system()=='Linux' and platform.machine().lower() in {'x86_64','amd64'} and sys.byteorder=='little' and ctypes.sizeof(ctypes.c_void_p)==8


def install():
    """Irreversibly restrict only this process/threads and future children; fail closed."""
    global _INSTALLED
    if _INSTALLED:return
    if not supported():raise ValueError('No-connect guard requires reviewed Linux x86_64 ABI')
    # Never inherit a pre-connected socket that could bypass the new-connect rule.
    for item in os.listdir('/proc/self/fd'):
        try:target=os.readlink('/proc/self/fd/'+item)
        except FileNotFoundError:continue
        if target.startswith('socket:'):raise ValueError('Unexpected inherited socket before network restriction')
    class Instruction(ctypes.Structure):
        _fields_=[('code',ctypes.c_ushort),('jt',ctypes.c_ubyte),('jf',ctypes.c_ubyte),('k',ctypes.c_uint32)]
    class Program(ctypes.Structure):
        _fields_=[('len',ctypes.c_ushort),('filter',ctypes.POINTER(Instruction))]
    values=filter_program();array=(Instruction*len(values))(*(Instruction(*value) for value in values))
    program=Program(len(values),array)
    libc=ctypes.CDLL(None,use_errno=True);libc.prctl.restype=ctypes.c_int;libc.syscall.restype=ctypes.c_long
    if libc.prctl(38,1,0,0,0)!=0:raise OSError('Cannot set no-new-privileges')
    # seccomp(SECCOMP_SET_MODE_FILTER, SECCOMP_FILTER_FLAG_TSYNC, program).
    # Synchronisation failure may return a positive TID: every nonzero result fails.
    if libc.syscall(ctypes.c_long(317),ctypes.c_uint(1),ctypes.c_uint(1),ctypes.byref(program))!=0:
        raise OSError('Cannot install synchronised outbound connection restriction')
    # These probes cannot send packets if the reviewed filter is installed.
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as probe:
        if probe.connect_ex(('127.0.0.1',1))!=errno.EPERM:raise OSError('Outbound restriction self-test failed')
    try:
        probe=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    except PermissionError:pass
    else:
        probe.close();raise OSError('Datagram restriction self-test failed')
    # Invalid FDs make these probes packet-free even if a filter regresses.
    for number in (46,53,307,425,426,427,438):
        ctypes.set_errno(0)
        if libc.syscall(ctypes.c_long(number),-1,0,0,0,0,0)!=-1 or ctypes.get_errno()!=errno.EPERM:
            raise OSError('Alternate network syscall restriction self-test failed')
    ctypes.set_errno(0)
    if libc.syscall(ctypes.c_long(44),-1,0,0,0x20000000,ctypes.c_void_p(1),16)!=-1 or ctypes.get_errno()!=errno.EPERM:
        raise OSError('TCP Fast Open restriction self-test failed')
    _INSTALLED=True


def configure(host,mode,production=False):
    value=os.getenv('PERSONAL_CODEX_DENY_CONNECT','0')
    only=worker_only()
    if offline_only() and host != "127.0.0.1":
        raise ValueError("Offline mode requires the 127.0.0.1 listener")
    if value not in {'0','1'}:raise ValueError('Invalid outbound restriction setting')
    if production and (not only or value!='1'):
        raise ValueError('Private Serve requires worker-only inference and outbound connection restriction')
    if value=='1':
        if not only or host!='127.0.0.1' or mode!='disabled':
            raise ValueError('No-connect deployment requires worker-only inference, loopback and disabled execution')
        install()
