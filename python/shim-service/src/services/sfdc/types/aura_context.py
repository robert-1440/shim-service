import json
from typing import Dict, Any, Optional, Union

from utils.http_client import HttpResponse
from utils.salesforce_utils import extract_aura_framework_id, extract_aura_context_json


class AuraContext:
    mode: str
    app: str
    loaded: dict[str, str]
    path_prefix: str
    style_context: Optional[Dict[str, Any]]

    def __init__(self, mode: str,
                 app: str,
                 loaded: Dict[str, str],
                 path_prefix: str,
                 style_context: Dict[str, Any] = None):
        self.mode = mode
        self.app = app
        self.loaded = loaded
        self.path_prefix = path_prefix
        self.style_context: Optional[Dict[str, Any]] = style_context

    def __eq__(self, other):
        if not isinstance(other, AuraContext):
            return False

        return (self.mode == other.mode and
                self.app == other.app and
                self.loaded == other.loaded and
                self.path_prefix == other.path_prefix and
                self.style_context == other.style_context)

    def __str__(self):
        return json.dumps(self.to_record(), indent=True)

    def __repr__(self):
        return self.__str__()

    def to_record(self) -> Dict[str, Any]:
        return {
            'mode': self.mode,
            'app': self.app,
            'pathPrefix': self.path_prefix,
            'loaded': self.loaded,
            'styleContext': self.style_context
        }

    def fill(self, record: Dict[str, Any]):
        record['mode'] = self.mode
        record['loaded'] = self.loaded
        record['app'] = self.app

    def to_json(self) -> str:
        return json.dumps(self.to_record())

    @classmethod
    def from_json(cls, json_data: Union[str, dict]) -> Optional[Any]:
        if json_data is None:
            return None
        if isinstance(json_data, str):
            json_data = json.loads(json_data)
        return cls(
            mode=json_data['mode'],
            app=json_data['app'],
            loaded=json_data['loaded'],
            path_prefix=json_data['pathPrefix'],
            style_context=json_data.get('styleContext')
        )


class AuraSettings:
    fwuid: Optional[str]
    aura_context: Optional[AuraContext]
    app_context_id: Optional[str]
    uad: Optional[int]
    density: Optional[str]
    aura_token: Optional[str]

    def __init__(self):
        self.fwuid = None
        self.aura_context = None
        self.app_context_id = None
        self.uad = None
        self.density = None
        self.aura_token = None

    def to_json(self) -> str:
        record = {'fwuid': self.fwuid}
        if self.aura_context is not None:
            self.aura_context.fill(record)
        if self.app_context_id is not None:
            record['dn'] = []
            record['globals'] = {
                'appContextId': self.app_context_id,
                'density': self.density
            }
            record['uad'] = self.uad != 0
        return json.dumps(record)

    def parse_links(self, response: HttpResponse):
        links = response.get_header_as_list('link')
        if links is not None and len(links) > 0:
            for link in links:
                if self.fwuid is None:
                    self.fwuid = extract_aura_framework_id(link)
                if self.aura_context is None:
                    self.aura_context = AuraContext.from_json(extract_aura_context_json(link))

                if self.fwuid is not None and self.aura_context is not None:
                    break
