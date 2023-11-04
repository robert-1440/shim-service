from urllib.parse import urlparse

import utils.uri_utils
from better_test_case import BetterTestCase
from utils import path_utils
from utils.path_utils import Path, encode_for_url, decode_from_url, join_paths, parse_query_string


class MySuite(BetterTestCase):

    def test_path_splitter(self):
        self.assertEqual(['path', 'component'], path_utils.split_path("path/component"))
        self.assertEqual(['path', 'component'], path_utils.split_path("/path/component"))
        self.assertEqual(['path', 'component'], path_utils.split_path("/path//component"))

    def test_path_matcher(self):
        p = Path("/configuration-service/users/{userId}")
        url = "/configuration-service/users/the-user-id"
        match = p.matches(url)
        self.assertEqual({'userId': 'the-user-id'}, match)

        self.assertEqual({'userId': 'the-user-id'}, p.matches(url, path_utils.split_path(url)))

        self.assertIsNone(p.matches("/configuration-service/users/the-user-id/nope"))

        p = Path("/configuration-service/users")
        self.assertHasLength(0, p.matches("/configuration-service/users"))

        self.assertRaises(ValueError, lambda: Path("/configuration-service/users/{userId}/blah/{userId}"))

    def test_encode_for_url(self):
        self.assertEqual("foo%2Fbar", encode_for_url("foo/bar"))
        self.assertEqual("foo/bar", decode_from_url("foo%2Fbar"))
        self.assertEqual("me%401440.io", encode_for_url('me@1440.io'))
        self.assertEqual("me@1440.io", decode_from_url("me%401440.io"))

    def test_join_paths(self):
        self.assertEqual("a/b", join_paths("a", "b"))
        self.assertEqual("a/b", join_paths("a", "/b"))
        self.assertEqual("a/b", join_paths("a/", "/b"))

    def test_query_parameters(self):
        parsed = urlparse("https://hello.1440.io/services/search?name=First&last=Last")
        self.assertEqual({'name': 'First', 'last': 'Last'}, parse_query_string(parsed.query))

    def test_parse_query_string(self):
        self.assertIsNone(parse_query_string(None))
        self.assertHasLength(0, parse_query_string(""))
        self.assertEqual({'one': '1', 'two': '2'}, parse_query_string("one=1&two=2"))

    def test_get_path(self):
        self.assertEqual('/hello/world', path_utils.get_path("https://host.com/hello/world"))
        self.assertEqual('/hello/world', path_utils.get_path("https://host.com/hello/world?value=1"))

    def test_form_url(self):
        self.assertEqual('https://myhost.com/path',
                         utils.uri_utils.form_https_url('myhost.com', "path"))
        self.assertEqual('https://myhost.com/path?url=https%3A%2F%2Fsomehost.com%2Fpath',
                         utils.uri_utils.form_https_url('myhost.com', "path",
                                                        query_params={'url': 'https://somehost.com/path'}))
