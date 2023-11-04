from typing import Any

from aws.sns import Sns
from bean import BeanName
from bean.beans import inject


@inject(BeanName.SNS_CLIENT)
def init(client: Any):
    return Sns(client)
