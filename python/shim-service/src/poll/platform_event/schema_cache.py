from typing import Optional, Any, Callable

from utils.concurrent_cache import ConcurrentTtlCache

Schema = Any
SchemaLoader = Callable[[], Schema]


class SchemaCache:
    def __init__(self):
        self.cache = ConcurrentTtlCache(100, 60 * 1000)

    def get_schema(self, tenant_id: int, schema_id: str, loader: SchemaLoader) -> Optional[Schema]:
        key = f"{tenant_id}:{schema_id}"
        return self.cache.get(key, loader)
