"""The OIDC diagnostic must never print bearer tokens or non-allowlisted claims."""
import base64
import importlib.util
import io
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('sentinel_oidc_identity', Path(__file__).parents[2] / 'scripts/oidc_identity.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_identity_diagnostic_only_prints_safe_claims(monkeypatch, capsys):
    claims = {'iss': 'https://token.actions.githubusercontent.com', 'aud': 'sts.amazonaws.com', 'sub': 'repo:ajay2005k/Multicurrency:ref:refs/heads/main', 'repository': 'ajay2005k/Multicurrency', 'ref': 'refs/heads/main', 'sensitive_test_field': 'must-never-appear'}
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=')
    token = 'synthetic-header.' + payload + '.synthetic-signature'
    monkeypatch.setenv('ACTIONS_ID_TOKEN_REQUEST_URL', 'https://example.com/token?job=test')
    monkeypatch.setenv('ACTIONS_ID_TOKEN_REQUEST_TOKEN', 'synthetic-request-bearer')
    monkeypatch.setenv('TARGET_ROLE_ARN', 'arn:aws:iam::000000000000:role/test')
    def open_request(request, **kwargs):
        assert 'audience=sts.amazonaws.com' in request.full_url
        assert request.headers['Authorization'] == 'Bearer synthetic-request-bearer'
        return io.StringIO(json.dumps({'value': token}))
    monkeypatch.setattr(module, 'urlopen', open_request)
    module.main()
    output = capsys.readouterr().out
    assert claims['sub'] in output
    assert 'must-never-appear' not in output
    assert token not in output
    assert 'synthetic-request-bearer' not in output
