"""Test shared GitHub OIDC provider ownership across bootstrap updates."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[2] / 'deployment'))
spec = importlib.util.spec_from_file_location('sentinel_bootstrap', Path(__file__).parents[2] / 'deployment/bootstrap_github.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_existing_provider_ownership_survives_repeat_run(monkeypatch, tmp_path):
    calls = {}
    class Client:
        def get_caller_identity(self):
            return {'Account': '000000000000', 'Arn': 'arn:aws:iam::000000000000:role/test'}
        def get_open_id_connect_provider(self, **kwargs):
            return {'ClientIDList': ['existing-audience', 'sts.amazonaws.com']}
        def add_client_id_to_open_id_connect_provider(self, **kwargs):
            raise AssertionError('Existing audience must not be replaced or duplicated')
        def describe_stacks(self, **kwargs):
            return {'Stacks': [{'StackStatus': 'CREATE_COMPLETE', 'Parameters': [{'ParameterKey': 'CreateOidcProvider', 'ParameterValue': 'true'}]}]}
        def validate_template(self, **kwargs):
            return {}
        def update_stack(self, **kwargs):
            calls.update(kwargs)
    class Session:
        def __init__(self, *args):
            pass
        def client(self, name):
            return Client()
    monkeypatch.setattr(module, 'AwsSession', Session)
    monkeypatch.setattr(module.shutil, 'which', lambda name: '/usr/bin/aws')
    monkeypatch.setattr(module, 'wait_stack', lambda *a: {'DeployRoleArn': 'deploy', 'CloudFormationRoleArn': 'cfn', 'RuntimeBoundaryArn': 'boundary'})
    monkeypatch.chdir(tmp_path)
    module.bootstrap(SimpleNamespace(region='ap-south-1', stack='sentinel-payments', repository='ajay2005k/Multicurrency', github_subject='repo:ajay2005k@91924588/Multicurrency@1427070663:ref:refs/heads/main', fx_secret_arn=''))
    params = {item['ParameterKey']: item['ParameterValue'] for item in calls['Parameters']}
    assert params['CreateOidcProvider'] == 'true', 'Changing this to false would delete a shared provider owned by the stack'
    assert (tmp_path / 'github-variables.json').is_file()


def test_subject_accepts_observed_immutable_ids():
    module.validate_subject('ajay2005k/Multicurrency', 'repo:ajay2005k@91924588/Multicurrency@1427070663:ref:refs/heads/main')


def test_subject_rejects_other_repositories_branches_and_wildcards():
    import pytest
    for subject in [
        'repo:other@91924588/Multicurrency@1427070663:ref:refs/heads/main',
        'repo:ajay2005k@91924588/other@1427070663:ref:refs/heads/main',
        'repo:ajay2005k@91924588/Multicurrency@1427070663:ref:refs/heads/dev',
        'repo:ajay2005k/*:ref:refs/heads/main',
    ]:
        with pytest.raises(RuntimeError):
            module.validate_subject('ajay2005k/Multicurrency', subject)
