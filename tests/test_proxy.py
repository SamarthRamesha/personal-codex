"""Serve HTTP-backend policy: exact authority, loopback-only trust, no auth bypass."""
import json
import os
import unittest
from email.message import Message
from unittest.mock import patch
from app import security
import test_security as fixture

ORIGIN='https://backend.example.ts.net'


def headers(**fields):
    result=Message()
    for name,value in fields.items():result[name.replace('_','-')]=value
    return result


class ProxyPolicyTests(unittest.TestCase):
    def test_configuration_requires_explicit_private_origin_auth_and_loopback(self):
        for origin in ('http://backend.example.ts.net','https://example.com','https://u:p@host.ts.net','https://host.ts.net/path','https://host.ts.net/?q=x','https://host.ts.net/#x'):
            with self.assertRaises(ValueError):security.public_origin(origin)
        self.assertEqual(security.public_origin(ORIGIN+':443/'),ORIGIN)
        for host,auth,tls in [('0.0.0.0',True,False),('100.100.100.100',True,False),('127.0.0.1',False,False),('127.0.0.1',True,True)]:
            with self.assertRaises(ValueError):security.validate_proxy_config(host,auth,tls,ORIGIN)
        security.validate_proxy_config('127.0.0.1',True,False,ORIGIN)

    def test_exact_serve_headers_produce_secure_context_only_from_loopback(self):
        fields=headers(Host='backend.example.ts.net',Origin=ORIGIN,X_Forwarded_Host='backend.example.ts.net',X_Forwarded_Proto='https',X_Forwarded_For='100.100.100.101')
        self.assertEqual(security.request_boundary(fields,'127.0.0.1',8787,'127.0.0.1',origin=ORIGIN),(True,None))
        for peer in ('100.100.100.101','192.168.1.2'):
            self.assertIsNotNone(security.request_boundary(fields,'127.0.0.1',8787,peer,origin=ORIGIN)[1])
        self.assertIsNotNone(security.request_boundary(fields,'127.0.0.1',8787,'127.0.0.1')[1])

    def test_wrong_and_duplicated_proxy_headers_are_not_trusted(self):
        for field,value in [('Host','evil.ts.net'),('Origin','https://evil.ts.net'),('X-Forwarded-Proto','http'),('X-Forwarded-Host','evil.ts.net'),('Forwarded','proto=https')]:
            fields=headers(Host='backend.example.ts.net',Origin=ORIGIN,X_Forwarded_Host='backend.example.ts.net',X_Forwarded_Proto='https')
            if field in fields:fields.replace_header(field,value)
            else:fields[field]=value
            self.assertIsNotNone(security.request_boundary(fields,'127.0.0.1',8787,'127.0.0.1',origin=ORIGIN)[1],field)
        fields=headers(Host='backend.example.ts.net',X_Forwarded_Host='backend.example.ts.net',X_Forwarded_Proto='https')
        fields['X-Forwarded-Proto']='https'
        self.assertIsNotNone(security.request_boundary(fields,'127.0.0.1',8787,'127.0.0.1',origin=ORIGIN)[1])

    def test_local_diagnostic_does_not_inherit_proxy_cookie_security(self):
        self.assertEqual(security.request_boundary(headers(Host='localhost:8787'),'127.0.0.1',8787,'127.0.0.1',origin=ORIGIN),(False,None))


@unittest.skipUnless(os.getenv("PERSONAL_CODEX_HTTP_TESTS")=="1","requires explicitly enabled loopback listener")
class ServeHttpTests(unittest.TestCase):
    tearDown = fixture.AuthHttpTests.tearDown
    request = fixture.AuthHttpTests.request
    # Reuse fixture mechanics, not inherited test discovery (the parent already covers auth independently).
    def setUp(self):
        fixture.AuthHttpTests.setUp(self)
        self.policy=patch.dict(os.environ,{'PERSONAL_CODEX_PUBLIC_ORIGIN':ORIGIN});self.policy.start()
        self.addCleanup(self.policy.stop)

    def test_serve_contract_keeps_bearer_auth_and_secure_cookie(self):
        proxy={'Host':'backend.example.ts.net','X-Forwarded-Host':'backend.example.ts.net','X-Forwarded-Proto':'https','Origin':ORIGIN}
        self.assertEqual(self.request('GET','/api/connection',headers=proxy)[0],401)
        status,_,body=self.request('GET','/api/connection',headers={**proxy,'Authorization':'Bearer '+self.token})
        self.assertEqual(status,200);self.assertTrue(json.loads(body)['secure_transport'])
        status,response,_=self.request('POST','/api/session',{'token':self.token},proxy)
        self.assertEqual(status,200);self.assertIn('; Secure',response['Set-Cookie'])
        cookie=response['Set-Cookie'].split(';')[0]
        self.assertEqual(self.request('GET','/api/projects',headers={**proxy,'Cookie':cookie})[0],200)
        self.assertEqual(self.request('POST','/api/conversations',{}, {**proxy,'Cookie':cookie,'Origin':'https://evil.ts.net'})[0],403)
