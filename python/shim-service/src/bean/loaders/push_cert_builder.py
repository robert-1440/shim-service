from firebase_admin.credentials import Certificate


def init():
    def build_it(content: str):
        return Certificate(content)

    return build_it
