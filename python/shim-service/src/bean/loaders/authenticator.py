from auth.auth_handler import AuthenticatorImpl
from bean import BeanName
from bean.beans import inject
from instance import Instance


@inject(bean_instances=BeanName.INSTANCE)
def init(instance: Instance):
    return AuthenticatorImpl(instance.get_admin_client())
