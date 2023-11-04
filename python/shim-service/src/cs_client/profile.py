from typing import Optional

from cs_client import ServiceKeyCredentials


class Profile:
    def __init__(self, url: str, service_creds: Optional[ServiceKeyCredentials]):
        self.url = url
        self.service_creds = service_creds
