from typing import Any

from aws.sns import Sns
from bean import BeanName, inject


@inject(BeanName.SNS_CLIENT)
def init(client: Any):
    return Sns(client)
