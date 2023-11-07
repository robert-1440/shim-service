from bean import BeanName, Bean
from bean.beans import inject
from push_notification.gcp.gcp_notifier import GcpPushNotifier


@inject(beans=(BeanName.PUSH_NOTIFICATION_CREDS, BeanName.FIREBASE_ADMIN, BeanName.PUSH_NOTIFICATION_CERT_BUILDER))
def init(gcp_creds_bean: Bean, firebase_admin_bean: Bean, cert_builder_bean: Bean):
    return GcpPushNotifier(
        gcp_creds_bean.create_supplier(),
        firebase_admin_bean.create_supplier(),
        cert_builder_bean.create_supplier()
    )
