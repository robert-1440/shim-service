import json
from http.cookiejar import Cookie
from typing import Dict, Any, Callable, Optional, List

from better_test_case import BetterTestCase
from utils.salesforce_utils import extract_sf_sub_domain, extract_aura_token, extract_aura_context_json, \
    extract_aura_framework_id
from utils.uri_utils import Uri

AURA_FRAMEWORK_ID = "MDM0c01pMVUtd244bVVLc2VRYzQ2UWRkdk8xRWxIam5GeGw0LU1mRHRYQ3cyNDYuMTUuMi0zLjAuNA"

AURA_TOKEN_COOKIE_NAME = '_Host-ERIC_PROD3475335519753692748'

AURA_TOKEN_COOKIE_VALUE = ('eyJub25jZSI6ImdTMDQzenkyUXhVMWQtcVRGbHNzTHB5M1UxS0Y1LU9SdmpzeVBYTGs2amdcdTAwM2QiLCJ0eXAiOiJ'
                           'KV1QiLCJhbGciOiJIUzI1NiIsImtpZCI6IntcInRcIjpcIjAwRDFUMDAwMDAwT0h5UFwiLFwidlwiOlwiMDJHMVQwMD'
                           'AwMDBUaWVVXCIsXCJhXCI6XCJjYWltYW5zaWduZXJcIn0iLCJjcml0IjpbImlhdCJdLCJpYXQiOjE2OTgyNTMzODgxO'
                           'DQsImV4cCI6MH0=..i8-KSKyaEuMaW4oKa9d2nOW4MG5jQ-55EtFq3hzr_sM=')

AURA_TOKEN_STRING = ("eyJub25jZSI6ImdTMDQzenkyUXhVMWQtcVRGbHNzTHB5M1UxS0Y1LU9SdmpzeVBYTGs2amdcdTAwM2QiLCJ0eXAiOiJKV1Q"
                     "iLCJhbGciOiJIUzI1NiIsImtpZCI6IntcInRcIjpcIjAwRDFUMDAwMDAwT0h5UFwiLFwidlwiOlwiMDJHMVQwMDAwMDBUaW"
                     "VVXCIsXCJhXCI6XCJjYWltYW5zaWduZXJcIn0iLCJjcml0IjpbImlhdCJdLCJpYXQiOjE2OTgyNTMzODgxODQsImV4cCI6M"
                     "H0=..i8-KSKyaEuMaW4oKa9d2nOW4MG5jQ-55EtFq3hzr_sM=")

LINK = ("</l/%7B%22mode%22%3A%22PROD%22%2C%22app%22%3A%22one%3Aone%22%2C%22loaded%22%3A%7B%22APPLICATION%40markup%3A"
        "%2F%2Fone%3Aone%22%3A%22d3iVMP6FYbZosAU6ofyg3g%22%7D%2C%22styleContext%22%3A%7B%22c%22%3A%22other%22%2C%22x"
        "%22%3A%5B%22isDesktop%22%5D%2C%22tokens%22%3A%5B%22markup%3A%2F%2Fforce%3AsldsTokens%22%2C%22markup%3A%2F%2"
        "Fforce%3Abase%22%2C%22markup%3A%2F%2Fforce%3AoneSalesforceSkin%22%2C%22markup%3A%2F%2Fforce%3AlevelOneDensity"
        "%22%2C%22markup%3A%2F%2Fforce%3AthemeTokens%22%2C%22markup%3A%2F%2Fforce%3AformFactorLarge%22%5D%2C%22tuid"
        "%22%3A%22laXTvWAv_LY0aV39lbUdVg%22%2C%22cuid%22%3A-2017058372%7D%2C%22pathPrefix%22%3A%22%22%7D/app.css?2=>;"
        "rel=preload;as=style;nopush,<https://static.lightning.force.com/na236/auraFW/javascript/"
        "MDM0c01pMVUtd244bVVLc2VRYzQ2UWRkdk8xRWxIam5GeGw0LU1mRHRYQ3cyNDYuMTUuMi0zLjAuNA/aura_prod.js>;"
        "rel=preload;as=script,<https://static.lightning.force.com/na236/aurafile"
        "/%7B%22mode%22%3A%22PROD%22%2C%22app%22%3A%22one%3Aone%22%2C%22ls%22%3A1%2C%22lrmc%22%3A%22-386269907%22%7D/"
        "1gMLv-V5fAkTDQqQKJI-eQ/apppart1-4.js>;rel=preload;as=script,<https://static.lightning.force.com/na236/aurafile"
        "/%7B%22mode%22%3A%22PROD%22%2C%22app%22%3A%22one%3Aone%22%2C%22ls%22%3A1%2C%22lrmc%22%3A%22-386269907%22%7D/"
        "HMKoIp4VYYgorSAEtU4tgQ/apppart2-4.js>;rel=preload;as=script,<https://static.lightning.force.com/na236/aurafile"
        "/%7B%22mode%22%3A%22PROD%22%2C%22app%22%3A%22one%3Aone%22%2C%22ls%22%3A1%2C%22lrmc%22%3A%22-386269907%22%7D/"
        "M5UBrjZdY-tTz87GZPfUiQ/apppart3-4.js>;rel=preload;as=script,<https://static.lightning.force.com/na236/aurafile"
        "/%7B%22mode%22%3A%22PROD%22%2C%22app%22%3A%22one%3Aone%22%2C%22ls%22%3A1%2C%22lrmc%22%3A%22-386269907%22%7D/"
        "iPSE7SR6NJAfI-CEMOPSHw/apppart4-4.js>;rel=preload;as=script,</jslibrary/1698091350000/ui-analytics-reporting"
        "/EclairNG.js>;rel=prefetch;as=script;nopush,</jslibrary/1698091350000/canvas/CanvasRendering.js>;rel=prefetch"
        ";as=script;nopush")

