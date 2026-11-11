"""
Logging helpers.

Several debrid providers (AllDebrid, TorBox, Premiumize) take the user's
API key as a query parameter, and httpx error messages include the full
request URL. :class:`RedactSecretsFilter` masks those parameters in every
log record so keys never reach log files.

It also shortens Stremio config IDs (32 hex characters) that appear as a
URL path segment, e.g. in uvicorn access logs: anyone holding a full
config ID can use the owner's debrid account.
"""

import logging
import re

_SECRET_QUERY_PARAM = re.compile(
    r"(?i)([?&](?:apikey|api_key|key|token|access_token|customer_id|pin)=)[^&\s'\"<>]+"
)


_CONFIG_ID_SEGMENT = re.compile(r"(?i)/([0-9a-f]{6})[0-9a-f]{26}(?=/|\s|$|[?'\"])")


def redact_secrets(text: str) -> str:
    text = _SECRET_QUERY_PARAM.sub(r"\1***", text)
    return _CONFIG_ID_SEGMENT.sub(r"/\1...", text)


def _redact_value(value: object) -> object:
    if isinstance(value, str):
        return redact_secrets(value)

    # Numbers keep their type so %d / %f format specifiers still work.
    if value is None or isinstance(value, bool | int | float):
        return value

    # Anything else (exceptions, httpx.URL, ...) is rendered with %s by the
    # caller, so check its text. httpx logs every request with the URL as an
    # httpx.URL object, and some providers put the API key in the query.
    text = str(value)
    redacted = redact_secrets(text)

    return redacted if redacted != text else value


class RedactSecretsFilter(logging.Filter):
    """
    Redact the message template and each argument separately, keeping
    ``record.args`` intact: uvicorn's access formatter unpacks it.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg)

        if isinstance(record.args, tuple):
            record.args = tuple(_redact_value(arg) for arg in record.args)
        elif isinstance(record.args, dict):
            record.args = {
                key: _redact_value(value) for key, value in record.args.items()
            }

        if record.exc_info and not record.exc_text:
            record.exc_text = redact_secrets(
                logging.Formatter().formatException(record.exc_info)
            )
        elif record.exc_text:
            record.exc_text = redact_secrets(record.exc_text)

        return True


def mask_config_id(config: str) -> str:
    """
    Shorten a config ID for logging.

    The config ID in an addon URL grants use of the owner's debrid
    account, so it must never be written to logs in full.
    """

    if len(config) <= 6:
        return "***"

    return f"{config[:6]}..."


def redact_value(value: object, *secrets: str | None) -> str:
    """
    Render ``value`` as text with any of ``secrets`` masked out.

    Provider errors (e.g. httpx status errors) often embed the request
    URL, which for some providers carries the API key as a query param.
    """

    text = str(value)

    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")

    return text


def install_redaction_filter() -> None:
    """
    Attach the redaction filter to the root handlers (covers app loggers,
    which propagate) and directly to uvicorn's loggers, which have their own
    non-propagating handlers.
    """
    redaction_filter = RedactSecretsFilter()

    for handler in logging.getLogger().handlers:
        if not any(isinstance(f, RedactSecretsFilter) for f in handler.filters):
            handler.addFilter(redaction_filter)

    for name in ("uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(name)
        if not any(isinstance(f, RedactSecretsFilter) for f in logger.filters):
            logger.addFilter(redaction_filter)
