import pytest
import secrets
import boto3
import time

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

    @property
    def notification(self) -> str:
        return 'arn:aws:sns:ap-northeast-1:445285296882:acme-cert-updater-test-UpdateTopic-141WK4DP5P40E'

def test_certonly():
    cfg = Config()
    assert app.needs_init(cfg) == True
    app.certonly(cfg)

    time.sleep(10)
    assert app.needs_init(cfg) == False
    app.renew(cfg)

    s3 = boto3.resource('s3')
    s3.Bucket(cfg.bucket_name).objects.filter(
        Prefix = cfg.prefix + '/',
    ).delete()

def test_notify():
    cfg = Config()
    app.notify(cfg, {
        'domain': 'shogo82148.com',
    }, 'fooobar.json')