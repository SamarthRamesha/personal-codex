"""Deployment egress boundaries. Kernel test is explicit Linux-only, never mocked as proof."""
import errno
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import unittest
from unittest.mock import Mock,patch
from app import network_policy as policy,server,conversations


class WorkerOnlyTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'PERSONAL_CODEX_INFERENCE_POLICY':'worker-only'});self.env.start();self.addCleanup(self.env.stop)
    def test_direct_providers_rejected_before_transport_factory_even_with_cloud_consent(self):
        with patch.object(server.providers,'transport_for') as factory:
            for kind,endpoint,cloud in [('ollama','http://127.0.0.1:11434',False),('ollama','http://192.0.2.1',True),('openai-compatible','https://example.invalid',True),('respan-gateway','',False)]:
                row={'kind':kind,'endpoint':endpoint,'cloud_allowed':cloud}
                for resolver in (server.active_provider_transport,server.round_transport,conversations.transport_for):
                    with self.assertRaisesRegex(ValueError,'only endpoint-free'):resolver(row)
                with self.assertRaises(ValueError):server.validate_provider_config(kind,endpoint,'fixture','',cloud)
            factory.assert_not_called()
    def test_stored_provider_cannot_trigger_model_discovery(self):
        store=Mock();store.one.return_value={'kind':'ollama','endpoint':'http://127.0.0.1:11434','model':'old','enabled':1}
        with patch.object(conversations.providers,'discover_models') as discover:
            with self.assertRaises(ValueError):conversations.resolve_provider(store,{'provider_id':'fixture','model':'different'},None)
            discover.assert_not_called()
    def test_injected_provider_rejected_before_message_or_thread(self):
        store=Mock()
        with patch.object(conversations.threading,'Thread') as thread:
            with self.assertRaises(ValueError):conversations._start_turn(store,{},'hello',provider={'kind':'ollama'})
            store.write.assert_not_called();thread.assert_not_called()
    def test_worker_requires_empty_network_metadata_and_development_keeps_local_provider(self):
        self.assertEqual(server.validate_provider_config('mac-worker','','fixture','',False)['kind'],'mac-worker')
        for key,value in [('endpoint','http://127.0.0.1'),('secret_ref','KEY'),('cloud_allowed',True)]:
            with self.assertRaises(ValueError):policy.require_provider({'kind':'mac-worker',key:value})
        with patch.dict(os.environ,{'PERSONAL_CODEX_INFERENCE_POLICY':'development'}):
            self.assertEqual(server.validate_provider_config('ollama','http://127.0.0.1:11434','fixture','',False)['kind'],'ollama')
    def test_production_requires_guard_and_invalid_configs_never_install(self):
        with patch.object(policy,'install') as install:
            with self.assertRaises(ValueError):policy.configure('127.0.0.1','disabled',production=True)
            for host,mode in [('0.0.0.0','disabled'),('127.0.0.1','development')]:
                with patch.dict(os.environ,{'PERSONAL_CODEX_DENY_CONNECT':'1'}):
                    with self.assertRaises(ValueError):policy.configure(host,mode)
            install.assert_not_called()
            with patch.dict(os.environ,{'PERSONAL_CODEX_DENY_CONNECT':'1'}):policy.configure('127.0.0.1','disabled',production=True)
            install.assert_called_once()



class OfflineProviderTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"PERSONAL_CODEX_INFERENCE_POLICY": "offline"})
        env.start()
        self.addCleanup(env.stop)
        self.row = {"kind": "ollama", "endpoint": policy.OLLAMA_ENDPOINT, "model": policy.OFFLINE_MODELS[0]}

    def test_launcher_inventory_filters_saved_provider_rows(self):
        first, second = policy.OFFLINE_MODELS
        with patch.dict(os.environ, {"PERSONAL_CODEX_INSTALLED_OFFLINE_MODELS": second,
                                     "PERSONAL_CODEX_OFFLINE_MODEL": second}):
            self.assertEqual(policy.offline_models(), (second,))
            self.assertFalse(policy.provider_allowed({**self.row, "model": first}))
            self.assertTrue(policy.provider_allowed({**self.row, "model": second}))

    def test_offline_policy_requires_exact_endpoint_and_configured_tag_before_transport(self):
        for alternate in (
            {"endpoint": "http://localhost:11434"},
            {"endpoint": policy.OLLAMA_ENDPOINT + "/api/generate"},
            {"cloud_allowed": True},
            {"secret_ref": "SECRET"},
            {"kind": "mac-worker"},
            {"kind": "respan-gateway"},
            {"model": "cloud-model:cloud"},
        ):
            with self.subTest(alternate=alternate), patch.object(server.providers, "post_json") as post:
                row = {**self.row, **alternate}
                for resolver in (server.active_provider_transport, server.round_transport,
                                 conversations.transport_for, server.provider_approval_kind):
                    with self.assertRaisesRegex(ValueError, "Offline mode"):
                        resolver(row)
                with self.assertRaisesRegex(ValueError, "Offline mode"):
                    server.providers.OllamaTransport()(row)
                post.assert_not_called()

    def test_upstream_model_disallowed_and_local_generation_bounded(self):
        with patch.object(server.providers, "post_json") as post:
            post.return_value = {"remote_model": "synthetic-upstream"}
            with self.assertRaisesRegex(ValueError, "remote model"):
                server.providers.OllamaStreamTransport()({**self.row, "prompt": "hello"})
            post.assert_called_once_with(policy.OLLAMA_ENDPOINT, "/api/show", {"model": self.row["model"]}, timeout=5)
        with patch.object(server.providers, "post_json", side_effect=[{}, {"message": {"content": "hello"}}]) as post:
            server.providers.OllamaTransport()({**self.row, "prompt": "hello", "json_output": True})
            payload = post.call_args.args[2]
            self.assertEqual(payload["options"], {"num_ctx": 8192, "num_predict": 768, "temperature": 0.2})
            self.assertEqual(payload["format"], "json")
            self.assertIs(payload["think"], False)

    def test_offline_requires_loopback_and_preserves_worker_production_gate(self):
        with self.assertRaisesRegex(ValueError, "127.0.0.1"):
            policy.configure("0.0.0.0", "development")
        with self.assertRaisesRegex(ValueError, "Private Serve"):
            policy.configure("127.0.0.1", "disabled", production=True)
        policy.configure("127.0.0.1", "development")

