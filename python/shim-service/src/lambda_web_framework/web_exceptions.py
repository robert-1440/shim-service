from typing import Dict, Any, Union


class LambdaHttpException(Exception):
    def __init__(self, status_code: int,
                 message: str,
                 headers: Dict[str, str] = None,
                 error_code: str = None,
                 body: Union[str, dict] = None):
        super(LambdaHttpException, self).__init__(message)
        self.status_code = status_code
        self.message = message
        self.headers = headers
        self.error_code = error_code
        self.body = body

    def to_response(self) -> Dict[str, Any]:
        if self.error_code is not None:
            body = {
                'code': self.error_code,
                'message': self.message,
                'errorMessage': self.message
            }
        else:
            body = {"errorMessage": self.message}
        if self.body is not None:
            body['response'] = self.body
        result = {
            "statusCode": self.status_code,
            "body": body
        }
        if self.headers is not None and len(self.headers) > 0:
            result['headers'] = self.headers
        return result


class ForbiddenException(LambdaHttpException):
    def __init__(self, message: str):
        super(ForbiddenException, self).__init__(403, f"Forbidden: {message}")


class NotAuthorizedException(LambdaHttpException):
    def __init__(self, message: str):
        super(NotAuthorizedException, self).__init__(401, f"Not Authorized: {message}")


class NotFoundException(LambdaHttpException):
    def __init__(self, resource: str = None):
        message = "Resource Not Found"
        if resource is not None and len(resource) > 0:
            message += f": {resource}"
        super(NotFoundException, self).__init__(404, message)


class GoneException(LambdaHttpException):
    def __init__(self, message: str = None):
        super(GoneException, self).__init__(410, message)


class MethodNotAllowedException(LambdaHttpException):
    def __init__(self):
        super(MethodNotAllowedException, self).__init__(415, "Method not allowed")


class BadRequestException(LambdaHttpException):
    def __init__(self, message: str, error_code: str = None):
        super(BadRequestException, self).__init__(400, message, error_code=error_code)


class ConflictException(LambdaHttpException):
    def __init__(self, message: str, error_code: str = None):
        super(ConflictException, self).__init__(409, message, error_code=error_code)


class EntityExistsException(LambdaHttpException):
    def __init__(self, message: str):
        super(EntityExistsException, self).__init__(409, message)


class MissingParameterException(BadRequestException):
    def __init__(self, parameter: str, parameter_type: str = "parameter"):
        super(MissingParameterException, self).__init__(f"Missing {parameter_type} '{parameter}'.")


class InvalidParameterException(BadRequestException):
    def __init__(self, parameter: str, message: str):
        super(InvalidParameterException, self).__init__(f"'{parameter}' is invalid: {message}",
                                                        error_code="InvalidParameter")
