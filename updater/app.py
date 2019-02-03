import os
import boto3
import os.path
import pathlib
import json
import logging
import tempfile
import certbot.main
import configobj
from datetime import datetime

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
    tmppath = pathlib.Path(tmp)
    bucket = s3.Bucket(config.bucket_name)
    domains = config.domains.split(',')
    now = datetime.utcnow().isoformat()
    for domain in domains:
        domain = domain.strip().replace('*.', '', 1)
        live = os.path.join(tmp, 'config-dir/live/', domain)
        bucket.upload_file(os.path.join(live, 'cert.pem'), build_key(config.prefix, domain, now, 'cert.pem'))
        bucket.upload_file(os.path.join(live, 'chain.pem'), build_key(config.prefix, domain, now, 'chain.pem'))
        bucket.upload_file(os.path.join(live, 'fullchain.pem'), build_key(config.prefix, domain, now, 'fullchain.pem'))
        bucket.upload_file(os.path.join(live, 'privkey.pem'), build_key(config.prefix, domain, now, 'privkey.pem'))

        certconfig = {
            "accounts": {},
            "csr": {},
            "keys": {},
            "renewal": {},
        }

        accounts_path = pathlib.Path(os.path.join(tmp, 'config-dir/accounts/'))
        for root, _, files in os.walk(str(accounts_path)):
            for name in files:
                path = pathlib.Path(root, name)
                certconfig["accounts"][str(path.relative_to(accounts_path))] = path.read_text()
        csr_path = pathlib.Path(os.path.join(tmp, 'config-dir/csr/'))
        for root, _, files in os.walk(str(csr_path)):
            for name in files:
                path = pathlib.Path(root, name)
                certconfig["accounts"][str(path.relative_to(csr_path))] = path.read_text()
        keys_path = pathlib.Path(os.path.join(tmp, 'config-dir/keys/'))
        for root, _, files in os.walk(str(keys_path)):
            for name in files:
                path = pathlib.Path(root, name)
                certconfig["accounts"][str(path.relative_to(keys_path))] = path.read_text()

        renewal_config = configobj.ConfigObj(os.path.join(tmp, 'config-dir', 'renewal', domain + '.conf'))
        for key in ['archive_dir', 'cert', 'privkey', 'chain', 'fullchain']:
            certconfig[key] = str(pathlib.Path(certconfig[key]).relative_to(tmppath))
        for key in ['config_dir', 'work_dir', 'logs_dir']:
            certconfig['renewalparams'][key] = str(pathlib.Path(certconfig['renewalparams'][key]).relative_to(tmppath))
        for key, value in renewal_config.items():
            certconfig['renewal'][key] = value

        bucket.put_object(
            Body = json.dumps(certconfig),
            Key = build_key(config.prefix, domain + '.json'),
            ContentType = 'application/json',
        )

def build_key(*segment) -> str:
    path = "/".join(segment)
    path = path.replace("//", "/")
    if len(path) > 1 and path[0] == "/":
        path = path[1:]
    return path

def lambda_handler(event, context):
    return {}

if __name__ == "__main__":
    lambda_handler({}, None)
