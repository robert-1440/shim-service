from typing import Optional

from aws.dynamodb import DynamoDb
from repos import OptimisticLockException
from repos.aws import TENANT_CONTEXT_TABLE
from repos.aws.abstract_table_repo import AwsVirtualTableRepo
from tenant import TenantContext, TenantContextType
from tenant.repo import TenantContextRepo


class AwsTenantContextRepo(AwsVirtualTableRepo, TenantContextRepo):
    __hash_key_attributes__ = {
        'contextType': str,
        'tenantId': int
    }
    __virtual_table__ = TENANT_CONTEXT_TABLE
    __initializer__ = TenantContext.from_record

    def __init__(self, ddb: DynamoDb):
        super(AwsTenantContextRepo, self).__init__(ddb)

    def find_context(self, context_type: TenantContextType, tenant_id: int) -> Optional[TenantContext]:
        return self.find(context_type.value, tenant_id, consistent=True)

    def update_or_create_context(self, context: TenantContext):
        if not self.patch_with_condition(context, 'stateCounter', context.state_counter + 1,
                                         {'contextData': context.data}):
            if not self.create(context):
                raise OptimisticLockException()
        context.state_counter += 1

    def delete_context(self, context: TenantContext) -> bool:
        return self.delete_with_condition(context, 'stateCounter', context.state_counter)
