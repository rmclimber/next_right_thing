import logging
import os
from importlib import import_module


logger = logging.getLogger(__name__)


LIST_ACTIVE_RSS_SOURCES_SQL = """
SELECT id, user_id, url
FROM content_sources
WHERE status = 'active'
  AND source_type = 'rss';
"""


class DataApiContentSourceRepository:
    """Reads active RSS Content Sources for the non-VPC dispatcher only."""

    def __init__(self, client=None):
        self._client = client or _rds_data_client()

    def list_active_rss_sources(self):
        logger.warning("Executing active RSS source query through RDS Data API")
        response = self._client.execute_statement(
            resourceArn=_required_env("DATABASE_CLUSTER_ARN"),
            secretArn=_required_env("DB_SECRET_ARN"),
            database=_required_env("DB_NAME"),
            sql=LIST_ACTIVE_RSS_SOURCES_SQL,
        )
        if not isinstance(response, dict):
            raise RuntimeError("Malformed RDS Data API response: expected an object")
        records = response.get("records", [])
        if not isinstance(records, list):
            raise RuntimeError("Malformed RDS Data API response: records must be a list")

        sources = [_decode_source_record(record) for record in records]
        logger.warning("Retrieved %s active RSS content sources", len(sources))
        return sources


def _decode_source_record(record):
    if not isinstance(record, list) or len(record) != 3:
        raise RuntimeError("Malformed RDS Data API response: expected three source columns")

    source_id, user_id, url = (_string_value(field, name) for field, name in zip(record, ("id", "user_id", "url")))
    return {"id": source_id, "user_id": user_id, "url": url}


def _string_value(field, name):
    if not isinstance(field, dict) or set(field) != {"stringValue"}:
        raise RuntimeError(f"Malformed RDS Data API response: {name} must be a stringValue")

    value = field["stringValue"]
    if not isinstance(value, str):
        raise RuntimeError(f"Malformed RDS Data API response: {name} must be a string")
    return value


def _required_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _rds_data_client():
    return import_module("boto3").client("rds-data")