AURA_CONTEXT = {"mode": "PROD", "app": "one:one",
                "loaded": {"APPLICATION@markup://one:one": "d3iVMP6FYbZosAU6ofyg3g"},
                "styleContext": {"c": "other", "x": ["isDesktop"],
                                 "tokens": ["markup://force:sldsTokens", "markup://force:base",
                                            "markup://force:oneSalesforceSkin", "markup://force:levelOneDensity",
                                            "markup://force:themeTokens", "markup://force:formFactorLarge"],
                                 "tuid": "laXTvWAv_LY0aV39lbUdVg", "cuid": -2017058372}, "pathPrefix": ""}


def extract(url: str) -> str:
    return extract_sf_sub_domain(Uri.parse(url))


class MockHttpClient:
    def __init__(self, cookies: Dict[str, str]):
        self.cookies: List[Cookie] = []
        for key, value in cookies.items():
            cookie = Cookie(
                0,
                name=key,
                value=value,
                port='',
                port_specified=False,
                domain='some.domain.com',
                domain_specified=False,
                domain_initial_dot=False,
                path='',
                path_specified=False,
                secure=True,
                expires=None,
                discard=False,
                comment=None,
                comment_url=None,
                rest={}
            )
            self.cookies.append(cookie)

    def find_first_cookie_match(self, matcher: Callable[[Cookie], bool]) -> Optional[Cookie]:
        for cookie in filter(matcher, self.cookies):
            return cookie
        return None


class TestSuite(BetterTestCase):

    def test_get_sub_domain(self):
        self.assertEqual('lagoon-ocean-1014',
                         extract('https://lagoon-ocean-1014.scratch.lightning.force.com'))
        self.assertEqual('webhooks-1440-dev-ed.develop',
                         extract('https://webhooks-1440-dev-ed.develop.my.salesforce.com'))

    def test_aura_token(self):
        cookies = {
            'some-cookie': 'some-value',
            AURA_TOKEN_COOKIE_NAME: AURA_TOKEN_COOKIE_VALUE
        }
        m: Any = MockHttpClient(cookies)

        token = extract_aura_token(m)
        self.assertEqual(AURA_TOKEN_STRING, token)

    def test_aura_context(self):
        context = extract_aura_context_json(LINK)
        self.assertEqual(AURA_CONTEXT, json.loads(context))

    def test_aura_framework_id(self):
        framework_id = extract_aura_framework_id(LINK)
        self.assertEqual(AURA_FRAMEWORK_ID, framework_id)
