from typing import Any

AwsClient = Any


def is_not_found_exception(source: Exception) -> bool:
    return is_exception(source, 404, "ResourceNotFoundException")


def is_invalid_request(source: Exception) -> bool:
    return is_exception(source, 400, "InvalidRequestException")


def is_conflict_exception(source: Exception) -> bool:
    return is_exception(source, 409, "ConflictException")


def is_exception(source: Exception, status: int, code: str):
    if hasattr(source, "response"):
        response = getattr(source, "response")
        if response is not None and type(response) is dict:
            metadata = response.get('ResponseMetadata')
            if metadata is not None:
                if metadata.get('HTTPStatusCode') == status and status == 404:
                    return True
            error = response.get('Error')
            if error is not None:
                if code == error.get('Code'):
                    return True
    return False
