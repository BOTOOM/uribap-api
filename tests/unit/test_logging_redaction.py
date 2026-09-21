from uribap_api.infrastructure.logging import redact_sensitive


def test_redacts_sensitive_values_recursively() -> None:
    payload = {
        "authorization": "Bearer secret-token",
        "nested": {"password": "local-password", "safe": "value"},
        "items": [{"cookie": "session-value"}],
    }
    redacted = redact_sensitive(payload)
    assert redacted == {
        "authorization": "[REDACTED]",
        "nested": {"password": "[REDACTED]", "safe": "value"},
        "items": [{"cookie": "[REDACTED]"}],
    }
