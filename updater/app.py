import os
import logging
import tempfile
import certbot.main

# set up the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# load settings
domains = os.environ.get('UPDATER_DOMAINS')
email = os.environ.get('UPDATER_EMAIL')
bucket_name = os.environ.get('UPDATER_BUCKET_NAME')
prefix = os.environ.get('UPDATER_PREFIX')
environment = os.environ.get('UPDATER_ENVIRONMENT')
acme_server = os.environ.get('UPDATER_ACME_SERVER', 'https://acme-v02.api.letsencrypt.org/directory')

def lambda_handler(event, context):
    with tempfile.TemporaryDirectory() as tmp:
        input_array = [
            'certonly',
            '-n',
            '--agree-tos',
            '--email', 'shogo82148@gmail.com',
            '--dns-route53',
            '-d', '*.shogo82148.com',
            '--config-dir', '/Users/shogoichinose/src/github.com/shogo82148/acme-cert-updater/.tmp/config-dir/',
            '--work-dir', '/Users/shogoichinose/src/github.com/shogo82148/acme-cert-updater/.tmp/work-dir/',
            '--logs-dir', '/Users/shogoichinose/src/github.com/shogo82148/acme-cert-updater/.tmp/logs-dir/',
            '--staging'
        ]
        certbot.main.main(input_array)
    return {}

if __name__ == "__main__":
    lambda_handler({}, None)
