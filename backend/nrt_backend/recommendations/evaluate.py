"""Compare frozen, already eligible selection pools without writing events or calling providers."""

import argparse
import json
import math
from datetime import datetime
from pathlib import Path

from nrt_backend.recommendations.candidates import candidate_from_content_item
from nrt_backend.recommendations.embeddings import (
    DIMENSIONS,
    MODEL_KEY,
    embedding_text,
    semantic_relevances,
    text_hash,
)
from nrt_backend.recommendations.scoring import ranked, score_candidate


def _ndcg(ids, labels, k=3):
    def dcg(grades):
        return sum((2 ** grade - 1) / math.log2(index + 2) for index, grade in enumerate(grades))
    ideal = dcg(sorted(labels.values(), reverse=True)[:k])
    return dcg([labels[item_id] for item_id in ids[:k]]) / ideal if ideal else 0.0


def evaluate(document):
    synthetic = document.get("synthetic", False)
    if type(synthetic) is not bool:
        raise ValueError("synthetic must be a boolean")
    if not synthetic and document.get("model_key") != MODEL_KEY:
        raise ValueError("Real evaluation requires the current model/representation key")
    rows = []
    for case in document["cases"]:
        if type(case["available_minutes"]) is not int or not 1 <= case["available_minutes"] <= 240:
            raise ValueError("available_minutes must be between 1 and 240")
        now = datetime.fromisoformat(case["now"])
        if now.tzinfo is None:
            raise ValueError("Evaluation time must include timezone")
        items = []
        for raw in case["content_items"]:
            item = {"content_type": "article", "duration_minutes": None, "summary": None,
                    "url": "https://example.com/evaluation", "content_source": {}, **raw}
            for field in ("published_at", "discovered_at", "created_at"):
                value = item.get(field, case["now"])
                item[field] = datetime.fromisoformat(value) if value else None
                if item[field] is None and field != "published_at":
                    raise ValueError(f"{field} is required")
                if item[field] is not None and item[field].utcoffset() is None:
                    raise ValueError(f"{field} must include timezone")
            items.append(item)
        if not items or len(items) > 50:
            raise ValueError("Expected a frozen selection pool of 1..50 items")
        goals = case["goals"]
        for subjects in (items, goals):
            ids = [subject.get("id") for subject in subjects]
            if any(not isinstance(subject_id, str) or not subject_id for subject_id in ids) or len(set(ids)) != len(ids):
                raise ValueError("Subject IDs must be nonempty unique strings")
        for item in items:
            duration = item["duration_minutes"]
            if duration is not None and (type(duration) is not int or duration <= 0):
                raise ValueError("Known duration must be a positive integer")
        labels = case["labels"]
        if set(labels) != {str(item["id"]) for item in items} or any(
            type(value) is not int or value not in {0, 1, 2} for value in labels.values()
        ):
            raise ValueError("Every selection-pool item needs a relevance label of 0, 1, or 2")
        cache = {}
        for kind, subjects in (("content_item", items), ("goal", goals)):
            for subject in subjects:
                vector = subject.get("embedding")
                if vector is not None:
                    if synthetic and isinstance(vector, list):
                        vector = vector + [0.0] * max(0, DIMENSIONS - len(vector))
                    cache[(kind, str(subject["id"]))] = {
                        "text_hash": text_hash(embedding_text(subject, kind)), "vector": vector,
                    }
        candidates = [candidate_from_content_item(item) for item in items]
        baseline = ranked([score_candidate(candidate, goals, case["available_minutes"], now) for candidate in candidates])
        ready = True
        try:
            relevance = semantic_relevances(items, goals, cache)
            semantic = ranked([score_candidate(candidate, goals, case["available_minutes"], now,
                                               relevance=relevance[candidate.content_item_id]) for candidate in candidates])
        except ValueError:
            ready, semantic = False, baseline
        base_ids = [entry.candidate.content_item_id for entry in baseline]
        semantic_ids = [entry.candidate.content_item_id for entry in semantic]
        rows.append({"case": case["name"], "semantic_ready": ready,
                     "baseline_order": base_ids, "semantic_order": semantic_ids,
                     "baseline_top1_relevance": labels[base_ids[0]],
                     "semantic_top1_relevance": labels[semantic_ids[0]],
                     "baseline_ndcg_at_3": _ndcg(base_ids, labels),
                     "semantic_ndcg_at_3": _ndcg(semantic_ids, labels)})
    count = len(rows)
    if not count:
        raise ValueError("Evaluation requires at least one case")
    return {"synthetic": synthetic, "cases": rows,
            "summary": {"case_count": count,
                        "semantic_coverage": sum(row["semantic_ready"] for row in rows) / count,
                        "changed_winners": sum(row["baseline_order"][0] != row["semantic_order"][0] for row in rows),
                        **{key: sum(row[key] for row in rows) / count for key in (
                            "baseline_top1_relevance", "semantic_top1_relevance", "baseline_ndcg_at_3", "semantic_ndcg_at_3",
                        )}}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate(json.loads(args.fixture.read_text(encoding="utf-8"))), indent=2))


if __name__ == "__main__":
    main()
