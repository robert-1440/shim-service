from better_test_case import BetterTestCase
from mocks.extended_http_session_mock import ExtendedHttpMockSession
from utils.http_client import create_client, HttpClient, HttpResponse, RequestBuilder, HttpMethod
from utils.uri_utils import Uri

ROOT = 'https://httpbin.org'


class HttpClientTests(BetterTestCase):
    client: HttpClient

    def test_cookies(self):
        self.get('cookies/set/sessioncookie/mycookie')
        uri = Uri.parse(ROOT)
        self.assertEqual('mycookie', self.client.find_cookie_value_by_uri(uri, 'sessioncookie'))

    def test_request_builder(self):
        mock = ExtendedHttpMockSession()
        client = self.client
        setattr(client, '_HttpClientImpl__session', mock)
        mock.capture_only = True
        rb = RequestBuilder(HttpMethod.GET, "https://somewhere.com/hello").timeout_seconds(80)
        rb.send(client)

        req = mock.requests_seen.pop(0)
        self.assertEqual(80, req.timeout_seconds)

    def get(self, uri: str) -> HttpResponse:
        while uri.startswith("/"):
            uri = uri[1::]

        url = f"{ROOT}/{uri}"
        return self.client.get(url)

    def setUp(self):
        self.client = create_client()
