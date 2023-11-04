from typing import Any, Callable, Dict, List, Optional

AwsClient = Any

def is_not_found_exception(source: Exception) -> bool:
    return is_exception(source, 404, "ResourceNotFoundException")


def is_resource_exists(source: Exception):
    return is_exception(source, 400, "ResourceExistsException")


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


def paginate(client: Any, method: str,
             list_name: str,
             visitor: Callable[[Dict[str, Any]], None],
             **kwargs):
    """
    Creates a paginator.

    :param client: The client.
    :param method: The method to call (i.e. list_secrets)
    :param list_name: The name of the list parameter in the page returned (i.e. SecretList)
    :param visitor: The function to call with each row of a page.
    """
    paginator = client.get_paginator(method)
    page_iterator = paginator.paginate(**kwargs)
    for page in page_iterator:
        if list_name not in page:
            break
        for row in page[list_name]:
            visitor(row)


def paginate_all(client: Any, method: str,
                 list_name: str,
                 transformer: Optional[Callable[[Dict[str, Any]], Any]],
                 **kwargs) -> List[Any]:
    results = []

    def visitor(n: Dict[str, Any]):
        if transformer is not None:
            n = transformer(n)
        results.append(n)

    paginate(client, method, list_name, visitor, **kwargs)
    return results
