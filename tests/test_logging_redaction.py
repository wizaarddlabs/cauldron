import logging

from app.logging_utils import RedactSecretsFilter, redact_secrets

CONFIG_ID = "0123456789abcdef0123456789abcdef"
INFO_HASH = "a" * 40


def test_redacts_api_keys_in_query_strings():
    text = "Client error for url 'https://api.example/x?token=SECRET&id=1&apikey=K2'"

    redacted = redact_secrets(text)

    assert "SECRET" not in redacted
    assert "K2" not in redacted
    assert "id=1" in redacted


def test_shortens_config_ids_but_not_info_hashes():
    text = f"GET /{CONFIG_ID}/playback/{INFO_HASH} HTTP/1.1"

    redacted = redact_secrets(text)

    assert CONFIG_ID not in redacted
    assert "/012345.../playback/" in redacted
    assert INFO_HASH in redacted


def test_filter_keeps_access_log_args_shape():
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("1.2.3.4:5", "GET", f"/{CONFIG_ID}/stream/movie/tt1.json", "1.1", 200),
        None,
    )

    assert RedactSecretsFilter().filter(record)

    assert isinstance(record.args, tuple)
    assert len(record.args) == 5
    assert CONFIG_ID not in record.getMessage()


def test_filter_redacts_exception_args():
    record = logging.LogRecord(
        "app",
        logging.ERROR,
        __file__,
        1,
        "failed: %s",
        (ValueError("bad url https://x/?apikey=SECRET"),),
        None,
    )

    RedactSecretsFilter().filter(record)

    assert "SECRET" not in record.getMessage()
