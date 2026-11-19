import copy
import json
import unittest
from hashlib import md5
from unittest.mock import Mock, patch

from nrt_backend.lambdas.embedding_refresh import handler as worker
from nrt_backend.recommendations.backfill import RefreshInterrupted, refresh_subject
from nrt_backend.recommendations.data_api_embeddings import (
    PAGE_SIZE,
    TEXT_CHUNK_CHARACTERS,
    DataApiEmbeddingRepository,
    aws_client,
    retry_transient,
)
from nrt_backend.recommendations.embeddings import (
    DIMENSIONS,
    MODEL_KEY,
    embedding_text,
    text_hash,
)

ENVIRONMENT = {"DATABASE_CLUSTER_ARN": "cluster-arn", "DB_SECRET_ARN": "secret-arn", "DB_NAME": "nrt"}
VECTOR = [1.0] + [0.0] * (DIMENSIONS - 1)


def api_records(rows):
    def field(value):
        if value is None:
            return {"isNull": True}
        return {"longValue": value} if type(value) is int else {"stringValue": value}
    return {"records": [[field(value) for value in row] for row in rows]}


class AwsFailure(RuntimeError):
    def __init__(self, code):
        super().__init__("Private provider error body must not be logged")
        self.response = {"Error": {"Code": code}}


class MemoryRepository:
    def __init__(self, users=1, items=2):
        self.subjects = {}
        self.reads, self.saves = [], []
        for user in range(users):
            user_id = f"user-{user:03}"
            self.subjects[(user_id, "goal")] = [{"id": "goal", "title": "Professional learning"}]
            self.subjects[(user_id, "content_item")] = [
                {"id": f"item-{index:03}", "title": f"Learning item {index}"} for index in range(items)
            ]

    def list_users(self, limit, after_user):
        users = sorted({key[0] for key in self.subjects})
        return [user for user in users if after_user is None or user > after_user][:limit]

    def list_subjects(self, user_id, kind, limit, after_id):
        self.reads.append((user_id, kind, after_id))
        return [subject for subject in self.subjects[(user_id, kind)]
                if after_id is None or subject["id"] > after_id][:limit]

    def save(self, user_id, kind, subject_id, fingerprint, vector):
        subject = next(subject for subject in self.subjects[(user_id, kind)] if subject["id"] == subject_id)
        subject.update(cached_hash=fingerprint, cached_vector=vector)
        self.saves.append((user_id, kind, subject_id))


