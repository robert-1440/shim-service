from bean import BeanName, Bean, inject
from config import Config
from instance import Instance
from repos.secrets import SecretsRepo


@inject(bean_instances=(BeanName.CONFIG,
                        BeanName.SECRETS_REPO),
        beans=(BeanName.ADMIN_CLIENT, BeanName.PUSH_NOTIFICATION_MANAGER))
def init(config: Config,
         secrets_repo: SecretsRepo,
         admin_client_bean: Bean,
         push_notification_manager_bean: Bean):
    return Instance(
        config,
        secrets_repo,
        admin_client_bean.create_supplier(),
        push_notification_bean_supplier=push_notification_manager_bean.create_supplier()
    )
