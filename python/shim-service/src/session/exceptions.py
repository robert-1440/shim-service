class SessionNotActiveException(Exception):
    def __init__(self):
        super(SessionNotActiveException, self).__init__("Session is no longer active")
