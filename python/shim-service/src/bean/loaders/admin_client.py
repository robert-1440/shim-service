import os

from bean import BeanName, inject
from cs_client import ServiceKeyCredentials
from cs_client.admin import AdminClient
from cs_client.profile import Profile
from instance import SERVICE_ALIAS
from repos.secrets import SecretsRepo


@inject(bean_instances=BeanName.SECRETS_REPO)
def init(secrets_repo: SecretsRepo):
    key = secrets_repo.get_service_keys().keys[1]
    return AdminClient(Profile(os.environ.get('CONFIG_SERVICE_URL', 'https://configuration.1440.io'),
                               ServiceKeyCredentials(SERVICE_ALIAS, key)))
