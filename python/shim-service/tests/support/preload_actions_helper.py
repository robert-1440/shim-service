import json

from mocks.extended_http_session_mock import ExtendedHttpMockSession
from services.sfdc.types.preload_actions import _Context, _ValuesProvider, _PreloadActions, QUERY_COMPONENT
from support.http_support import decode_form_data
from test_salesforce_utils import AURA_TOKEN_STRING, AURA_FRAMEWORK_ID
from utils.http_client import HttpRequest
from utils.uri_utils import decode_from_url

UAD = 10
APP_CONTEXT_ID = 'app-context-id'
DENSITY = 'some-density'

_GLOBAL_VALUE_PROVIDER = _ValuesProvider("$Global",
                                        {
                                            'appContextId': {
                                                'value': APP_CONTEXT_ID
                                            },
                                            'density': {
                                                'value': DENSITY
                                            }
                                        })
_CONTEXT = _Context(
    'mode',
    'app',
    'path_Prefix',
    'fwuid',
    42,
    UAD,
    'descriptorUids',
    {'foo': 'bar'},
    {'$Global': _GLOBAL_VALUE_PROVIDER}

)

_PRELOAD_ACTIONS = _PreloadActions(
    'whoknows',
    _CONTEXT,
    'perf-summary'
)

_JSON_CONTENT = json.dumps(_PRELOAD_ACTIONS.to_record())

# For some reason, we don't sent the full aura context as it was returned
# Go figure.
_EXPECTED_AURA_CONTEXT = {
    "fwuid": AURA_FRAMEWORK_ID,
    "mode": "PROD",
    "loaded": {
        "APPLICATION@markup://one:one": "d3iVMP6FYbZosAU6ofyg3g"
    },
    "app": "one:one"
}
_EXPECTED_BODY = {
    'aura.token': AURA_TOKEN_STRING,
    'aura.context': _EXPECTED_AURA_CONTEXT,
    'message': decode_from_url(QUERY_COMPONENT.content)
}


def prepare_preload_actions(http_session_mock: ExtendedHttpMockSession,
                            validate: bool = False):
    url = "https://somewhere.lightning.force.com/aura?preloadActions"

    def callback(request: HttpRequest):
        decoded = decode_form_data(request.body)
        decoded['aura.context'] = json.loads(decoded['aura.context'])

        if decoded != _EXPECTED_BODY:
            expected = json.dumps(_EXPECTED_BODY, indent=True)
            actual = json.dumps(decoded, indent=True)
            raise AssertionError(f"Body does not match.\nExpected:\n{expected}\nActual:\n{actual}.")
        # Make sure we can parse the json
        message = decoded['message']
        json.loads(message)

    http_session_mock.add_post_response(
        url,
        200,
        body=_JSON_CONTENT,
        expected_content_type='application/x-www-form-urlencoded',
        request_callback=callback if validate else None
    )
