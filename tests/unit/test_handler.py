import pytest
import secrets

from updater import app

class Config(object):
    def __init__(self):
        self._prefix = secrets.token_hex(16)

    @property
    def domains(self):
        return "*.shogo82148.com"

    @property
    def email(self) -> str:
        return "shogo82148@gmail.com"
    
    @property
    def bucket_name(self) -> str:
        return "shogo82148-acme-cert-updater-test"

    @property
    def prefix(self) -> str:
        return self._prefix

    @property
    def environment(self) -> str:
        return 'staging'

    @property
    def acme_server(self) -> str:
        return 'https://acme-v02.api.letsencrypt.org/directory'

def test_certonly():
    cfg = Config()
    app.certonly(cfg)
    app.renew(cfg)
