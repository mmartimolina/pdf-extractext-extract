import asyncio
import json
import urllib.error
from unittest.mock import MagicMock

import pytest

from src.consul import ConsulRegistration


@pytest.fixture
def registration(monkeypatch):
    monkeypatch.setenv("CONSUL_HTTP_ADDR", "http://localhost:8500/")
    monkeypatch.setenv("SERVICE_ADDRESS", "172.20.0.2")
    monkeypatch.delenv("CONSUL_SERVICE_ID", raising=False)
    return ConsulRegistration("extract", 8000, "/health")


def test_registration_configuration(registration):
    assert registration.address == "http://localhost:8500"
    assert registration.service_name == "extract"
    assert registration.service_id.startswith("extract-")
    assert registration.service_address == "172.20.0.2"
    assert registration.port == 8000
    assert registration.health_path == "/health"
    assert registration.enabled is True
    assert registration.registered is False


def test_registration_disabled(monkeypatch):
    monkeypatch.delenv("CONSUL_HTTP_ADDR", raising=False)
    instance = ConsulRegistration("extract", 8000, "/health")

    asyncio.run(instance.register())

    assert instance.enabled is False
    assert instance.registered is False


def test_register_success(registration, monkeypatch):
    calls = []

    def fake_request(method, path, payload):
        calls.append((method, path, payload))

    monkeypatch.setattr(registration, "_request", fake_request)

    asyncio.run(registration.register())

    assert registration.registered is True
    assert len(calls) == 1

    method, path, payload = calls[0]
    assert method == "PUT"
    assert path == "/v1/agent/service/register"
    assert payload["ID"] == registration.service_id
    assert payload["Name"] == "extract"
    assert payload["Address"] == "172.20.0.2"
    assert payload["Port"] == 8000
    assert payload["Check"]["HTTP"] == "http://172.20.0.2:8000/health"
    assert payload["Check"]["Interval"] == "10s"


def test_register_failure_is_fail_soft(registration, monkeypatch, caplog):
    def fake_request(method, path, payload):
        raise RuntimeError("Consul unavailable")

    monkeypatch.setattr(registration, "_request", fake_request)
    monkeypatch.setattr("src.consul.REGISTER_ATTEMPTS", 2)
    monkeypatch.setattr("src.consul.REGISTER_RETRY_SECONDS", 0)

    asyncio.run(registration.register())

    assert registration.registered is False
    assert "consul_service_registration_failed" in caplog.text


def test_register_retries_until_success(registration, monkeypatch):
    calls = []
    attempts = []

    def flaky_request(method, path, payload):
        attempts.append(method)
        if len(attempts) < 3:
            raise RuntimeError("Consul unavailable")
        calls.append((method, path, payload))

    monkeypatch.setattr(registration, "_request", flaky_request)
    monkeypatch.setattr("src.consul.REGISTER_RETRY_SECONDS", 0)

    asyncio.run(registration.register())

    assert registration.registered is True
    assert len(attempts) == 3
    assert len(calls) == 1


def test_register_gives_up_after_max_attempts(registration, monkeypatch):
    attempts = []

    def failing_request(method, path, payload):
        attempts.append(method)
        raise RuntimeError("Consul unavailable")

    monkeypatch.setattr(registration, "_request", failing_request)
    monkeypatch.setattr("src.consul.REGISTER_ATTEMPTS", 2)
    monkeypatch.setattr("src.consul.REGISTER_RETRY_SECONDS", 0)

    asyncio.run(registration.register())

    assert registration.registered is False
    assert len(attempts) == 2


def test_acl_token_is_optional(monkeypatch):
    monkeypatch.setenv("CONSUL_HTTP_ADDR", "http://localhost:8500")
    instance = ConsulRegistration("extract", 8000, "/health")
    assert instance.acl_token == ""

    monkeypatch.setenv("CONSUL_ACL_TOKEN", "test-token")
    instance = ConsulRegistration("extract", 8000, "/health")
    assert instance.acl_token == "test-token"


def test_deregister_does_nothing_when_not_registered(registration, monkeypatch):
    def unexpected_request(*args):
        pytest.fail("No debería enviar una solicitud")

    monkeypatch.setattr(registration, "_request", unexpected_request)

    asyncio.run(registration.deregister())

    assert registration.registered is False


def test_deregister_success(registration, monkeypatch):
    calls = []
    registration.registered = True

    def fake_request(method, path, payload):
        calls.append((method, path, payload))

    monkeypatch.setattr(registration, "_request", fake_request)

    asyncio.run(registration.deregister())

    assert calls == [
        (
            "PUT",
            f"/v1/agent/service/deregister/{registration.service_id}",
            None,
        )
    ]


def test_deregister_failure_is_fail_soft(registration, monkeypatch, caplog):
    registration.registered = True

    def fake_request(method, path, payload):
        raise RuntimeError("Consul unavailable")

    monkeypatch.setattr(registration, "_request", fake_request)

    asyncio.run(registration.deregister())

    assert "consul_service_deregister_failed" in caplog.text


def test_http_request_sends_json_payload(registration, monkeypatch):
    response = MagicMock()
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return response

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    payload = {"Name": "extract", "Port": 8000}
    registration._request("PUT", "/register", payload)

    request = captured["request"]
    assert request.full_url == "http://localhost:8500/register"
    assert request.method == "PUT"
    assert json.loads(request.data.decode()) == payload
    assert request.get_header("Content-type") == "application/json"
    assert request.get_header("X-consul-token") is None
    assert captured["timeout"] == 3


def test_http_request_sends_acl_token(monkeypatch):
    monkeypatch.setenv("CONSUL_HTTP_ADDR", "http://localhost:8500")
    monkeypatch.setenv("CONSUL_ACL_TOKEN", "test-token")
    registration = ConsulRegistration("extract", 8000, "/health")

    response = MagicMock()
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        return response

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    registration._request("PUT", "/register", None)

    assert captured["request"].get_header("X-consul-token") == "test-token"


def test_http_request_without_payload(registration, monkeypatch):
    response = MagicMock()
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        return response

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    registration._request("PUT", "/deregister", None)

    assert captured["request"].data is None


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.URLError("connection refused"),
        TimeoutError("request timed out"),
    ],
)
def test_http_request_translates_connection_errors(registration, monkeypatch, error):
    def fake_urlopen(request, timeout):
        raise error

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(RuntimeError, match="Consul no disponible"):
        registration._request("PUT", "/register", None)
