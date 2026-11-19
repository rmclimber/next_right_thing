"""Versioned text representation and provider-independent semantic relevance."""

import json
import math
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
from importlib import import_module
from typing import Protocol

MODEL_ID = "amazon.titan-embed-text-v2:0"
DIMENSIONS = 256
MODEL_KEY = f"bedrock:{MODEL_ID}:{DIMENSIONS}:text-v1"
MAX_TEXT_CHARACTERS = 4000


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden_depth += 1
        self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden_depth = max(0, self.hidden_depth - 1)
        self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden_depth:
            self.parts.append(data)


def embedding_text(subject: dict, kind: str) -> str:
    if kind not in {"content_item", "goal"}:
        raise ValueError("Unknown embedding subject kind")
    detail = "summary" if kind == "content_item" else "description"
    parser = _PlainText()
    parser.feed(f"{subject['title']}\n{subject.get(detail) or ''}")
    parser.close()
    return " ".join(unescape("".join(parser.parts)).split())[:MAX_TEXT_CHARACTERS]


def text_hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def validated_vector(value, dimensions=DIMENSIONS) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != dimensions:
        raise ValueError("Invalid embedding dimensions")
    if any(isinstance(entry, bool) or not isinstance(entry, (int, float)) for entry in value):
        raise ValueError("Embedding must contain numbers")
    try:
        vector = [float(entry) for entry in value]
    except OverflowError as error:
        raise ValueError("Embedding values exceed floating point range") from error
    if not all(math.isfinite(entry) for entry in vector):
        raise ValueError("Embedding must be finite and nonzero")
    scale = max(abs(entry) for entry in vector)
    if scale == 0:
        raise ValueError("Embedding must be finite and nonzero")
    scaled = [entry / scale for entry in vector]
    norm = math.hypot(*scaled)
    return [entry / norm for entry in scaled]


class TitanEmbeddingProvider:
    """Only instantiated by batch tooling, never by recommendation requests."""

    def __init__(self, client=None):
        if client is None:
            config = import_module("botocore.config").Config(
                connect_timeout=3, read_timeout=15, retries={"max_attempts": 1},
            )
            client = import_module("boto3").client("bedrock-runtime", config=config)
        self.client = client

    def embed(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("Cannot embed empty text")
        response = self.client.invoke_model(
            modelId=MODEL_ID, contentType="application/json", accept="application/json",
            body=json.dumps({"inputText": text, "dimensions": DIMENSIONS, "normalize": True}),
        )
        body = response["body"]
        try:
            return validated_vector(json.loads(body.read())["embedding"])
        finally:
            body.close()


def semantic_relevances(content_items: list[dict], goals: list[dict], embeddings: dict) -> dict:
    """Require complete current coverage; callers fall back as a whole on ValueError."""
    if not goals:
        raise ValueError("No active Goals")

    def vector(subject, kind):
        text = embedding_text(subject, kind)
        if not text:
            raise ValueError("Embedding text must be nonempty")
        cached = embeddings.get((kind, str(subject["id"])))
        if not cached or cached["text_hash"] != text_hash(text):
            raise ValueError("Missing or stale embedding")
        return validated_vector(cached["vector"])

    goal_vectors = [(goal["title"], vector(goal, "goal")) for goal in goals]
    result = {}
    for item in content_items:
        item_vector = vector(item, "content_item")
        best_score, best_title = 0.0, None
        for title, goal_vector in goal_vectors:
            similarity = max(0.0, min(1.0, math.fsum(a * b for a, b in zip(item_vector, goal_vector))))
            if similarity > best_score:
                best_score, best_title = similarity, title
        result[str(item["id"])] = (best_score, best_title)
    return result
