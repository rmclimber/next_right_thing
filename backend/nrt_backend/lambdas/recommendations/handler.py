import json
import logging

from nrt_backend.recommendations.service import RecommendationService


logger = logging.getLogger(__name__)
MIN_AVAILABLE_MINUTES = 1
MAX_AVAILABLE_MINUTES = 240


def handler(event, context):
    if _http_method(event) != "GET":
        return _json_response(405, {"message": "Method not allowed"})
    user_id = _authenticated_sub(event)
    if not user_id:
        return _json_response(401, {"message": "Unauthorized"})
    try:
        available_minutes = _available_minutes(event)
    except ValueError as error:
        return _json_response(400, {"message": str(error)})
    try:
        recommendation = RecommendationService().recommend_next(user_id, available_minutes)
    except Exception:
        logger.exception("Recommendation generation failed")
        return _json_response(500, {"message": "Internal server error"})
    return _json_response(200, {"recommendation": recommendation})


def _available_minutes(event):
    value = (event.get("queryStringParameters") or {}).get("available_minutes")
    if value is None or not isinstance(value, str) or not value.isdigit():
        raise ValueError("available_minutes must be an integer between 1 and 240")
    minutes = int(value)
    if not MIN_AVAILABLE_MINUTES <= minutes <= MAX_AVAILABLE_MINUTES:
        raise ValueError("available_minutes must be an integer between 1 and 240")
    return minutes


def _http_method(event):
    return event.get("requestContext", {}).get("http", {}).get("method", event.get("httpMethod", ""))


def _authenticated_sub(event):
    return event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {}).get("sub")


def _json_response(status_code, body):
    return {"statusCode": status_code, "headers": {"content-type": "application/json"}, "body": json.dumps(body)}
