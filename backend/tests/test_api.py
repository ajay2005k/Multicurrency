import os
os.environ['DATABASE_PATH'] = ':memory:'
os.environ['FX_PROVIDER'] = 'demo'
from fastapi.testclient import TestClient
from backend.app import app
client = TestClient(app)
BASE = {'amount': 100, 'currency': 'USD', 'customer_id': 'test@example.com', 'merchant': 'Test store', 'country': 'US', 'billing_country': 'US'}

def post(body, key):
    return client.post('/api/payments/validate', json=body, headers={'Idempotency-Key': key})

def test_decisions_conversion_and_persistence():
    a = post(BASE, 'approve-key')
    assert a.status_code == 200 and a.json()['decision'] == 'approve'
    b = post({**BASE, 'amount': 3000, 'currency': 'EUR', 'device_new': True}, 'review-key')
    assert b.json()['decision'] == 'review'
    assert b.json()['usd_amount'] == 3260.87
    c = post({**BASE, 'amount': 15000, 'country': 'GB', 'device_new': True}, 'deny-key')
    assert c.json()['decision'] == 'deny'
    assert client.get('/api/transactions/' + c.json()['id']).json() == c.json()
    assert client.get('/api/transactions?decision=deny').json()['total'] >= 1
    assert client.get('/api/dashboard').json()['total'] >= 3

def test_idempotency_and_conflict():
    first = post(BASE, 'repeat-key')
    assert post(BASE, 'repeat-key').json() == first.json()
    assert post({**BASE, 'amount': 200}, 'repeat-key').status_code == 409

def test_invalid_and_missing():
    for patch in [{'amount': -1}, {'currency': 'XYZ'}, {'country': 'XX'}, {'amount': 1.111}]:
        assert post({**BASE, **patch}, 'invalid-key').status_code == 422
    assert client.post('/api/payments/validate', json=BASE).status_code == 422
    assert client.get('/api/transactions/missing').status_code == 404

def test_live_provider_fails_closed(monkeypatch):
    monkeypatch.setenv('FX_PROVIDER', 'exchangerate')
    monkeypatch.delenv('EXCHANGE_RATE_API_KEY', raising=False)
    assert post(BASE, 'no-live-key').status_code == 503

def test_velocity():
    body = {**BASE, 'customer_id': 'velocity@example.com'}
    for n in range(3):
        assert post(body, f'velocity-{n}').status_code == 200
    result = post(body, 'velocity-final').json()
    assert any('velocity' in r['signal'] for r in result['reasons'])

def test_auth(monkeypatch):
    monkeypatch.setenv('APP_API_KEY', 'test-secret')
    assert client.get('/api/dashboard').status_code == 401
    assert client.get('/api/dashboard', headers={'X-API-Key': 'test-secret'}).status_code == 200
    assert client.get('/api/health').status_code == 200

def test_provider_timeout_does_not_record_payment(monkeypatch):
    import httpx
    import backend.app as module
    before = len(module.store.all())
    monkeypatch.setenv('FX_PROVIDER', 'exchangerate')
    monkeypatch.setenv('EXCHANGE_RATE_API_KEY', 'synthetic-test-key')
    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout('simulated timeout')
    monkeypatch.setattr(module.httpx, 'get', timeout)
    assert post(BASE, 'timeout-key').status_code == 503
    assert len(module.store.all()) == before

def test_live_rate_conversion(monkeypatch):
    import backend.app as module
    import httpx
    monkeypatch.setenv('FX_PROVIDER', 'exchangerate')
    monkeypatch.setenv('EXCHANGE_RATE_API_KEY', 'synthetic-test-key')
    monkeypatch.setattr(module.httpx, 'get', lambda *a, **k: httpx.Response(200, request=httpx.Request('GET', 'https://example.com'), json={'result': 'success', 'conversion_rates': {'EUR': 0.8}}))
    result = post({**BASE, 'currency': 'EUR', 'amount': 80}, 'live-conversion').json()
    assert result['usd_amount'] == 100 and result['rate_source'] == 'live'

def test_lambda_health_adapter():
    from backend.app import handler
    event = {'version': '2.0', 'routeKey': '$default', 'rawPath': '/api/health', 'rawQueryString': '', 'headers': {'host': 'example.execute-api.us-east-1.amazonaws.com'}, 'requestContext': {'http': {'method': 'GET', 'path': '/api/health', 'sourceIp': '127.0.0.1'}, 'stage': '$default'}, 'isBase64Encoded': False}
    assert handler(event, {})['statusCode'] == 200

def test_dashboard_reports_live_fx(monkeypatch):
    monkeypatch.setenv('FX_PROVIDER', 'exchangerate')
    assert client.get('/api/dashboard').json()['fx_provider'] == 'live'

def test_secret_failure_does_not_record_payment(monkeypatch):
    import backend.app as module
    before = len(module.store.all())
    monkeypatch.setenv('FX_PROVIDER', 'exchangerate')
    monkeypatch.delenv('EXCHANGE_RATE_API_KEY', raising=False)
    monkeypatch.setenv('EXCHANGE_RATE_SECRET_ARN', 'arn:aws:secretsmanager:ap-south-1:000000000000:secret:synthetic')
    def denied(*args):
        raise RuntimeError('simulated inaccessible secret')
    monkeypatch.setattr(module, 'secret_exchange_key', denied)
    response = post(BASE, 'unavailable-secret')
    assert response.status_code == 503
    assert response.json()['detail'] == 'Live exchange-rate credentials are unavailable'
    assert len(module.store.all()) == before
