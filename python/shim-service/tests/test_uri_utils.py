from better_test_case import BetterTestCase
from utils.uri_utils import form_https_uri, Uri, form_https_url, form_url_from_endpoint


class MySuite(BetterTestCase):

    def test_it(self):
        host = "myhost.com"
        uri = form_https_uri(host, '/path', query_params={'a': 'one'})
        self.assertEqual('https://myhost.com/path?a=one', uri.to_url())

        parsed_uri: Uri = Uri.parse(uri.to_url())
        self.assertEqual('https', parsed_uri.scheme)
        self.assertEqual('/path', parsed_uri.path)
        self.assertEqual('https://myhost.com', parsed_uri.origin)
        self.assertEqual({'a': 'one'}, parsed_uri.query_params)
        self.assertEqual(uri, parsed_uri)

    def test_strange(self):
        host = "myhost.com"
        uri = form_https_uri(host, '/path', query_params='odd')
        self.assertEqual('https://myhost.com/path?odd', uri.to_url())

    def test_form_url(self):
        url = form_https_url("somehost.com", "foo/bar",
                             {'a': 'one',
                              'b': 'two'})
        self.assertEqual("https://somehost.com/foo/bar?a=one&b=two", url)

        url = form_url_from_endpoint("https://somehost.com",
                                     "foo/bar",
                                     {'a': 'one',
                                      'b': 'two'})

        self.assertEqual("https://somehost.com/foo/bar?a=one&b=two", url)
