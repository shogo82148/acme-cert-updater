import pytest

from updater import app

class TestConfig(object):
    @property
    def domains(self):
        return "*.shogo82148.com"

    @property
    def email(self) -> str:
        return "shogo82148@gmail.com"
    
    @property
    def bucket_name(self) -> str:
        return ""

    @property
    def prefix(self) -> str:
        return ""

    @property
    def environment(self) -> str:
        return 'staging'

    @property
    def acme_server(self) -> str:
        return 'https://acme-v02.api.letsencrypt.org/directory'

def test_certonly():
    app.certonly(TestConfig())
