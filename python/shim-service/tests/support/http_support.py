from typing import Dict, Any

from urllib.parse import parse_qsl, unquote_plus


def decode_query_component(text: str) -> str:
    return unquote_plus(text)


def decode_form_data(content: str) -> Dict[str, Any]:
    results = {}
    for key, value in parse_qsl(content):
        results[key] = decode_query_component(value)

    return results
