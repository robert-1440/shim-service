from bean import BeanName, Bean
from bean.beans import inject
from config import Config
from instance import Instance
from repos.secrets import SecretsRepo


@inject(bean_instances=(BeanName.CONFIG,
                        BeanName.SECRETS_REPO),
        beans=(BeanName.ADMIN_CLIENT, BeanName.PUSH_NOTIFIER))
def init(config: Config,
         secrets_repo: SecretsRepo,
         admin_client_bean: Bean,
         push_notifier_bean: Bean):
    return Instance(
        config,
        secrets_repo,
        admin_client_bean.create_supplier(),
        push_notification_bean_supplier=push_notifier_bean.create_supplier()
    )
