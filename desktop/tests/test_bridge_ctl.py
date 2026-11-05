"""Real authenticated Unix-socket reuse; no SSH or deployment mutations."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import socketserver
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('desktop_ctl',Path(__file__).parents[1]/'scripts/desktop_bridge_ctl.py')
ctl=importlib.util.module_from_spec(spec);spec.loader.exec_module(ctl)

@unittest.skipUnless(hasattr(socketserver,'UnixStreamServer'),'Runs on the Linux bridge host')
class ExistingBridge(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);ctl.ROOT=root;ctl.SYSTEM=root;ctl.MCP=root/'untouched-mcp.json'
        self.token='a'*64;self.endpoint_token=self.token;self.import_tool=True
        self.secret=root/'desktop-bridge-token';self.secret.write_text(self.token)
        fixture=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*a):pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                good=self.headers.get('Authorization')=='Bearer '+fixture.endpoint_token
                value={'jsonrpc':'2.0','id':body['id'],'result':{'tools':[{'name':'project_import'}] if fixture.import_tool else []}}
                data=json.dumps(value).encode();self.send_response(200 if good else 401)
                self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        class UnixServer(socketserver.ThreadingMixIn,socketserver.UnixStreamServer):
            daemon_threads=True
        self.server=UnixServer(str(root/'desktop-bridge.sock'),Handler)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
    def enroll(self,token):
        output=io.StringIO()
        with patch('sys.stdin',io.StringIO(json.dumps({'token':token}))),contextlib.redirect_stdout(output):ctl.enroll()
        return json.loads(output.getvalue())
    def test_existing_same_device_is_idempotent(self):
        first=self.enroll(self.token);second=self.enroll(self.token)
        self.assertTrue(first['reused'] and second['reused'])
        self.assertEqual(self.secret.read_text(),self.token)
        self.assertFalse(ctl.MCP.exists())
    def test_other_device_is_not_replaced(self):
        with self.assertRaises(ctl.BridgeConflict):self.enroll('b'*64)
        self.assertEqual(self.secret.read_text(),self.token)
    def test_matching_file_without_endpoint_auth_is_not_reused(self):
        self.endpoint_token='b'*64
        with self.assertRaises(ctl.BridgeConflict):self.enroll(self.token)
    def test_old_tool_catalog_is_not_accepted(self):
        self.import_tool=False
        with self.assertRaises(ctl.BridgeConflict):self.enroll(self.token)

if __name__=='__main__':unittest.main()
