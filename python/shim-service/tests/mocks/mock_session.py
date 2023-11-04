class MockSession:
    def __init__(self,
                 tenant_id: int,
                 session_id: str,
                 instance_url: str,
                 user_id: str,
                 access_token: str):
        self.instance_url = instance_url
        self.tenant_id = tenant_id
        self.session_id = session_id
        self.user_id = user_id
        self.access_token = access_token
