"""Verify the secure CloudShell CLI adapter without calling AWS."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

spec = importlib.util.spec_from_file_location('sentinel_deploy', Path(__file__).parents[2] / 'deployment/deploy.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_cli_adapter_keeps_sensitive_values_out_of_arguments(monkeypatch):
    seen = []
    def run(command, **kwargs):
        assert 'synthetic-workspace-key' not in ' '.join(command)
        file_arg = command[command.index('--cli-input-json') + 1]
        path = Path(file_arg.removeprefix('file://'))
        assert path.stat().st_mode & 0o777 == 0o600
        assert json.loads(path.read_text())['Parameters'][0]['ParameterValue'] == 'synthetic-workspace-key'
        seen.append(path)
        return SimpleNamespace(returncode=0, stdout='{"StackId":"test-stack"}', stderr='')
    monkeypatch.setattr(module.subprocess, 'run', run)
    result = module.AwsClient('cloudformation', 'ap-south-1').create_stack(Parameters=[{'ParameterKey': 'WorkspaceAccessKey', 'ParameterValue': 'synthetic-workspace-key'}])
    assert result['StackId'] == 'test-stack'
    assert not seen[0].exists()


def test_cli_errors_preserve_error_code_without_exposing_values(monkeypatch):
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=255, stdout='', stderr='An error occurred (AccessDenied) when calling the CreateStack operation: denied'))
    with pytest.raises(module.AwsError) as result:
        module.AwsClient('cloudformation', 'ap-south-1').create_stack(StackName='sentinel')
    assert str(result.value) == 'AccessDenied'
    assert result.value.response['Error']['Code'] == 'AccessDenied'


def test_upload_sets_frontend_content_and_cache_headers(monkeypatch):
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    monkeypatch.setattr(module.subprocess, 'run', run)
    module.AwsClient('s3', 'ap-south-1').upload_file('/tmp/index.html', 'example', 'index.html', ExtraArgs={'ContentType': 'text/html', 'CacheControl': 'no-cache'})
    command = commands[0]
    assert command[:3] == ['aws', 's3', 'cp']
    assert command[command.index('--content-type') + 1] == 'text/html'
    assert command[command.index('--cache-control') + 1] == 'no-cache'


def test_ci_requires_secret_without_prompting(monkeypatch):
    monkeypatch.delenv('SENTINEL_WORKSPACE_ACCESS_KEY', raising=False)
    monkeypatch.setattr(module.getpass, 'getpass', lambda *a: pytest.fail('CI must never prompt'))
    with pytest.raises(RuntimeError, match='SENTINEL_WORKSPACE_ACCESS_KEY'):
        module.workspace_key(non_interactive=True)


def test_ci_reads_workspace_key_from_environment(monkeypatch):
    monkeypatch.setenv('SENTINEL_WORKSPACE_ACCESS_KEY', 'synthetic-actions-workspace-key')
    monkeypatch.setattr(module.getpass, 'getpass', lambda *a: pytest.fail('Environment key must not prompt'))
    assert module.workspace_key(non_interactive=True) == 'synthetic-actions-workspace-key'


def test_interactive_access_key_confirmation(monkeypatch):
    monkeypatch.delenv('SENTINEL_WORKSPACE_ACCESS_KEY', raising=False)
    answers = iter(['first-synthetic-key', 'different-synthetic-key'])
    monkeypatch.setattr(module.getpass, 'getpass', lambda *a: next(answers))
    with pytest.raises(RuntimeError, match='did not match'):
        module.workspace_key()
