"""Targeted RDS Data API source-health updates for the non-VPC RSS Fetch Lambda."""

import os
from importlib import import_module


UPDATE_SOURCE_HEALTH_SQL = """
UPDATE content_sources
SET
    last_fetch_status = :status,
    last_fetch_attempt_at = CURRENT_TIMESTAMP,
    last_fetch_success_at = CASE
        WHEN :status = 'healthy' THEN CURRENT_TIMESTAMP
        ELSE last_fetch_success_at
    END,
    last_fetch_error = :error
WHERE id = CAST(:content_source_id AS uuid)
  AND user_id = :user_id;
"""


class DataApiContentSourceHealthRepository:
    """Updates one owned Content Source without requiring VPC database access."""

    def __init__(self, client=None):
        self._client = client or _rds_data_client()

    def record(self, *, user_id: str, content_source_id: str, status: str, error: str | None) -> bool:
        response = self._client.execute_statement(
            resourceArn=_required_env("DATABASE_CLUSTER_ARN"),
            secretArn=_required_env("DB_SECRET_ARN"),
            database=_required_env("DB_NAME"),
            sql=UPDATE_SOURCE_HEALTH_SQL,
            parameters=[
                _string_parameter("status", status),
                _string_parameter("content_source_id", content_source_id),
                _string_parameter("user_id", user_id),
                _nullable_string_parameter("error", error),
            ],
        )
        if not isinstance(response, dict):
            raise RuntimeError("Malformed RDS Data API response: expected an object")
        return response.get("numberOfRecordsUpdated", 0) == 1


def _string_parameter(name: str, value: str):
    return {"name": name, "value": {"stringValue": value}}


def _nullable_string_parameter(name: str, value: str | None):
    return {"name": name, "value": {"isNull": True}} if value is None else _string_parameter(name, value)


def _required_env(name: str):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _rds_data_client():
    return import_module("boto3").client("rds-data")
