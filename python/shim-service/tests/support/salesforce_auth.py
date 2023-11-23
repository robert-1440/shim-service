import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import requests

from support import xml_utils
from support.persisted_cache import Expirable, PersistedCache
from utils.uri_utils import Uri


# url = "https://login.salesforce.com/services/Soap/u/55.0/"

class AuthInfo(Expirable):

    def __init__(self,
                 session_id: str,
                 server_url: str,
                 user_id: str,
                 org_id: str,
                 seconds_valid: int):
        self.server_url = server_url
        self.session_id = session_id
        self.user_id = user_id
        self.org_id = org_id
        self.seconds_valid = seconds_valid
        self.__origin: Optional[str] = None

    @property
    def origin(self):
        if not hasattr(self, "AuthInfo__origin") or self.__origin is None:
            self.__origin = Uri.parse(self.server_url).origin
        return self.__origin

    def get_ttl_seconds(self) -> int:
        return self.seconds_valid


auth_cache = PersistedCache(os.path.join(Path.home(), ".sfdc/auth-cache"))


@auth_cache.cached(3600)
def __auth(key: str = 'cdo') -> AuthInfo:
    file_name = os.path.join(Path.home(), f".sfdc/auth-settings-{key}.json")
    with open(file_name, "r") as f:
        settings = json.load(f)
    url = settings['url']
    username = settings['user']
    password = settings['password']
    token = settings.get('token')
    if token is not None:
        password += token

    headers = {'content-type': 'text/xml', 'SOAPAction': 'login'}
    xml = "<soapenv:Envelope xmlns:soapenv='http://schemas.xmlsoap.org/soap/envelope/' " + \
          "xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance' " + \
          "xmlns:urn='urn:partner.soap.sforce.com'><soapenv:Body>" + \
          "<urn:login><urn:username><![CDATA[" + username + \
          "]]></urn:username><urn:password><![CDATA[" + password + \
          "]]></urn:password></urn:login></soapenv:Body></soapenv:Envelope>"
    res = requests.post(url, data=xml, headers=headers, verify=False)

    element = ET.XML(res.content.decode('utf-8'))
    child = xml_utils.get_child(element, "Body/loginResponse/result")
    user_id = xml_utils.get_child(child, "userId").text
    session_id = xml_utils.get_child(child, "sessionId").text
    server_url = xml_utils.get_child(child, "serverUrl").text
    org_id = xml_utils.get_child(child, "userInfo/organizationId").text
    seconds_valid = int(xml_utils.get_child(child, "userInfo/sessionSecondsValid").text)

    if len(org_id) > 15:
        org_id = org_id[0:15:]

    return AuthInfo(session_id, server_url, user_id, org_id, seconds_valid)


def get_auth_info(key: str = 'cdo') -> AuthInfo:
    return __auth(key)
