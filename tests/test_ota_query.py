import base64
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from opkv import ota_query as oq

NEGOTIATION = "1615897067573"


def ctr(data, key, iv):
    c = Cipher(algorithms.AES(key), modes.CTR(iv)).encryptor()
    return c.update(data) + c.finalize()


def b64(data):
    return base64.b64encode(data).decode()


def der_b64(public_key):
    return b64(public_key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo))


@pytest.fixture
def ota_server(monkeypatch):
    """An OTA server that really decrypts the request (RSA-OAEP session key, AES-CTR body) and encrypts its answer.

    .state["reply"](request body) -> a dict (encrypted as the plaintext answer), bytes (sent as the raw response)
    or an int (a bare HTTP status); .seen lists (request headers, decrypted body, protectedKey entry).
    """
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    seen, state = [], {"reply": lambda body: {"components": []}}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            wrapped = json.loads(self.headers["protectedKey"])["SCENE_1"]
            oaep = padding.OAEP(mgf=padding.MGF1(hashes.SHA1()), algorithm=hashes.SHA1(), label=None)
            key = base64.b64decode(private.decrypt(base64.b64decode(wrapped["protectedKey"]), oaep))
            params = json.loads(request["params"])
            body = json.loads(ctr(base64.b64decode(params["cipher"]), key, base64.b64decode(params["iv"])))
            seen.append((self.headers, body, wrapped))
            reply = state["reply"](body)
            if isinstance(reply, int):
                self.send_response(reply)
                self.send_header("Content-Length", "0")
                return self.end_headers()
            if isinstance(reply, dict):
                iv = os.urandom(16)
                inner = {"cipher": b64(ctr(json.dumps(reply).encode(), key, iv)), "iv": b64(iv)}
                reply = json.dumps({"responseCode": 200, "body": json.dumps(inner)}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(reply)))
            self.end_headers()
            self.wfile.write(reply)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    # region EU is served by entry 3
    monkeypatch.setitem(oq.SERVERS, 3, (f"http://127.0.0.1:{srv.server_port}/update/v3", der_b64(private.public_key()), NEGOTIATION))
    srv.seen, srv.state = seen, state
    yield srv
    srv.shutdown()
    srv.server_close()
    thread.join()


def query(**kw):
    return oq.query(oq.Query("CPH2653EEA", "CPH2653", "EU", 6, **kw))


def test_request_is_encrypted_for_the_server_and_describes_a_device(ota_server):
    query(letter="C")
    headers, body, wrapped = ota_server.seen[0]
    assert body["otaVersion"] == "CPH2653NV44_11.C.01_0001_100001010000"
    assert (body["model"], body["productName"], body["trackRegion"], body["uRegion"], body["reqMode"]) == (
        "CPH2653EEA", "CPH2653EEA", "EU", "EU", "manual")
    assert (body["androidVersion"], body["colorOSVersion"], body["mode"]) == ("Android16.0", "ColorOS16", "0")
    assert (headers["version"], headers["mode"], wrapped["negotiationVersion"]) == ("2", "manual", NEGOTIATION)
    assert "imei" in body and set(body["imei"]) == {"0"}                      # no real device identifiers


def test_beta_flag_switches_the_request_mode(ota_server):
    query(beta=True, req_mode="taste")
    headers, body, _ = ota_server.seen[0]
    assert (body["mode"], body["reqMode"], headers["mode"]) == ("1", "taste", "taste")


def test_explicit_ota_version_replaces_the_generated_one(ota_server):
    query(ota_version="CPH2653_11.A.1_1_202501010000")
    assert ota_server.seen[0][1]["otaVersion"] == "CPH2653_11.A.1_1_202501010000"


def test_answer_is_decrypted_and_unwrapped(ota_server):
    ota_server.state["reply"] = lambda body: {"body": {"versionName": "CPH2653_16.0.0.210(EX01)", "components": []}}
    assert query()["versionName"] == "CPH2653_16.0.0.210(EX01)"


