from threading import RLock
from typing import Optional

from bean import BeanSupplier
from config import Config
from cs_client.admin import AdminClient
from push_notification.manager import PushNotificationManager
from repos.secrets import SecretsRepo
from utils.concurrent_cache import ConcurrentTtlCache

SERVICE_ALIAS = 'shim'

_CACHE_TIME_MINUTES = 10


class Instance:
    def __init__(self,
                 config: Config,
                 secrets_repo: SecretsRepo,
                 admin_client_bean_supplier: BeanSupplier[AdminClient],
                 push_notification_bean_supplier: BeanSupplier[PushNotificationManager]):
        self.config = config
        self.__secrets_repo = secrets_repo
        self.__mutex = RLock()
        self.__ac_supplier = admin_client_bean_supplier
        self.__fcm_token_cache = ConcurrentTtlCache(1000,
                                                    60,
                                                    self.__load_fcm_device_token,
                                                    )
        self.__push_notification_bean_supplier = push_notification_bean_supplier

    def get_admin_client(self) -> AdminClient:
        return self.__ac_supplier.get()

    def verify_fcm_device_token(self, token: str) -> Optional[str]:
        message = self.__fcm_token_cache.get(token)
        if message is None or len(message) == 0:
            return None
        return message

    def __load_fcm_device_token(self, token: str) -> str:
        return self.__push_notification_bean_supplier.get().test_push_notification(token) or ""

    def find_tenant_id(self, org_id: str) -> Optional[int]:
        return self.__ac_supplier.get().find_tenant_id(org_id)

    def get_tenant_id(self, org_id: str) -> int:
        return self.__ac_supplier.get().get_tenant_id(org_id)
