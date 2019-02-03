import os
import boto3
import os.path
import pathlib
import json
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
            '--config-dir', os.path.join(tmp, 'config-dir/'),
            '--work-dir', os.path.join(tmp, 'word-dir/'),
            '--logs-dir', os.path.join(tmp, 'logs-dir/'),
        ]
        if config.environment == 'production':
            input_array.append('--server')
            input_array.append(config.acme_server)
        else:
            input_array.append('--staging')
        certbot.main.main(input_array)
        save_cert(config, tmp)

s3 = boto3.resource('s3')
def save_cert(config, tmp):
    """upload the certificate files to Amazon S3"""
    bucket = s3.Bucket(config.bucket_name)
    domains = config.domains.split(',')
    for domain in domains:
        domain = domain.strip().replace('*.', '', 1)
        live = os.path.join(tmp, 'config-dir/live/', domain)
        bucket.upload_file(os.path.join(live, 'cert.pem'), 'cert.pem')
        bucket.upload_file(os.path.join(live, 'chain.pem'), 'chain.pem')
        bucket.upload_file(os.path.join(live, 'fullchain.pem'), 'fullchain.pem')
        bucket.upload_file(os.path.join(live, 'privkey.pem'), 'privkey.pem')

        config = {
            "accounts": {},
        }
        accounts_path = pathlib.Path(os.path.join(tmp, 'config-dir/accounts/'))
        for root, _, files in os.walk(str(accounts_path)):
            for name in files:
                path = pathlib.Path(root, name)
                config["accounts"][str(path.relative_to(accounts_path))] = path.read_text()
        bucket.put_object(
            Body = json.dumps(config),
            Key = domain + '.json',
            ContentType = 'application/json',
        )

def lambda_handler(event, context):
    return {}

if __name__ == "__main__":
    lambda_handler({}, None)