def test_answer_without_the_body_wrapper_is_taken_as_is(ota_server):
    ota_server.state["reply"] = lambda body: {"versionName": "V", "components": []}
    assert query()["versionName"] == "V"


def test_server_error_code_is_reported_with_its_message(ota_server):
    ota_server.state["reply"] = lambda body: json.dumps({"responseCode": 2004, "errMsg": "no update"}).encode()
    with pytest.raises(oq.OtaQueryError, match="server 2004: no update"):
        query()


def test_failed_check_is_reported(ota_server):
    ota_server.state["reply"] = lambda body: {"body": {"checkFailReason": "region mismatch"}}
    with pytest.raises(oq.OtaQueryError, match="check failed: region mismatch"):
        query()


def test_garbage_answer_is_a_decode_error(ota_server):
    ota_server.state["reply"] = lambda body: b"not json"
    with pytest.raises(oq.OtaQueryError, match="decode: JSONDecodeError"):
        query()


def test_http_failure_is_reported_without_the_url(ota_server):
    ota_server.state["reply"] = lambda body: 500
    with pytest.raises(oq.OtaQueryError, match=r"^http: HTTPError$"):
        query()


def test_server_key_that_is_not_rsa_is_refused(ota_server, monkeypatch):
    url = oq.SERVERS[3][0]
    monkeypatch.setitem(oq.SERVERS, 3, (url, der_b64(ec.generate_private_key(ec.SECP256R1()).public_key()), NEGOTIATION))
    with pytest.raises(oq.OtaQueryError, match="not an RSA key"):
        query()


def test_every_region_has_a_server():
    assert {oq.SERVER_CODE[server] for _, server in oq.REGIONS.values()} <= set(oq.SERVERS)


@pytest.mark.parametrize("group,rui", [
    ("Android 17", 7), ("Android 16", 6), ("Android 15", 6), ("Android 14", 5), ("Android 13", 4), ("Android 12", 3),
    ("Android 11", 2), ("Android 10", 1), ("ColorOS 15", 6), ("ColorOS 14", 5), ("ColorOS 8", 6), ("ColorOS 7", 1),
    ("Realme UI 3", 3), ("RUI 9", 7), ("Realme UI 0", 1), ("android 16", 6), ("OxygenOS", 6)])
def test_rui_from_the_firmware_group_name(group, rui):
    assert oq.rui_from_group(group) == rui


def test_firmware_version_string():
    assert oq.firmware_version("CPH2653", "NV44", "C") == "CPH2653NV44_11.C.01_0001_100001010000"


def test_components_are_normalised():
    root = {"versionName": "V", "realOtaVersion": "R", "securityPatch": "2026-10-05",
            "components": [{"componentPackets": {"manualUrl": "https://a.example/x.zip?p=1\n&q=2 ", "url": "https://b.example/y.zip",
                                                 "md5": "m", "size": "5000"}},
                           {"componentPackets": {"url": "https://c.example/z.zip"}}, {"componentPackets": {}}, {}]}
    got = oq.components(root)
    assert [c["source_url"] for c in got] == ["https://a.example/x.zip?p=1&q=2", "https://c.example/z.zip"]
    assert (got[0]["version"], got[0]["ota_version"], got[0]["md5"], got[0]["size"], got[0]["security_patch"]) == (
        "V", "R", "m", 5000, "2026-10-05")
    assert (got[1]["md5"], got[1]["size"]) == ("", 0)


def test_components_fall_back_to_the_component_version():
    got = oq.components({"components": [{"componentVersion": "CV", "componentPackets": {"url": "https://a.example/x.zip"}}]})
    assert (got[0]["version"], got[0]["ota_version"], got[0]["security_patch"]) == ("CV", "CV", "")


def test_answer_without_components_gives_nothing():
    assert oq.components({}) == [] and oq.components({"components": None}) == []
