"""Private service lifecycle: one data-root owner, bounded clients, graceful stop."""
from __future__ import annotations
import fcntl
import os
from pathlib import Path
import socket
from socketserver import TCPServer
import stat
import threading
import time
from http.server import ThreadingHTTPServer


class InstanceLock:
    def __init__(self,root:Path):self.root=root;self.fd=None
    def __enter__(self):
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.fd=os.open(self.root/'.backend.lock',os.O_RDWR|os.O_CREAT|getattr(os,'O_NOFOLLOW',0),0o600)
        info=os.fstat(self.fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode & 0o077:
            os.close(self.fd);self.fd=None;raise ValueError('Backend lock must be a private owner-only regular file')
        try:fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self.fd);self.fd=None;raise ValueError('A backend already owns this data directory') from None
        return self
    def __exit__(self,*_):
        if self.fd is not None:os.close(self.fd);self.fd=None


class ControlServer(ThreadingHTTPServer):
    daemon_threads=True
    allow_reuse_address=True
    def __init__(self,address,handler,*,tls_context=None,max_clients=32):
        self.address_family=socket.AF_INET6 if ':' in address[0] else socket.AF_INET
        self.tls_context=tls_context;self.capacity=threading.BoundedSemaphore(max_clients)
        self.active=0;self.activity=threading.Condition()
        super().__init__(address,handler)
    def server_bind(self):
        # HTTPServer uses getfqdn here. A local listener must start without reverse DNS.
        TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]
    def get_request(self):
        client,address=super().get_request();client.settimeout(10)
        if self.tls_context is not None:
            try:client=self.tls_context.wrap_socket(client,server_side=True,do_handshake_on_connect=False)
            except Exception:client.close();raise
        return client,address
    def process_request(self,request,address):
        if not self.capacity.acquire(blocking=False):self.shutdown_request(request);return
        with self.activity:self.active+=1
        try:super().process_request(request,address)
        except Exception:
            self._release();raise
    def _release(self):
        self.capacity.release()
        with self.activity:self.active-=1;self.activity.notify_all()
    def process_request_thread(self,request,address):
        try:super().process_request_thread(request,address)
        finally:self._release()
    def handle_error(self,request,address):
        print('[personal-codex] request failed; details withheld from service logs',flush=True)
    def drain(self,timeout=8):
        deadline=time.monotonic()+timeout
        with self.activity:
            while self.active and time.monotonic()<deadline:self.activity.wait(min(.1,deadline-time.monotonic()))
            return self.active==0
