import json
from typing import Any, Dict, Optional

from services.sfdc.types.aura_context import AuraSettings
from utils.http_client import HttpClient, MediaType
from utils.http_utils import Raw, encode_form_data
from utils.uri_utils import form_https_uri

QUERY_COMPONENT = Raw(
    "%7B%22actions%22%3A%5B%7B%22descriptor%22%3A%22serviceComponent%3A%2F%2Fui.global.components.one.one.controller.OneController%2FACTION%24getCurrentApp%22%2C%22params%22%3A%7B%7D%2C%22id%22%3A%220%3Bp%22%7D%5D%7D")


class _ValuesProvider:
    def __init__(self, type: str, values: Dict[str, Any]):
        self.type = type
        self.values = values

    def to_record(self) -> dict:
        return {
            'type': self.type,
            'values': self.values
        }

    def get_value(self, key: str) -> Any:
        entry = self.values[key]
        return entry['value']

    @classmethod
    def from_record(cls, record: Dict[str, Any]):
        return cls(record['type'], record['values'])


class _Context:
    def __init__(self, mode: Optional[str],
                 app: Optional[str],
                 path_prefix: Optional[str],
                 fwuid: Optional[str],
                 mlr: Optional[int],
                 uad: Optional[int],
                 descriptor_uids: Optional[Any],
                 loaded: Optional[Dict[str, Any]],
                 global_value_provider_map: Optional[Dict[str, _ValuesProvider]]):
        self.mode = mode
        self.app = app
        self.path_prefix = path_prefix
        self.fwuid = fwuid
        self.mlr = mlr
        self.uad = uad
        self.descriptor_uids = descriptor_uids
        self.loaded = loaded
        self.global_value_provider_map = global_value_provider_map

    def to_record(self) -> dict:
        return {
            'mode': self.mode,
            'app': self.app,
            'pathPrefix': self.path_prefix,
            'fwuid': self.fwuid,
            'mlr': self.mlr,
            'uad': self.uad,
            'descriptorUids': self.descriptor_uids,
            'loaded': self.loaded,
            'globalValueProviders': list(
                map(lambda v: v.to_record(),
                    self.global_value_provider_map.values())) if self.global_value_provider_map is not None else None
        }

    def get_values_provider(self, provider_type: str) -> Optional[_ValuesProvider]:
        return self.global_value_provider_map.get(provider_type) if self.global_value_provider_map else None

    @classmethod
    def from_record(cls, record):
        global_value_provider_map = {}
        if 'globalValueProviders' in record:
            value_providers_list = record['globalValueProviders']
            for data in value_providers_list:
                value_provider = _ValuesProvider.from_record(data)
                global_value_provider_map[value_provider.type] = value_provider

        return cls(
            record.get('mode'),
            record.get('app'),
            record.get('pathPrefix'),
            record.get('fwuid'),
            record.get('mlr'),
            record.get('uad'),
            record.get('descriptorUids'),
            record.get('loaded'),
            global_value_provider_map
        )


class _PreloadActions:
    uad: Optional[int]
    app_context_id: Optional[str]
    density: Optional[str]

    def __init__(self, actions: Any, context: _Context, perf_summary: Any):
        self.actions = actions
        self.context = context
        self.perf_summary = perf_summary
        self.uad = None
        self.app_context_id = None
        self.density = None

        if context is not None:
            self.uad = context.uad
            provider: _ValuesProvider = context.get_values_provider('$Global')
            if provider is not None:
                self.app_context_id = provider.get_value('appContextId')
                self.density = provider.get_value('density')

    def to_record(self) -> dict:
        return {
            'actions': self.actions,
            'context': self.context.to_record() if self.context else None,
            'perfSummary': self.perf_summary if self.perf_summary is not None else None
        }

    @classmethod
    def from_record(cls, record: Dict[str, Any]):
        return cls(
            record['actions'],
            _Context.from_record(record['context']),
            record.get('perfSummary')
        )


def load(settings: AuraSettings,
         client: HttpClient,
         domain: str):
    params = {
        'aura.token': settings.aura_token,
        'aura.context': settings.to_json(),
        'message': QUERY_COMPONENT
    }

    uri = form_https_uri(domain, "aura", "preloadActions")
    data = encode_form_data(params)
    resp = client.post(uri.to_url(), MediaType.X_WWW_FORM_URLENCODED,
                       accept_type=MediaType.JSON,
                       body=data)
    preload_actions = _PreloadActions.from_record(json.loads(resp.body))
    if settings.uad is None:
        settings.uad = preload_actions.uad
    if settings.app_context_id is None:
        settings.app_context_id = preload_actions.app_context_id
        settings.density = preload_actions.density