def decision(nr,args=(),arch=0xc000003e):
    # Interpret standard classic-BPF instructions against syscall metadata. These
    # adversarial vectors are portable policy checks, not kernel enforcement proof.
    data=struct.pack('<iIQ6Q',nr,arch,0,*(tuple(args)+(0,)*6)[:6]);pc=0;acc=0;program=policy.filter_program()
    for _ in range(100):
        code,jt,jf,k=program[pc];pc+=1
        if code==0x20:acc=struct.unpack_from('<I',data,k)[0]
        elif code==0x15:pc+=jt if acc==k else jf
        elif code==0x35:pc+=jt if acc>=k else jf
        elif code==0x54:acc&=k
        elif code==0x06:return k
        else:raise AssertionError('Unsupported filter instruction')
    raise AssertionError('Filter did not terminate')


class FilterPolicyTests(unittest.TestCase):
    def test_connections_alternate_abis_io_uring_and_crossprocess_fd_routes_denied(self):
        for nr in (42,46,53,307,425,426,427,438,101,310,311,0x4000002a):self.assertEqual(decision(nr),policy.DENY,nr)
        self.assertEqual(decision(42,arch=0x40000003),policy.KILL)
    def test_only_tcp_stream_socket_creation_allowed_and_server_io_preserved(self):
        for family in (2,10):
            for flags in (1,1|0x80000,1|0x800):
                for proto in (0,6):self.assertEqual(decision(41,(family,flags,proto)),policy.ALLOW)
        for args in ((2,2,0),(10,2,17),(1,1,0),(17,3,0),(16,3,0),(2,1,132)):
            self.assertEqual(decision(41,args),policy.DENY,args)
        for nr in (0,1,3,43,44,49,50,51,52,232,288):self.assertEqual(decision(nr),policy.ALLOW,nr)
    def test_tcp_fast_open_and_destination_pointer_cannot_bypass_connect_denial(self):
        for args in ((1,0,1,0x20000000,0,0),(1,0,1,0,1,16),(1,0,1,0,1<<32,16)):
            self.assertEqual(decision(44,args),policy.DENY,args)
        self.assertEqual(decision(44,(1,0,1,0,0,0)),policy.ALLOW)
    def test_unsupported_platform_fails_without_installing_filter(self):
        with patch.object(policy,'supported',return_value=False):
            with self.assertRaisesRegex(ValueError,'Linux x86_64'):policy.install()


@unittest.skipUnless(policy.supported() and os.getenv('PERSONAL_CODEX_LINUX_NETWORK_TESTS')=='1','requires explicit disposable Linux x86_64 syscall test')
class LinuxNetworkTests(unittest.TestCase):
    def test_real_filter_inheritance_denials_and_inbound_http_survives(self):
        # Only a child is restricted; the unfiltered test parent connects to its
        # synthetic loopback server. No LAN/public destination or private file.
        code='''
import errno,json,os,socket,subprocess,sys
from app import network_policy
network_policy.install()
with socket.socket() as s:
 s.bind(('127.0.0.1',0));s.listen(1)
 print(json.dumps({'port':s.getsockname()[1],'policy':network_policy.status()}),flush=True)
 client,_=s.accept()
 with client:
  client.recv(1024);client.sendall(b'HTTP/1.1 200 OK\\r\\nContent-Length: 2\\r\\nConnection: close\\r\\n\\r\\nOK')
for family,kind in ((socket.AF_INET,socket.SOCK_DGRAM),(socket.AF_UNIX,socket.SOCK_STREAM)):
 try: s=socket.socket(family,kind)
 except PermissionError: pass
 else: s.close();raise AssertionError('unsafe socket allowed')
child="import errno,socket; s=socket.socket(); assert s.connect_ex(('127.0.0.1',1))==errno.EPERM"
subprocess.run([sys.executable,'-c',child],check=True)
print('network-denials-and-descendant-inheritance-passed',flush=True)
'''
        process=subprocess.Popen([sys.executable,'-B','-c',code],cwd=Path(__file__).resolve().parents[1],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            # Caller supplies a total test timeout via unittest process supervisor.
            first=json.loads(process.stdout.readline());self.assertTrue(first['policy']['outbound_connections_denied'])
            with socket.create_connection(('127.0.0.1',first['port']),timeout=3) as client:
                client.sendall(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n');self.assertIn(b'200 OK',client.recv(1024))
            output,error=process.communicate(timeout=5)
            self.assertEqual(process.returncode,0,error);self.assertIn('inheritance-passed',output)
        finally:
            if process.poll() is None:process.kill();process.communicate()
