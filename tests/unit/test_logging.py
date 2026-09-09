import logging

from uribap_api.infrastructure.logging import JsonFormatter, _request_id


def test_json_log_formatter_includes_request_id_without_sensitive_headers() -> None:
    token = _request_id.set("req_test")
    try:
        record = logging.LogRecord("test", logging.INFO, __file__, 1, "safe message", (), None)
        payload = JsonFormatter().format(record)
    finally:
        _request_id.reset(token)

    assert '"requestId": "req_test"' in payload
    assert "Authorization" not in payload
