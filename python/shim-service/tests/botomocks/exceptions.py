import uuid
from typing import Dict, Any, List, Optional


class AwsExceptionResponseException(Exception):
    def __init__(self, operation_name: Optional[str], status_code: int, error_code: str,
                 error_message: str,
                 **kwargs):
        req_id = str(uuid.uuid4())
        error_node = {
            'Message': error_message,
            'Code': error_code
        }
        kwargs.update(error_node)
        record = {
            'Error': error_node,
            'ResponseMetadata': {
                'RequestId': req_id,
                'HTTPStatusCode': status_code,
                'HTTPHeaders': {
                    'x-amzn-request-id': req_id,
                    'content-type': "application/x-amz-json-1.1",
                    'connection': "close"
                },
                'RetryAttempts': 0
            },
            'Message': error_message
        }
        if operation_name is not None:
            record['operation_name'] = operation_name
        self.response = record
        super(AwsExceptionResponseException, self).__init__(error_message)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


class AwsResourceNotFoundResponseException(AwsExceptionResponseException):
    def __init__(self, operation_name: str, message: str):
        super(AwsResourceNotFoundResponseException, self).__init__(operation_name=operation_name,
                                                                   status_code=400,
                                                                   error_code="ResourceNotFoundException",
                                                                   error_message=message)


class AwsResourceExistsResponseException(AwsExceptionResponseException):
    def __init__(self, operation_name: str, message: str):
        super(AwsResourceExistsResponseException, self).__init__(operation_name=operation_name,
                                                                 status_code=400,
                                                                 error_code="ResourceExistsException",
                                                                 error_message=message)


class AwsInvalidRequestResponseException(AwsExceptionResponseException):
    def __init__(self, operation_name: str, message: str):
        super(AwsInvalidRequestResponseException, self).__init__(operation_name=operation_name,
                                                                 status_code=400,
                                                                 error_code="InvalidRequestException",
                                                                 error_message=message)


class AwsInvalidParameterResponseException(AwsExceptionResponseException):
    def __init__(self, operation_name: str, message: str,
                 error_code: str = "InvalidParameterException",
                 **kwargs):
        super(AwsInvalidParameterResponseException, self).__init__(operation_name=operation_name,
                                                                   status_code=400,
                                                                   error_code=error_code,
                                                                   error_message=message,
                                                                   **kwargs)


class AwsConflictResponseException(AwsExceptionResponseException):
    def __init__(self, operation_name: str, message: str,
                 error_code: str = "ConflictException",
                 **kwargs):
        super(AwsConflictResponseException, self).__init__(operation_name=operation_name,
                                                           status_code=409,
                                                           error_code=error_code,
                                                           error_message=message,
                                                           **kwargs)


class ConditionalCheckFailedException(AwsExceptionResponseException):
    def __init__(self, operation_name: str):
        super(ConditionalCheckFailedException, self).__init__(operation_name=operation_name,
                                                              status_code=409,
                                                              error_code="ConditionalCheckFailed",
                                                              error_message="Condition check failed.")


class AwsTransactionCanceledException(AwsExceptionResponseException):
    def __init__(self, reasons: List[Dict[str, Any]]):
        reason_text = f"{list(map(lambda r: r['Code'], reasons))}"
        super(AwsTransactionCanceledException, self).__init__(
            operation_name=None,
            status_code=400,
            error_code="TransactionCanceledException",
            error_message=f"Transaction cancelled, please refer cancellation reasons for specific reasons {reason_text}"
        )
        self.response['CancellationReasons'] = reasons
