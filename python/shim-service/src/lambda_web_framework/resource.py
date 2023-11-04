from typing import Collection

from lambda_web_framework.router import add_route, BodyTransformer
from lambda_web_framework.web_router import Method
from utils.path_utils import join_base_path, join_paths


class Resource:
    def __init__(self, root_url: str, resource_name: str):
        self.__prefix_url = join_base_path(root_url, resource_name)

    def route(self, path: str,
              response_codes: Collection[int] = (200, 400, 404),
              method: Method = Method.GET,
              include_request: bool = False,
              session_required: bool = False,
              api_required: bool = False,
              no_instance: bool = False,
              body_transformer: BodyTransformer = None):
        def decorator(wrapped_function):
            add_route(join_paths(self.__prefix_url, path), method, wrapped_function, response_codes,
                      include_request,
                      session_required,
                      api_required,
                      no_instance,
                      body_transformer)

        return decorator
