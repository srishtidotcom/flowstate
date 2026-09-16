import json

import httpx
import pytest

from backend.extraction.extractor import (
    SYSTEM_PROMPT,
    ExtractionError,
    extract_tasks,
)
from backend.preprocessing.normalizer import Chunk


class FakeResponse:
    def __init__(self, content=None, *, payload=None, status_code=200):
        self._payload = payload or {"message": {"content": content}}
        self.status_code = status_code
        self.request = httpx.Request("POST", "http://ollama.test/api/chat")

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error",
                request=self.request,
                response=httpx.Response(self.status_code, request=self.request),
            )


def _chunk():
    return Chunk(
        text="Priya will submit the budget by EOD Friday.",
        speaker="Asha",
        source_ref="chat.txt:7",
    )


def _valid_item(**overrides):
    item = {
        "title": "Submit the budget",
        "owner": "Priya",
        "deadline": "by EOD Friday",
        "confidence": 0.97,
        "dependencies": [],
        "source_ref": "chat.txt:7",
    }
    item.update(overrides)
    return item


def test_prompt_has_schema_json_only_instruction_and_four_required_examples():
    assert "Return JSON only" in SYSTEM_PROMPT
    assert SYSTEM_PROMPT.count("Input:") >= 4
    assert '"owner":null' in SYSTEM_PROMPT
    assert "by EOD Friday" in SYSTEM_PROMPT
    assert '"minimum": 0.0' in SYSTEM_PROMPT
    assert '"maximum": 1.0' in SYSTEM_PROMPT


def test_valid_response_is_bound_to_exact_source_text():
    calls = []

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeResponse(json.dumps([_valid_item()]))

    tasks = extract_tasks([_chunk()], post=post)

    assert len(tasks) == 1
    assert tasks[0].source_ref == "chat.txt:7"
    assert tasks[0].source_snippet == _chunk().text
    assert tasks[0].confidence == 0.97
    assert calls[0][1]["json"]["format"]["type"] == "array"


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("not json", "malformed JSON"),
        (json.dumps([{"title": "Missing fields"}]), "violated the task schema"),
        (json.dumps([_valid_item(dependencies="none")]), "violated the task schema"),
        (json.dumps([_valid_item(confidence=-0.1)]), "violated the task schema"),
        (json.dumps([_valid_item(confidence=1.1)]), "violated the task schema"),
        (json.dumps([_valid_item(source_ref="invented:99")]), "unknown source_ref"),
    ],
)
def test_invalid_model_output_is_rejected(content, message):
    with pytest.raises(ExtractionError, match=message):
        extract_tasks([_chunk()], post=lambda *args, **kwargs: FakeResponse(content))


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        (
            httpx.ReadTimeout(
                "slow",
                request=httpx.Request("POST", "http://ollama.test"),
            ),
            "timed out",
        ),
        (
            httpx.ConnectError(
                "offline",
                request=httpx.Request("POST", "http://ollama.test"),
            ),
            "Could not connect",
        ),
    ],
)
def test_transport_failures_are_explicit(failure, message):
    def post(*args, **kwargs):
        raise failure

    with pytest.raises(ExtractionError, match=message):
        extract_tasks([_chunk()], post=post)


def test_http_and_envelope_failures_are_explicit():
    with pytest.raises(ExtractionError, match="HTTP 503"):
        extract_tasks(
            [_chunk()],
            post=lambda *args, **kwargs: FakeResponse(status_code=503),
        )

    with pytest.raises(ExtractionError, match="envelope was invalid"):
        extract_tasks(
            [_chunk()],
            post=lambda *args, **kwargs: FakeResponse(payload={"unexpected": True}),
        )


def test_one_bad_batch_fails_the_entire_extraction():
    chunks = [
        Chunk(text=f"Task {index}", source_ref=f"chat.txt:{index}")
        for index in range(1, 102)
    ]
    call_count = 0

    def post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return FakeResponse(json.dumps([]))
        return FakeResponse("bad second batch")

    with pytest.raises(ExtractionError, match="malformed JSON"):
        extract_tasks(chunks, post=post)
    assert call_count == 2