class WorkerTests(unittest.TestCase):
    def test_repeated_runs_skip_valid_vectors_and_changed_text_regenerates(self):
        repository, provider = MemoryRepository(), Mock()
        provider.embed.return_value = VECTOR
        result = worker.run_refresh(repository, provider)
        self.assertEqual((result["generated"], result["scanned"], result["remaining_work"]), (3, 3, False))
        self.assertEqual(worker.run_refresh(repository, provider)["skipped"], 3)
        self.assertEqual(provider.embed.call_count, 3)
        repository.subjects[("user-000", "goal")][0]["description"] = "New direction"
        self.assertEqual(worker.run_refresh(repository, provider)["generated"], 1)
        self.assertEqual(provider.embed.call_count, 4)

    def test_user_and_subject_pagination_cover_every_row_once(self):
        repository, provider = MemoryRepository(users=PAGE_SIZE + 1, items=PAGE_SIZE + 1), Mock()
        provider.embed.return_value = VECTOR
        result = worker.run_refresh(repository, provider, max_embeddings=1000)
        expected = (PAGE_SIZE + 1) * (PAGE_SIZE + 2)
        self.assertEqual(result["generated"], expected)
        self.assertEqual(len(set(repository.saves)), expected)
        self.assertEqual(result["users"], PAGE_SIZE + 1)
        self.assertIn(("user-010", "content_item", "item-009"), repository.reads)

    def test_partial_provider_failure_keeps_successes_and_retry_skips_them(self):
        repository, provider = MemoryRepository(), Mock()
        provider.embed.side_effect = [AwsFailure("AccessDeniedException"), VECTOR, VECTOR]
        with self.assertLogs(level="INFO") as logs, self.assertRaises(worker.RefreshFailed) as raised:
            worker.run_refresh(repository, provider, sleep=lambda seconds: None)
        self.assertEqual((raised.exception.summary["failed"], raised.exception.summary["generated"]), (1, 2))
        self.assertNotIn("Private provider error body", " ".join(logs.output))
        provider.embed.side_effect, provider.embed.return_value = None, VECTOR
        result = worker.run_refresh(repository, provider)
        self.assertEqual((result["generated"], result["skipped"]), (1, 2))
        self.assertEqual(provider.embed.call_count, 4)

    def test_transient_provider_failure_retries_with_bounded_backoff(self):
        repository, provider, sleep = MemoryRepository(items=0), Mock(), Mock()
        provider.embed.side_effect = [AwsFailure("ThrottlingException"), TimeoutError(), VECTOR]
        result = worker.run_refresh(repository, provider, sleep=sleep)
        self.assertEqual((result["attempted"], result["generated"]), (1, 1))
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])

    def test_exhausted_transient_provider_failure_is_reported_without_infinite_retries(self):
        provider = Mock()
        provider.embed.side_effect = AwsFailure("ServiceUnavailableException")
        with self.assertRaises(worker.RefreshFailed) as raised:
            worker.run_refresh(MemoryRepository(items=0), provider, sleep=lambda seconds: None)
        self.assertEqual(provider.embed.call_count, 3)
        self.assertEqual(raised.exception.summary["failed"], 1)

    def test_generation_budget_saves_progress_and_next_run_completes(self):
        repository, provider = MemoryRepository(), Mock()
        provider.embed.return_value = VECTOR
        with self.assertRaises(worker.RefreshFailed) as raised:
            worker.run_refresh(repository, provider, max_embeddings=1)
        self.assertEqual(raised.exception.summary["stop_reason"], "embedding_budget")
        self.assertTrue(raised.exception.summary["remaining_work"])
        self.assertEqual(len(repository.saves), 1)
        result = worker.run_refresh(repository, provider, max_embeddings=2)
        self.assertEqual((result["skipped"], result["generated"]), (1, 2))

    def test_time_budget_stops_before_any_external_work(self):
        repository, provider, budget = Mock(), Mock(), Mock(side_effect=RefreshInterrupted("time_budget"))
        with self.assertRaises(worker.RefreshFailed) as raised:
            worker.run_refresh(repository, provider, check_budget=budget)
        repository.list_users.assert_not_called()
        provider.embed.assert_not_called()
        self.assertEqual(raised.exception.summary["stop_reason"], "time_budget")

    def test_invalid_provider_output_preserves_prior_cache(self):
        repository, provider = MemoryRepository(items=0), Mock()
        subject = repository.subjects[("user-000", "goal")][0]
        subject.update(cached_hash="stale", cached_vector=VECTOR)
        before = copy.deepcopy(subject)
        provider.embed.return_value = [float("nan")] * DIMENSIONS
        with self.assertRaises(worker.RefreshFailed):
            worker.run_refresh(repository, provider)
        self.assertEqual(subject, before)
        self.assertEqual(repository.saves, [])

    def test_empty_normalized_text_does_not_spend_the_inference_budget(self):
        repository, provider = MemoryRepository(items=1), Mock()
        repository.subjects[("user-000", "goal")][0]["title"] = "<script>hidden</script>"
        provider.embed.return_value = VECTOR
        with self.assertRaises(worker.RefreshFailed) as raised:
            worker.run_refresh(repository, provider, max_embeddings=1)
        self.assertEqual((raised.exception.summary["generated"], raised.exception.summary["failed"]), (1, 1))
        self.assertEqual(raised.exception.summary["attempted"], 1)
        provider.embed.assert_called_once_with("Learning item 0")

    def test_one_write_failure_preserves_other_successes_and_reports_failure(self):
        repository, provider = MemoryRepository(), Mock()
        provider.embed.return_value = VECTOR
        save = repository.save

        def fail_goal_write(user_id, kind, *args):
            if kind == "goal":
                raise RuntimeError("private database failure")
            save(user_id, kind, *args)

        repository.save = fail_goal_write
        with self.assertRaises(worker.RefreshFailed) as raised:
            worker.run_refresh(repository, provider)
        self.assertEqual((raised.exception.summary["generated"], raised.exception.summary["failed"]), (2, 1))
        self.assertTrue(raised.exception.summary["remaining_work"])
        self.assertEqual(len(repository.saves), 2)

    def test_later_page_read_failure_keeps_earlier_page_writes(self):
        repository, provider = MemoryRepository(items=20), Mock()
        provider.embed.return_value = VECTOR
        list_subjects = repository.list_subjects

        def fail_second_page(user_id, kind, limit, after_id):
            if kind == "content_item" and after_id is not None:
                raise RuntimeError("private database read failure")
            return list_subjects(user_id, kind, limit, after_id)

        repository.list_subjects = fail_second_page
        with self.assertRaises(worker.RefreshFailed) as raised:
            worker.run_refresh(repository, provider)
        self.assertEqual(raised.exception.summary["generated"], 11)
        self.assertEqual(raised.exception.summary["stop_reason"], "RuntimeError")
        self.assertEqual(len(repository.saves), 11)

    def test_unreadable_subject_does_not_hide_other_subjects(self):
        repository, provider = MemoryRepository(), Mock()
        provider.embed.return_value = VECTOR
        repository.subjects[("user-000", "content_item")][0]["load_failed"] = True
        with self.assertRaises(worker.RefreshFailed) as raised:
            worker.run_refresh(repository, provider)
        self.assertEqual((raised.exception.summary["generated"], raised.exception.summary["failed"]), (2, 1))

    def test_handler_uses_data_api_and_deadline_with_configured_generation_limit(self):
        context = Mock()
        context.get_remaining_time_in_millis.return_value = 300_000
        with patch.dict("os.environ", {"EMBEDDING_REFRESH_MAX_EMBEDDINGS": "42"}), \
                patch.object(worker, "DataApiEmbeddingRepository") as repository, \
                patch.object(worker, "TitanEmbeddingProvider") as provider, \
                patch.object(worker, "aws_client") as aws_client, \
                patch.object(worker, "run_refresh", return_value={"generated": 1}) as run:
            self.assertEqual(worker.handler({}, context), {"generated": 1})
            aws_client.assert_called_once_with("bedrock-runtime")
            self.assertEqual(run.call_args.kwargs["max_embeddings"], 42)
            self.assertIs(run.call_args.args[0], repository.return_value)
            self.assertIs(run.call_args.args[1], provider.return_value)
            context.get_remaining_time_in_millis.return_value = 80_000
            with self.assertRaises(RefreshInterrupted):
                run.call_args.kwargs["check_budget"]()

    def test_invalid_configuration_never_initializes_aws_clients(self):
        with patch.dict("os.environ", {"EMBEDDING_REFRESH_MAX_EMBEDDINGS": "0"}), \
                patch.object(worker, "DataApiEmbeddingRepository") as repository, self.assertRaises(ValueError):
            worker.handler({}, Mock())
        repository.assert_not_called()


