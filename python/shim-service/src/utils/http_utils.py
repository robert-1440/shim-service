from io import StringIO
from typing import Dict, Any

from utils.uri_utils import encode_query_component


class Raw:
    def __init__(self, content: str):
        self.content = content


def encode_form_data(entries: Dict[str, Any]) -> str:
    builder = StringIO()
    for key, value in entries.items():
        if type(value) is Raw:
            value = value.content
        else:
            value = encode_query_component(value)
        if builder.tell() > 0:
            builder.write('&')
        builder.write(key)
        builder.write('=')
        builder.write(value)
    return builder.getvalue()

