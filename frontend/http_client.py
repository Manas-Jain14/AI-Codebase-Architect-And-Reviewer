from __future__ import annotations

import email.utils
import random
import re
import time
from datetime import datetime, timezone

import requests


GET_MAX_RETRIES = 2
GET_MAX_TOTAL_WAIT_SECONDS = 5.0
GET_BACKOFF_BASE_SECONDS = 0.5
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _safe_detail(value: object) -> str:
    detail = str(value)
    detail = re.sub(r"https?://[^\s'\"<>]+", "[backend URL]", detail)
    detail = re.sub(
        r"(?i)\b(authorization|password|secret|token|api[_-]?key)\b\s*[:=]\s*[^\s,;]+",
        r"\1=[redacted]",
        detail,
    )
    return detail[:240]


def _retry_after_seconds(response: requests.Response) -> float | None:
    value = response.headers.get("Retry-After", "").strip()
    if not value:
        return None

    if re.fullmatch(r"[0-9]+", value):
        return float(int(value))

    try:
        retry_at = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None

    if retry_at is None:
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)
    return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())


def _backoff_seconds(retry_number: int, remaining_wait: float) -> float:
    maximum = min(GET_BACKOFF_BASE_SECONDS * (2**retry_number), remaining_wait)
    return random.uniform(0.0, maximum)


def get_with_retries(
    url: str,
    *,
    timeout: float,
    allowed_statuses: frozenset[int] = frozenset(),
) -> requests.Response:
    waited = 0.0

    for retry_number in range(GET_MAX_RETRIES + 1):
        try:
            response = requests.get(url, timeout=timeout)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if retry_number >= GET_MAX_RETRIES:
                raise
            remaining_wait = GET_MAX_TOTAL_WAIT_SECONDS - waited
            if remaining_wait <= 0:
                raise
            delay = _backoff_seconds(retry_number, remaining_wait)
            time.sleep(delay)
            waited += delay
            continue

        if response.status_code not in RETRYABLE_STATUS_CODES or retry_number >= GET_MAX_RETRIES:
            if response.status_code not in allowed_statuses:
                response.raise_for_status()
            return response

        remaining_wait = GET_MAX_TOTAL_WAIT_SECONDS - waited
        if remaining_wait <= 0:
            response.raise_for_status()

        retry_after = (
            _retry_after_seconds(response)
            if response.status_code in {429, 503}
            else None
        )
        if retry_after is not None:
            if retry_after > remaining_wait:
                response.raise_for_status()
            delay = retry_after
        else:
            delay = _backoff_seconds(retry_number, remaining_wait)

        time.sleep(delay)
        waited += delay

    raise RuntimeError("GET retry loop exited unexpectedly")


def upload_zip(url: str, file_name: str, file_bytes: bytes) -> dict:
    response = requests.post(
        url,
        files={"file": (file_name, file_bytes, "application/zip")},
        timeout=300,
    )
    response.raise_for_status()
    return response.json()


def format_request_error(action: str, error: Exception) -> str:
    if isinstance(error, requests.exceptions.HTTPError) and error.response is not None:
        response = error.response
        if response.status_code == 429:
            retry_after = _retry_after_seconds(response)
            message = f"{action}: the backend is temporarily rate-limiting requests (HTTP 429)."
            if retry_after is not None:
                message += f" Retry-After: {response.headers.get('Retry-After')}."
            return message

        reason = _safe_detail(response.reason or "HTTP error")
        return f"{action}: the backend returned HTTP {response.status_code} ({reason})."

    if isinstance(error, requests.exceptions.RequestException):
        return f"{action}: {type(error).__name__}: {_safe_detail(error)}"

    return f"{action}: {type(error).__name__}: {_safe_detail(error)}"
