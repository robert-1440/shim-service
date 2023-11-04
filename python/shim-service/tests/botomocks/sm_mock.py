import json
from datetime import datetime
from typing import Dict, Union, Any

from botomocks import BaseMockClient, raise_not_found, MockPaginator, raise_invalid_request
from botomocks.exceptions import AwsResourceExistsResponseException


class MockSecret:
    def __init__(self, name: str, description: str):
        self.Name = name
        self.Description = description
        self.ARN = f"arn:aws:secretsmanager:us-west-1:999999999999:secret:{name}-1kyRfj"
        self.DeletedDate = None


class MockSecretValue:
    def __init__(self, secret_string: str):
        self.SecretString = secret_string


class MockSecretsManagerClient(BaseMockClient):
    def __init__(self):
        super(MockSecretsManagerClient, self).__init__()
        self.secrets: Dict[str, MockSecret] = {}
        self.secret_values: Dict[str, MockSecretValue] = {}

    def create_paginator(self, name: str):
        if name != "list_secrets":
            raise NotImplementedError(f"{name} not supported.")
        return MockPaginator("SecretList", self.secrets.values())

    def add_secret(self, secret: Union[MockSecret, Any],
                   value: str = None,
                   name: str = None,
                   description: str = None):
        if not isinstance(secret, MockSecret):
            assert name is not None, "name required."
            assert description is not None, "description required."
            if hasattr(secret, 'to_json'):
                value = secret.to_json()
            else:
                value = json.dumps(secret.__dict__)
            secret = MockSecret(name, description)

        self.secrets[secret.Name] = secret
        self.secret_values[secret.Name] = MockSecretValue(value)

    def create_secret(self, **kwargs):
        name = kwargs.pop("Name")
        secret_string = kwargs.pop("SecretString")
        description = kwargs.pop("Description")
        assert len(kwargs) == 0, f"Unexpected args: ${kwargs.keys()}"
        if name in self.secrets:
            raise AwsResourceExistsResponseException("CreateSecret",
                                                     f"The operation failed because the secret {name} already exists.")
        self.secrets[name] = MockSecret(name, description)
        self.secret_values[name] = MockSecretValue(secret_string)

    def get_secret_value(self, **kwargs):
        secret_id = kwargs.pop('SecretId')
        if len(kwargs) != 0:
            raise ValueError(f"Unexpected arguments: {kwargs}")
        s = self.secret_values.get(secret_id)
        if s is None:
            raise_not_found('GetSecretValue', "Secrets Manager can't find the specified secret.")
        v = self.secrets[secret_id]
        if v.DeletedDate is not None:
            raise_invalid_request('GetSecretValue', "Secret is in the process of being deleted.")

        return {
            'ARN': f"arn:aws:secretsmanager:us-west-1:999999999999:secret:{secret_id}-1kyRfj",
            'Name': secret_id,
            'SecretString': s.SecretString
        }

    def describe_secret(self, SecretId: str = None):
        s = self.secrets.get(SecretId)
        if s is None:
            raise_not_found("DescribeSecret", "Secret not found")
        else:
            return dict(s.__dict__)

    def update_secret(self, SecretId: str = None,
                      Description: str = None,
                      SecretString: str = None):
        s = self.secrets.get(SecretId)
        if s is None or s.DeletedDate is not None:
            raise_not_found("UpdateSecret", "Secret not found")
        s.Description = Description
        v = self.secret_values[SecretId]
        v.SecretString = SecretString

    def delete_secret(self, SecretId: str = None,
                      ForceDeleteWithoutRecovery: bool = False):
        if SecretId.startswith("arn:"):
            secret = None
            for s in filter(lambda s: s.ARN == SecretId and s.DeletedDate is None, self.secrets.values()):
                secret = s
                break
        else:
            secret = self.secrets.get(SecretId)
        if secret is None or secret.DeletedDate is not None:
            if ForceDeleteWithoutRecovery:
                return
            else:
                raise_not_found("DeleteSecret", "Secret not found.")
        else:
            secret.DeletedDate = datetime.now()

    def list_secrets(self, **kwargs):
        filters = kwargs.pop("Filters")
        if len(kwargs) != 0:
            raise ValueError(f"Unexpected arguments: {kwargs}")
        if len(filters) != 1:
            raise ValueError(f"Expected one filter vs {filters}")
        f = filters[0]
        key = f.pop("Key")
        if key != 'name':
            raise ValueError(f"Expecting 'Key' to be 'key' vs {key}")
        values = f.pop("Values")
        if len(f) != 0:
            raise ValueError(f"Unexpected filter values: {f}")
        if len(values) != 1:
            raise ValueError(f"Unexpected one value for Key, got: {values}")
        name = values[0]
        results = list(map(lambda s: s.__dict__, filter(lambda s: s.DeletedDate is None and s.Name.startswith(name),
                                                        self.secrets.values())))

        return {"SecretList": results}
