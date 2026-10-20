#!/usr/bin/env python3
"""Run inside AWS CloudShell. No AWS keys are requested or persisted."""
import argparse
import getpass
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import subprocess
import tempfile
import shutil
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid

ROOT = Path(__file__).resolve().parent

class AwsError(Exception):
    def __init__(self, code, message):
        self.response = {'Error': {'Code': code, 'Message': message}}
        super().__init__(code)


class AwsClient:
    """Use the AWS CLI already installed in CloudShell; no Python SDK needed."""
    def __init__(self, service, region):
        self.service = 's3api' if service == 's3' else service
        self.region = region

    def _run(self, arguments):
        result = subprocess.run(['aws', *arguments, '--region', self.region, '--no-cli-pager'], capture_output=True, text=True)
        if result.returncode:
            match = re.search(r'An error occurred \(([^)]+)\)', result.stderr)
            raise AwsError(match.group(1) if match else 'AwsCliError', result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def __getattr__(self, name):
        def operation(**parameters):
            # Sensitive CloudFormation parameters stay out of command arguments.
            # The temporary file is private and is removed after the AWS call.
            with tempfile.TemporaryDirectory(prefix='sentinel-') as directory:
                path = Path(directory) / 'request.json'
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, 'w') as stream:
                    json.dump(parameters, stream)
                return self._run([self.service, name.replace('_', '-'), '--cli-input-json', 'file://' + str(path), '--output', 'json'])
        return operation

    def upload_file(self, source, bucket, key, ExtraArgs=None):
        arguments = ['s3', 'cp', source, f's3://{bucket}/{key}', '--only-show-errors']
        for name, value in (ExtraArgs or {}).items():
            option = {'ContentType': '--content-type', 'CacheControl': '--cache-control'}[name]
            arguments.extend([option, value])
        return self._run(arguments)


class AwsSession:
    def __init__(self, region_name):
        self.region = region_name

    def client(self, name):
        return AwsClient(name, self.region)


def request(base, path, key=None, body=None):
    headers = {'Content-Type': 'application/json'}
    if key:
        headers['X-API-Key'] = key
    if body is not None:
        headers['Idempotency-Key'] = str(uuid.uuid4())
    req = Request(base + path, headers=headers, data=json.dumps(body).encode() if body is not None else None)
    with urlopen(req, timeout=40) as response:
        return json.load(response)


def wait_stack(client, name):
    deadline = time.monotonic() + 3600
    previous = None
    while time.monotonic() < deadline:
        stack = client.describe_stacks(StackName=name)['Stacks'][0]
        status = stack['StackStatus']
        if status != previous:
            print('Infrastructure:', status, flush=True)
            previous = status
        if status in ('CREATE_COMPLETE', 'UPDATE_COMPLETE'):
            return {item['OutputKey']: item['OutputValue'] for item in stack.get('Outputs', [])}
        if not status.endswith('_IN_PROGRESS'):
            raise RuntimeError('Stack did not complete. Inspect failed resources in AWS Console > CloudFormation > Events. Do not delete retained data to retry.')
        time.sleep(15)
    raise RuntimeError('Timed out waiting for infrastructure; inspect CloudFormation before retrying.')


def workspace_key(non_interactive=False):
    key = os.environ.get('SENTINEL_WORKSPACE_ACCESS_KEY')
    if key:
        return key
    if non_interactive:
        raise RuntimeError('Set the SENTINEL_WORKSPACE_ACCESS_KEY GitHub Actions secret before deploying. Never put the key in a workflow file or command argument.')
    key = getpass.getpass('Choose a workspace access key (24+ characters; input is hidden): ')
    if getpass.getpass('Confirm the workspace access key: ') != key:
        raise RuntimeError('Access keys did not match. Nothing has been deployed.')
    return key


