# acme-cert-updater

[![test](https://github.com/shogo82148/acme-cert-updater/actions/workflows/test.yml/badge.svg)](https://github.com/shogo82148/acme-cert-updater/actions/workflows/test.yml)

The acme-cert-updater automatically updates the certificate using ACME (Automated Certificate Management Environment) and Amazon Route 53.
It is a pre-build AWS Serverless Application of [Certbot](https://certbot.eff.org/) with [certbot-dns-route53](https://certbot-dns-route53.readthedocs.io/en/stable/) plugin.

## Usage

### Permission

The acme-cert-updater requires some SAM policy templates (S3ReadPolicy, S3CrudPolicy, and SNSPublishMessagePolicy),
and CAPABILITY_IAM Capabilities to use the Amazon Web Services Route 53 API.

### Deploy

The acme-cert-updater is available on [AWS Serverless Application Repository](https://serverlessrepo.aws.amazon.com/applications/arn:aws:serverlessrepo:us-east-1:445285296882:applications~acme-cert-updater).

Or here is a resource template of AWS Serverless Application Model.

```yaml
AWSTemplateFormatVersion: 2010-09-09
Transform: AWS::Serverless-2016-10-31

Resources:
  AcmeCertUpdater:
    Type: AWS::Serverless::Application
    Properties:
      Location:
        ApplicationId: arn:aws:serverlessrepo:us-east-1:445285296882:applications/acme-cert-updater
        SemanticVersion: 1.0.3
      Parameters:
        # S3 bucket name for saving the certificates (required)
        BucketName: YOUR_BUCKET_NAME

        # Comma separated list of domains to update the certificates (required)
        Domains: YOUR_DOMAINS

        # the S3 key of certificate
        # default: the first domain name of the Domains parameter
        CertName: YOUR_DOMAINS

        # Email address (required)
        Email: YOUR_EMAIL_ADDRESS

        # Amazon Route 53 Hosted Zone ID (required)
        HostedZone: YOUR_HOSTED_ZONE_ID

        # The Amazon SNS topic Amazon Resource Name (ARN) to which the updater reports events. (optional)
        Notification: ARN_SNS_TOPIC

        # url for acme server
        # default: https://acme-v02.api.letsencrypt.org/directory
        AcmeServer: https://acme-v02.api.letsencrypt.org/directory

        # execution environment
        # allowed values: production, staging
        # default: production
        Environment: production

        # Prefix of objects on S3 bucket.
        # default: "" (no prefix)
        Prefix: ""

        # Log level
        # allowed values: DEBUG, INFO, WARN, WARNING, ERROR, CRITICAL
        # default: ERROR
        LogLevel: ERROR
```

The following command will create a Cloudformation Stack and deploy the SAM resources.

```
aws cloudformation \
    --template-file template.yaml \
    --stack-name <STACK_NAME> \
    --capabilities CAPABILITY_AUTO_EXPAND CAPABILITY_IAM
```

### Download the certificate

[download-certificate.sh](https://github.com/shogo82148/acme-cert-updater/blob/master/download-certificate.sh) is a helper script for downloading the certificate.
It downloads the certificate, and executes the given command if the certificate is renewal.
Here is an example for reloading nginx.

```
./download-certificate.sh bucket-name example.com.json /etc/ssl/example.com systemctl reload nginx
```

bash, [AWS CLI](https://aws.amazon.com/cli/), and [jq](https://stedolan.github.io/jq/) are required.

## LICENSE

MIT License Copyright (c) 2019 Ichinose Shogo