class DataApiAdapterTests(unittest.TestCase):
    def repository(self, client):
        with patch.dict("os.environ", ENVIRONMENT):
            return DataApiEmbeddingRepository(client, sleep=lambda seconds: None)

    def test_user_discovery_is_bounded_and_parameterized(self):
        client = Mock()
        client.execute_statement.return_value = api_records([["user-b"]])
        self.assertEqual(self.repository(client).list_users(10, "user-a"), ["user-b"])
        kwargs = client.execute_statement.call_args.kwargs
        self.assertEqual(kwargs["resourceArn"], "cluster-arn")
        self.assertIn("status = 'active'", kwargs["sql"])
        self.assertNotIn("user-a", kwargs["sql"])
        self.assertIn({"name": "after_user", "value": {"stringValue": "user-a"}}, kwargs["parameters"])

    def test_data_api_socket_timeout_exceeds_its_server_statement_timeout(self):
        boto3, botocore = Mock(), Mock()
        with patch("nrt_backend.recommendations.data_api_embeddings.import_module",
                   side_effect=lambda name: {"boto3": boto3, "botocore.config": botocore}[name]):
            aws_client("rds-data")
            self.assertEqual(botocore.Config.call_args.kwargs["read_timeout"], 60)
            aws_client("bedrock-runtime")
            self.assertEqual(botocore.Config.call_args.kwargs["read_timeout"], 10)

    def test_earlier_subject_is_persisted_before_later_text_hydration_exhausts_budget(self):
        document = json.dumps({"title": "Ready", "description": None})
        client = Mock()

        def execute(**kwargs):
            if "SELECT id::text" in kwargs["sql"]:
                return api_records([
                    ["first", document, len(document), "hash", None, None],
                    ["long", "{", 5000, "hash", None, None],
                ])
            if "INSERT INTO" in kwargs["sql"]:
                return api_records([["first"]])
            raise RefreshInterrupted("time_budget")

        client.execute_statement.side_effect = execute
        repository = self.repository(client)
        repository.list_users = Mock(return_value=["user"])
        provider = Mock()
        provider.embed.return_value = VECTOR
        with self.assertRaises(worker.RefreshFailed) as raised:
            worker.run_refresh(repository, provider)
        self.assertEqual(raised.exception.summary["generated"], 1)
        provider.embed.assert_called_once_with("Ready")

    def test_long_markup_is_reassembled_without_changing_the_embedding_representation(self):
        raw = {"title": "Evidence &amp; learning", "summary": "<script>" + "x" * 10000 + "</script><p>临床学习 🧠 Bayesian inference</p>"}
        document = json.dumps(raw, ensure_ascii=False)
        chunks = [document[index:index + TEXT_CHUNK_CHARACTERS] for index in range(0, len(document), TEXT_CHUNK_CHARACTERS)]
        fingerprint = text_hash(embedding_text(raw, "content_item"))
        client = Mock()
        client.execute_statement.side_effect = [
            api_records([["item", chunks[0], len(document), md5(document.encode()).hexdigest(), fingerprint, json.dumps(VECTOR)]]),
            *[api_records([[chunk]]) for chunk in chunks[1:]],
        ]
        repository = self.repository(client)
        subject = next(repository.list_subjects("user", "content_item", 10))
        self.assertEqual(subject["summary"], raw["summary"])
        self.assertEqual(embedding_text(subject, "content_item"), embedding_text(raw, "content_item"))
        provider = Mock()
        self.assertEqual(refresh_subject(repository, provider, "user", "content_item", subject), "skipped")
        provider.embed.assert_not_called()
        for call in client.execute_statement.call_args_list[1:]:
            self.assertIn("md5(document) = :source_hash", call.kwargs["sql"])
            self.assertIn("subject.user_id = :user_id", call.kwargs["sql"])

    def test_concurrent_edit_marks_only_that_subject_unreadable(self):
        valid = json.dumps({"title": "Other", "description": None})
        client = Mock()
        client.execute_statement.side_effect = [api_records([
            ["changed", "{", 5000, "oldhash", None, None],
            ["other", valid, len(valid), "hash", None, None],
        ]), api_records([])]
        subjects = list(self.repository(client).list_subjects("user", "goal", 10))
        self.assertTrue(subjects[0]["load_failed"])
        self.assertEqual(subjects[1]["title"], "Other")

    def test_data_api_resume_is_retried_but_access_denial_is_not(self):
        client = Mock()
        client.execute_statement.side_effect = [AwsFailure("DatabaseResumingException"), api_records([])]
        self.assertEqual(self.repository(client).list_users(), [])
        self.assertEqual(client.execute_statement.call_count, 2)
        client.execute_statement.reset_mock(side_effect=True)
        client.execute_statement.side_effect = AwsFailure("AccessDeniedException")
        with self.assertRaises(AwsFailure):
            self.repository(client).list_users()
        client.execute_statement.assert_called_once()

    def test_save_normalizes_vector_and_requires_owned_subject(self):
        client = Mock()
        client.execute_statement.return_value = api_records([["item"]])
        repository = self.repository(client)
        repository.save("user", "content_item", "item", "hash", [2.0] + [0.0] * (DIMENSIONS - 1))
        kwargs = client.execute_statement.call_args.kwargs
        params = {entry["name"]: entry["value"].get("stringValue") for entry in kwargs["parameters"]}
        self.assertEqual(params["model_key"], MODEL_KEY)
        self.assertEqual(json.loads(params["vector"]), VECTOR)
        self.assertIn("user_id = :user_id", kwargs["sql"])
        client.execute_statement.return_value = api_records([])
        with self.assertRaises(ValueError):
            repository.save("other", "content_item", "item", "hash", VECTOR)

    def test_malformed_cache_is_regenerated_and_bad_responses_fail_cleanly(self):
        document = json.dumps({"title": "Text", "description": None})
        client = Mock()
        client.execute_statement.return_value = api_records([["goal", document, len(document), "hash", text_hash("Text"), "bad json"]])
        repository = self.repository(client)
        subject = next(repository.list_subjects("user", "goal", 10))
        self.assertIsNone(subject["cached_vector"])
        client.execute_statement.return_value = api_records([["goal"]])
        provider = Mock()
        provider.embed.return_value = VECTOR
        self.assertEqual(refresh_subject(repository, provider, "user", "goal", subject), "generated")
        client.execute_statement.return_value = {"records": "malformed"}
        with self.assertRaises(TypeError):
            repository.list_users()

    def test_deadline_during_retry_stops_without_another_request(self):
        operation, budget = Mock(side_effect=TimeoutError()), Mock(side_effect=[None, RefreshInterrupted("time_budget")])
        with self.assertRaises(RefreshInterrupted):
            retry_transient(operation, check_budget=budget, sleep=lambda seconds: None)
        operation.assert_called_once()

    def test_aurora_resume_gets_time_to_wake_but_still_has_a_bounded_retry_count(self):
        operation, sleep = Mock(), Mock()
        operation.side_effect = [AwsFailure("DatabaseResumingException"), AwsFailure("DatabaseResumingException"), "ready"]
        self.assertEqual(retry_transient(operation, sleep=sleep), "ready")
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [5, 10])
        self.assertEqual(operation.call_count, 3)


if __name__ == "__main__":
    unittest.main()