def deploy(args):
    if not re.fullmatch(r'[a-z][a-z0-9-]{2,23}', args.stack):
        raise RuntimeError('Use a lowercase stack name of 3–24 characters (letters, numbers, hyphens).')
    for required in ['backend.zip', 'hosting.yaml', 'web/index.html']:
        if not (ROOT / required).is_file():
            raise RuntimeError('Extract the complete deployment ZIP before running this script.')
    if not shutil.which('aws'):
        raise RuntimeError('Run this package in AWS CloudShell, which provides the AWS CLI and your authenticated AWS session.')
    session = AwsSession(region_name=args.region)
    account = session.client('sts').get_caller_identity()['Account']
    print(f'AWS session verified. Deployment region: {args.region}', flush=True)
    print('This creates pay-as-you-go S3, CloudFront, Lambda, API Gateway, DynamoDB, IAM and CloudWatch resources.', flush=True)
    key = workspace_key(args.non_interactive)
    if len(key) < 24:
        raise RuntimeError('Workspace access key must contain at least 24 characters. Run again and choose a longer key.')
    if bool(args.fx_secret_arn) != (args.fx_provider == 'exchangerate'):
        raise RuntimeError('For live FX supply both --fx-provider exchangerate and --fx-secret-arn. For reference rates omit both.')
    s3, cfn = session.client('s3'), session.client('cloudformation')
    bucket = f'{args.stack}-{account}-{args.region}-artifacts'
    try:
        s3.head_bucket(Bucket=bucket)
    except AwsError as error:
        if error.response.get('Error', {}).get('Code') not in ('404', 'NoSuchBucket', 'NotFound'):
            raise
        params = {'Bucket': bucket}
        if args.region != 'us-east-1':
            params['CreateBucketConfiguration'] = {'LocationConstraint': args.region}
        s3.create_bucket(**params)
    s3.put_public_access_block(Bucket=bucket, PublicAccessBlockConfiguration={'BlockPublicAcls': True, 'IgnorePublicAcls': True, 'BlockPublicPolicy': True, 'RestrictPublicBuckets': True})
    s3.put_bucket_encryption(Bucket=bucket, ServerSideEncryptionConfiguration={'Rules': [{'ApplyServerSideEncryptionByDefault': {'SSEAlgorithm': 'AES256'}}]})
    code = ROOT / 'backend.zip'
    object_key = 'lambda/' + hashlib.sha256(code.read_bytes()).hexdigest() + '.zip'
    print('Uploading Lambda deployment artifact…', flush=True)
    s3.upload_file(str(code), bucket, object_key)
    params = [
        {'ParameterKey': 'ArtifactBucket', 'ParameterValue': bucket},
        {'ParameterKey': 'BackendObjectKey', 'ParameterValue': object_key},
        {'ParameterKey': 'WorkspaceAccessKey', 'ParameterValue': key},
        {'ParameterKey': 'FxProvider', 'ParameterValue': args.fx_provider},
        {'ParameterKey': 'FxSecretArn', 'ParameterValue': args.fx_secret_arn},
    ]
    params.append({'ParameterKey': 'RuntimePermissionsBoundaryArn', 'ParameterValue': args.runtime_boundary_arn})
    common = {'StackName': args.stack, 'TemplateBody': (ROOT / 'hosting.yaml').read_text(), 'Parameters': params, 'Capabilities': ['CAPABILITY_IAM']}
    if args.cloudformation_role_arn:
        common['RoleARN'] = args.cloudformation_role_arn
    # Validate before creating the stack. This does not create AWS resources.
    cfn.validate_template(TemplateBody=common['TemplateBody'])
    try:
        existing = cfn.describe_stacks(StackName=args.stack)['Stacks'][0]
    except AwsError as error:
        if error.response.get('Error', {}).get('Code') != 'ValidationError' or 'does not exist' not in error.response['Error'].get('Message', ''):
            raise
        existing = None
    if existing:
        if not args.runtime_boundary_arn:
            for previous in existing.get('Parameters', []):
                if previous['ParameterKey'] == 'RuntimePermissionsBoundaryArn' and previous.get('ParameterValue'):
                    params[-1] = {'ParameterKey': 'RuntimePermissionsBoundaryArn', 'UsePreviousValue': True}
        if existing['StackStatus'] not in ('CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE'):
            raise RuntimeError('An existing stack needs attention. Inspect its CloudFormation Events before retrying.')
        try:
            cfn.update_stack(**common)
        except AwsError as error:
            if 'No updates are to be performed' not in error.response.get('Error', {}).get('Message', ''):
                raise
    else:
        cfn.create_stack(**common, EnableTerminationProtection=True, Tags=[{'Key': 'Project', 'Value': 'Sentinel'}])
    print('Provisioning HTTPS hosting and API. CloudFront can take several minutes.', flush=True)
    outputs = wait_stack(cfn, args.stack)
    frontend_bucket = outputs['FrontendBucketName']
    print('Uploading frontend…', flush=True)
    for file in sorted((ROOT / 'web').rglob('*')):
        if not file.is_file():
            continue
        path = file.relative_to(ROOT / 'web').as_posix()
        cache = 'no-cache' if path == 'index.html' else 'public, max-age=31536000, immutable'
        content_type = {'js': 'application/javascript', 'css': 'text/css', 'html': 'text/html; charset=utf-8'}.get(file.suffix[1:], mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
        s3.upload_file(str(file), frontend_bucket, path, ExtraArgs={'ContentType': content_type, 'CacheControl': cache})
    session.client('cloudfront').create_invalidation(DistributionId=outputs['DistributionId'], InvalidationBatch={'Paths': {'Quantity': 1, 'Items': ['/*']}, 'CallerReference': str(uuid.uuid4())})
    url = outputs['SiteUrl']
    print('Checking public HTTPS site and API…', flush=True)
    for attempt in range(30):
        try:
            with urlopen(url, timeout=30) as response:
                assert b'<div id="root">' in response.read()
            health = request(url, '/api/health')
            assert health['storage'] == 'dynamodb'
            break
        except (HTTPError, URLError, AssertionError, ValueError):
            if attempt == 29:
                raise RuntimeError('Infrastructure exists but public readiness checks have not passed. Re-run once CloudFront finishes, or inspect CloudWatch logs.')
            time.sleep(10)
    reference = str(uuid.uuid4())[:8]
    for name, amount, currency, country, billing, new in [('approve', 100, 'USD', 'US', 'US', False), ('review', 3000, 'EUR', 'DE', 'DE', True), ('deny', 15000, 'USD', 'GB', 'US', True)]:
        body = {'amount': amount, 'currency': currency, 'country': country, 'billing_country': billing, 'device_new': new, 'customer_id': f'launch-{reference}-{name}@example.com', 'merchant': 'Launch verification'}
        result = request(url, '/api/payments/validate', key, body)
        if result['decision'] != name:
            raise RuntimeError('A launch scenario returned an unexpected decision. Review the risk policy and current FX conversion.')
        print(f'Passed: {name} decision, conversion, and DynamoDB write', flush=True)
    for attempt in range(10):
        history = request(url, f'/api/transactions?search=launch-{reference}', key)
        if history['total'] == 3:
            break
        time.sleep(2)
    else:
        raise RuntimeError('Payments were processed but the persisted history check failed.')
    output = {'region': args.region, 'stack': args.stack, 'artifact_bucket': bucket, **outputs}
    (ROOT / 'deployment-output.json').write_text(json.dumps(output, indent=2) + '\n')
    print('\nDeployment verified. Live website: ' + url, flush=True)
    print('Open Workspace access and enter the key you chose. Do not share AWS credentials.', flush=True)
    print('Resource identifiers were saved to deployment-output.json; no keys were saved in that file.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--region', default='ap-south-1')
    parser.add_argument('--stack', default='sentinel-payments')
    parser.add_argument('--fx-provider', default='demo', choices=['demo', 'exchangerate'])
    parser.add_argument('--fx-secret-arn', default='')
    parser.add_argument('--non-interactive', action='store_true', help='Require SENTINEL_WORKSPACE_ACCESS_KEY from the process environment; never prompt')
    parser.add_argument('--cloudformation-role-arn', default='', help='Dedicated CloudFormation execution role for GitHub Actions')
    parser.add_argument('--runtime-boundary-arn', default='', help='Permissions boundary for the application Lambda role')
    args = parser.parse_args()
    try:
        deploy(args)
    except (AwsError, RuntimeError, HTTPError, URLError) as error:
        if isinstance(error, AwsError):
            print('AWS operation failed:', error.response.get('Error', {}).get('Code', 'Unknown'), file=sys.stderr)
            print('Check the current CloudShell role permissions and CloudFormation Events. Never send AWS keys in chat.', file=sys.stderr)
        elif isinstance(error, RuntimeError):
            print(str(error), file=sys.stderr)
        else:
            print('Deployment check failed:', type(error).__name__, file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
