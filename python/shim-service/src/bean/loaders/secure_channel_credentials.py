import certifi
from grpc import ssl_channel_credentials


def init():
    with open(certifi.where(), "rb") as f:
        return ssl_channel_credentials(f.read())
