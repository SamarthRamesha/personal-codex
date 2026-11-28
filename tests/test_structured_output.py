"""Structured coding output needs a bounded code budget and honest truncation errors."""
import io
import json
import os
import unittest
from unittest.mock import MagicMock,patch
from app import providers,server,network_policy

class Response(io.BytesIO):
    status=200

class StructuredOutputTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'PERSONAL_CODEX_INFERENCE_POLICY':'offline'});self.env.start();self.addCleanup(self.env.stop)
        self.request={'kind':'ollama','endpoint':network_policy.OLLAMA_ENDPOINT,'model':network_policy.OFFLINE_MODELS[0],'prompt':'synthetic coding fixture','cloud_allowed':False}

    def test_coding_budget_is_larger_and_chat_remains_bounded(self):
        with patch.object(providers,'post_json',return_value={}):
            plain=providers._ollama_payload(self.request,stream=False)
            structured=providers._ollama_payload({**self.request,'json_output':True},stream=True)
        self.assertEqual(plain['options']['num_predict'],768)
        self.assertEqual(structured['options']['num_predict'],2048)
        self.assertEqual(structured['format'],'json')
        self.assertFalse(structured['think'])

    def test_truncated_nonstream_proposal_is_rejected_before_tools(self):
        with patch.object(providers,'post_json',side_effect=[{}, {'done_reason':'length','message':{'content':'{"operations":['}}]):
            with self.assertRaisesRegex(providers.ProviderTransportError,'token limit'):
                providers.OllamaTransport()({**self.request,'json_output':True})

    def test_truncated_stream_is_not_accepted_as_a_complete_proposal(self):
        response=Response((json.dumps({'message':{'content':'{"operations":['},'done':True,'done_reason':'length'})+'\n').encode())
        connection=MagicMock();connection.sock=None;connection.getresponse.return_value=response
        with patch.object(providers,'post_json',return_value={}),patch.object(providers,'HTTPConnection',return_value=connection):
            with self.assertRaisesRegex(providers.ProviderTransportError,'token limit'):
                providers.OllamaStreamTransport()({**self.request,'json_output':True})
        connection.close.assert_called()

    def test_nonstream_round_keeps_structured_output_contract(self):
        captured=[]
        def transport(request):captured.append(request);return {'text':'{}'}
        with patch.object(server,'STREAM_PROVIDER',False),patch.object(providers,'transport_for',return_value=transport):
            server.round_transport(self.request)(self.request)
        self.assertTrue(captured[0].get('json_output'))

if __name__=='__main__':unittest.main()
