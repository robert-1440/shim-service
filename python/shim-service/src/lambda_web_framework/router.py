from typing import Callable, Dict, Optional, Tuple, Collection

from bean import BeanName, inject
from instance import Instance
from lambda_web_framework.request import LambdaHttpRequest, BodyTransformer
from lambda_web_framework.web_exceptions import NotFoundException, MethodNotAllowedException
from lambda_web_framework.web_router import Method, Route, Authenticator
from utils import loghelper, path_utils

logger = loghelper.get_logger(__name__)

_routes: Dict[str, Route] = {}


def __find_route(path: str) -> Optional[Route]:
    parts = path_utils.split_path(path)
    for r in filter(lambda r: r.path_matches(path, parts) is not None, _routes.values()):
        return r
    return None


def __find_full_route(path: str, method: str) -> Optional[Tuple[Route, Dict[str, str]]]:
    for r in filter(lambda r: r.method.name == method, _routes.values()):
        r: Route
        v = r.path_matches(path)
        if v is not None:
            return r, v
    return None


def add_route(path: str, method: Method, caller: Callable,
              response_codes: Collection[int],
              include_request: bool,
              session_required: bool,
              api_required: bool,
              no_instance: bool,
              body_transformer: BodyTransformer):
    key = f"{method.name}:{path}"
    if key in _routes:
        raise AssertionError(f"{key} route has already been added.")
    if body_transformer is not None and not method.body_allowed():
        raise AssertionError(f"Body is not allowed for method {method.name}")

    _routes[key] = Route(path, method, caller, response_codes, include_request, session_required,
                         api_required, no_instance,
                         body_transformer)


@inject(bean_instances=BeanName.AUTHENTICATOR)
def authenticate(route: Route, request: LambdaHttpRequest, authenticator: Authenticator):
    authenticator.authenticate(route, request)


@inject(bean_instances=BeanName.INSTANCE)
def process(request: LambdaHttpRequest, instance: Instance):
    path = request.path
    result = __find_full_route(path, request.method)
    if result is None:
        f = __find_route(path)
        if f is None:
            logger.info(f"Unable to find {path}")
            raise NotFoundException()
        else:
            raise MethodNotAllowedException()
    route = result[0]
    params = result[1]
    authenticate(route, request)
    return route.invoke(instance, request, params)
