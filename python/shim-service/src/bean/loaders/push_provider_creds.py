import json

from bean import BeanName
from bean.beans import inject
from cs_client.admin import AdminClient
from repos.secrets import PushNotificationProviderCredentials


@inject(bean_instances=BeanName.ADMIN_CLIENT)
def init(admin_client: AdminClient) -> PushNotificationProviderCredentials:
    secret = admin_client.find_secret("global/GcpCertificate")

    if secret is None:
        raise ValueError("Cannot find GCP credentials.")
    return PushNotificationProviderCredentials(json.loads(secret.client_secret))
