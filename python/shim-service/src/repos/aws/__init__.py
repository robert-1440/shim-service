SHIM_SERVICE_VIRTUAL_RANGE_TABLE = "ShimServiceVirtualRangeTable"
SHIM_SERVICE_VIRTUAL_TABLE = "ShimServiceVirtualTable"
SHIM_SERVICE_EVENT_TABLE = "ShimServiceEvent"
SHIM_SERVICE_SESSION_TABLE = "ShimServiceSession"


class VirtualTable:
    def __init__(self, name: str, table_type: str):
        self.name = name
        self.table_type = table_type


VIRTUAL_HASH_KEY = 'hashKey'
VIRTUAL_RANGE_KEY = 'rangeKey'

SEQUENCE_TABLE = VirtualTable('Sequence', 'a')
SFDC_SESSION_TABLE = VirtualTable('SfdcSession', 'b')
USER_SESSION_TABLE = VirtualTable('UserSession', 'c')
SESSION_CONTEXT_TABLE = VirtualTable('SessionContext', 'd')
PUSH_NOTIFICATION_TABLE = VirtualTable('PushNotification', 'e')
RESOURCE_LOCK_TABLE = VirtualTable('ResourceLock', 'f')
PENDING_EVENT_TABLE = VirtualTable('PendingEvent', 'g')
WORK_ID_MAP_TABLE = VirtualTable('WorkIdMap', 'h')
PENDING_TENANT_EVENT_TABLE = VirtualTable('PendingTenantEvent', 'i')
