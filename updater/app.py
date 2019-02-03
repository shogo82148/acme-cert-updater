import os
import logging
import tempfile
import certbot.main

# set up the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class Config(object):
    @property
    def domains(self):
        return os.environ.get('UPDATER_DOMAINS')
    
    @property
    def email(self) -> str:
        return os.environ.get('UPDATER_EMAIL')
    
    @property
    def bucket_name(self) -> str:
        return os.environ.get('UPDATER_BUCKET_NAME')

    @property
    def prefix(self) -> str:
        return os.environ.get('UPDATER_PREFIX')

    @property
    def environment(self) -> str:
        return os.environ.get('UPDATER_ENVIRONMENT')

    @property
    def acme_server(self) -> str:
        return os.environ.get('UPDATER_ACME_SERVER', 'https://acme-v02.api.letsencrypt.org/directory')

def certonly(config):
    with tempfile.TemporaryDirectory() as tmp:
        input_array = [
            'certonly',
            '-n',
            '--agree-tos',
            '--email', config.email,
            '--dns-route53',
            '-d', config.domains,
            # TODO: use tmp
            '--config-dir', '/Users/shogoichinose/src/github.com/shogo82148/acme-cert-updater/.tmp/config-dir/',
            '--work-dir', '/Users/shogoichinose/src/github.com/shogo82148/acme-cert-updater/.tmp/work-dir/',
            '--logs-dir', '/Users/shogoichinose/src/github.com/shogo82148/acme-cert-updater/.tmp/logs-dir/',
        ]
        if config.environment == 'production':
            input_array.append('--server')
            input_array.append(config.acme_server)
        else:
            input_array.append('--staging')
        certbot.main.main(input_array)

def save_cert(config, tmp):
    # TODO: upload to S3
    pass

def lambda_handler(event, context):
    return {}

if __name__ == "__main__":
    lambda_handler({}, None)
