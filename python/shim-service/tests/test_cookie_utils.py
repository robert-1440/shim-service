from requests.cookies import RequestsCookieJar

from better_test_case import BetterTestCase
from support import cookie_stuff
from utils import cookie_utils
from utils.uri_utils import Uri


class CookieSuite(BetterTestCase):

    def test_cookie(self):
        string = "oid=42; Domain=.example.com; Expires=Thu, 12-Jan-2027 13:55:08 GMT; Path=/"
        string2 = "sid=43; Domain=.example.com; Expires=Thu, 12-Jan-2027 13:55:08 GMT; Path=/main"
        string3 = "simple=100"
        jar = RequestsCookieJar()
        jar.set_cookie(cookie_stuff.parse_cookie(string))
        jar.set_cookie(cookie_stuff.parse_cookie(string2))
        jar.set_cookie(cookie_stuff.parse_cookie(string3))

        self.assertEqual("42", jar.get('oid'))
        self.assertEqual("42", jar.get('oid', domain='example.com'))
        self.assertEqual("42", jar.get('oid', domain='example.com', path="/"))

        uri = Uri.parse("https://example.com/")
        self.assertEqual("42", cookie_utils.find_cookie_for_uri(jar, uri, 'oid'))
        uri = Uri.parse("https://example.com/main")
        self.assertEqual("43", cookie_utils.find_cookie_for_uri(jar, uri, 'sid'))

        serialized = cookie_utils.serialize_cookie_jar(jar)

        new_jar = RequestsCookieJar()
        cookie_utils.deserialize_to_jar(new_jar, serialized)
