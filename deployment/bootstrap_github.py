#!/usr/bin/env python3
"""One-time AWS setup for GitHub deployments. Run from the cloned repo in CloudShell."""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys
from deploy import AwsError, AwsSession, wait_stack


def validate_subject(repository, subject):
    match = re.fullmatch(r'repo:([A-Za-z0-9_.-]+)(?:@[0-9]+)?/([A-Za-z0-9_.-]+)(?:@[0-9]+)?:ref:refs/heads/main', subject)
    if not match or '/'.join(match.groups()) != repository:
        raise RuntimeError('The GitHub OIDC subject must identify this exact repository and refs/heads/main. Wildcards and other branches are not allowed.')


def bootstrap(args):
    if not shutil.which('aws'):
        raise RuntimeError('Run this command in AWS CloudShell, using your existing AWS login.')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repository):
        raise RuntimeError('Repository must have the form owner/repository.')
    if not re.fullmatch(r'[a-z][a-z0-9-]{2,23}', args.stack):
        raise RuntimeError('Application stack name must contain 3–24 lowercase letters, numbers, or hyphens.')
    validate_subject(args.repository, args.github_subject)
    session = AwsSession(args.region)
    identity = session.client('sts').get_caller_identity()
    partition = identity['Arn'].split(':')[1]
    provider_arn = f"arn:{partition}:iam::{identity['Account']}:oidc-provider/token.actions.githubusercontent.com"
    iam = session.client('iam')
    try:
        provider = iam.get_open_id_connect_provider(OpenIDConnectProviderArn=provider_arn)
        if 'sts.amazonaws.com' not in provider.get('ClientIDList', []):
            # Add the required audience without replacing other existing audiences.
            iam.add_client_id_to_open_id_connect_provider(OpenIDConnectProviderArn=provider_arn, ClientID='sts.amazonaws.com')
        create_provider = False
    except AwsError as error:
        if error.response['Error']['Code'] != 'NoSuchEntity':
            raise
        create_provider = True
    name = args.stack + '-github'
    cfn = session.client('cloudformation')
    try:
        existing = cfn.describe_stacks(StackName=name)['Stacks'][0]
    except AwsError as error:
        if error.response['Error']['Code'] != 'ValidationError' or 'does not exist' not in error.response['Error']['Message']:
            raise
        existing = None
    if existing:
        # Preserve ownership when this stack originally created the shared provider.
        create_provider = next((p['ParameterValue'] == 'true' for p in existing.get('Parameters', []) if p['ParameterKey'] == 'CreateOidcProvider'), False)
        if existing['StackStatus'] not in ('CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE'):
            raise RuntimeError('The bootstrap stack needs attention. Inspect its CloudFormation Events before retrying.')
    template = Path(__file__).resolve().parents[1] / 'infra/github-oidc.yaml'
    parameters = [
        {'ParameterKey': 'Repository', 'ParameterValue': args.repository},
        {'ParameterKey': 'GithubSubject', 'ParameterValue': args.github_subject},
        {'ParameterKey': 'ApplicationStack', 'ParameterValue': args.stack},
        {'ParameterKey': 'CreateOidcProvider', 'ParameterValue': str(create_provider).lower()},
        {'ParameterKey': 'FxSecretArn', 'ParameterValue': args.fx_secret_arn},
    ]
    print('Setting up GitHub OIDC, a deployment role, an infrastructure role, and a bounded Lambda runtime policy.', flush=True)
    print('Only main-branch workflows in ' + args.repository + ' will be trusted. No AWS keys are created.', flush=True)
    print('Exact trusted GitHub subject: ' + args.github_subject, flush=True)
    common = {'StackName': name, 'TemplateBody': template.read_text(), 'Parameters': parameters, 'Capabilities': ['CAPABILITY_NAMED_IAM']}
    cfn.validate_template(TemplateBody=common['TemplateBody'])
    if existing:
        try:
            cfn.update_stack(**common)
        except AwsError as error:
            if 'No updates are to be performed' not in error.response['Error']['Message']:
                raise
    else:
        cfn.create_stack(**common, EnableTerminationProtection=True, Tags=[{'Key': 'Project', 'Value': 'Sentinel'}])
    outputs = wait_stack(cfn, name)
    variables = {
        'AWS_DEPLOY_ROLE_ARN': outputs['DeployRoleArn'],
        'AWS_CLOUDFORMATION_ROLE_ARN': outputs['CloudFormationRoleArn'],
        'AWS_RUNTIME_BOUNDARY_ARN': outputs['RuntimeBoundaryArn'],
        'AWS_REGION': args.region,
        'AWS_STACK_NAME': args.stack,
        'FX_PROVIDER': 'exchangerate' if args.fx_secret_arn else 'demo',
        'FX_SECRET_ARN': args.fx_secret_arn,
    }
    target = Path('github-variables.json')
    target.write_text(json.dumps(variables, indent=2) + '\n')
    print('\nAWS setup complete. These are non-secret GitHub Actions VARIABLES:', flush=True)
    print(json.dumps(variables, indent=2), flush=True)
    print('\nSet these under GitHub repository Settings > Secrets and variables > Actions > Variables.', flush=True)
    print('Separately add SENTINEL_WORKSPACE_ACCESS_KEY as an Actions SECRET (24+ characters). Use your existing workspace key to keep browser access unchanged.', flush=True)
    print('Then run the Test and deploy Sentinel workflow on main, or push a new main-branch commit.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', default='ajay2005k/Multicurrency')
    parser.add_argument('--github-subject', default='repo:ajay2005k@91924588/Multicurrency@1427070663:ref:refs/heads/main', help='Exact main-branch sub claim from the workflow OIDC diagnostic')
    parser.add_argument('--region', default='ap-south-1')
    parser.add_argument('--stack', default='sentinel-payments')
    parser.add_argument('--fx-secret-arn', default='')
    args = parser.parse_args()
    try:
        bootstrap(args)
    except AwsError as error:
        print('AWS setup failed: ' + error.response['Error']['Code'], file=sys.stderr)
        print('Inspect CloudFormation Events or ask the AWS account administrator for the required IAM/CloudFormation permissions. Do not send credentials in chat.', file=sys.stderr)
        return 1
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
