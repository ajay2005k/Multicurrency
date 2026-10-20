import hashlib
import json
import os
import sqlite3
import threading
import uuid
from functools import lru_cache
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from pydantic import BaseModel, Field

CURRENCIES = {'USD': 'US Dollar', 'EUR': 'Euro', 'GBP': 'British Pound', 'INR': 'Indian Rupee', 'JPY': 'Japanese Yen', 'CAD': 'Canadian Dollar', 'AUD': 'Australian Dollar', 'CHF': 'Swiss Franc', 'SGD': 'Singapore Dollar', 'AED': 'UAE Dirham'}
# Units of each currency per USD. Offline demonstration only.
DEMO_RATES = {'USD': 1, 'EUR': .92, 'GBP': .79, 'INR': 83.5, 'JPY': 151.2, 'CAD': 1.36, 'AUD': 1.53, 'CHF': .90, 'SGD': 1.35, 'AED': 3.6725}
COUNTRIES = {'US', 'GB', 'IN', 'DE', 'FR', 'JP', 'CA', 'AU', 'CH', 'SG', 'AE', 'BR', 'NG', 'ZA', 'CN', 'MX', 'NL', 'ES', 'IT'}
lock = threading.RLock()
app = FastAPI(title='Sentinel · Multi-currency Risk API', version='1.0.0')
app.add_middleware(CORSMiddleware, allow_origins=os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(','), allow_methods=['GET', 'POST'], allow_headers=['Content-Type', 'Idempotency-Key', 'X-API-Key'])


class Payment(BaseModel):
    amount: Decimal = Field(gt=0, le=100000000, max_digits=12, decimal_places=2)
    currency: str = Field(pattern='^[A-Z]{3}$')
    customer_id: str = Field(min_length=3, max_length=80, pattern=r'^[a-zA-Z0-9@._+-]+$')
    merchant: str = Field(min_length=2, max_length=80)
    country: str = Field(pattern='^[A-Z]{2}$')
    billing_country: str = Field(pattern='^[A-Z]{2}$')
    payment_method: Literal['card', 'bank_transfer', 'wallet'] = 'card'
    device_new: bool = False


class Store:
    def __init__(self):
        self.table = None
        if os.getenv('STORAGE_BACKEND', 'sqlite') == 'dynamodb':
            import boto3
            self.table = boto3.resource('dynamodb').Table(os.environ['TRANSACTIONS_TABLE'])
        else:
            path = os.getenv('DATABASE_PATH', str(Path(__file__).resolve().parent.parent / '.local' / 'sentinel.db'))
            if path != ':memory:':
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(path, check_same_thread=False)
            self.db.execute('CREATE TABLE IF NOT EXISTS transactions (id TEXT PRIMARY KEY, request_key TEXT UNIQUE, fingerprint TEXT, body TEXT NOT NULL)')
            self.db.commit()

    def all(self):
        if self.table:
            response = self.table.scan(ConsistentRead=True)
            items = response.get('Items', [])
            while 'LastEvaluatedKey' in response:
                response = self.table.scan(ExclusiveStartKey=response['LastEvaluatedKey'], ConsistentRead=True)
                items.extend(response.get('Items', []))
            return [json.loads(x['body']) for x in items]
        with lock:
            return [json.loads(row[0]) for row in self.db.execute('SELECT body FROM transactions')]

    def previous(self, key):
        if self.table:
            row = self.table.get_item(Key={'id': 'key#' + key}, ConsistentRead=True).get('Item')
            return (row['fingerprint'], json.loads(row['body'])) if row else None
        with lock:
            row = self.db.execute('SELECT fingerprint, body FROM transactions WHERE request_key=?', (key,)).fetchone()
            return (row[0], json.loads(row[1])) if row else None

    def put(self, key, fingerprint, body):
        if self.table:
            try:
                self.table.put_item(Item={'id': 'key#' + key, 'fingerprint': fingerprint, 'body': json.dumps(body)}, ConditionExpression='attribute_not_exists(id)')
            except self.table.meta.client.exceptions.ConditionalCheckFailedException:
                return False
            return True
        with lock:
            try:
                self.db.execute('INSERT INTO transactions VALUES (?, ?, ?, ?)', (body['id'], key, fingerprint, json.dumps(body)))
                self.db.commit()
                return True
            except sqlite3.IntegrityError:
                return False

store = Store()


@app.middleware('http')
async def api_auth(request, call_next):
    # Lambda deployment supplies an API key. Local demo is intentionally open.
    if request.method != 'OPTIONS' and request.url.path != '/api/health' and os.getenv('APP_API_KEY'):
        import secrets
        if not secrets.compare_digest(request.headers.get('x-api-key', ''), os.environ['APP_API_KEY']):
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail': 'A valid API key is required'}, status_code=401)
    return await call_next(request)


@lru_cache(maxsize=1)
def secret_exchange_key(secret_arn):
    import boto3
    # A plain-text Secrets Manager value; never returned in API payloads or logs.
    return boto3.client('secretsmanager').get_secret_value(SecretId=secret_arn)['SecretString']


def rates():
    if os.getenv('FX_PROVIDER', 'demo') == 'demo':
        return DEMO_RATES, 'demo', None
    if os.getenv('FX_PROVIDER') != 'exchangerate':
        raise HTTPException(503, 'Unsupported exchange-rate provider')
    key = os.getenv('EXCHANGE_RATE_API_KEY')
    if not key and os.getenv('EXCHANGE_RATE_SECRET_ARN'):
        try:
            key = secret_exchange_key(os.environ['EXCHANGE_RATE_SECRET_ARN'])
        except Exception:
            raise HTTPException(503, 'Live exchange-rate credentials are unavailable')
    if not key:
        raise HTTPException(503, 'Live exchange-rate credentials are not configured')
    try:
        response = httpx.get(f'https://v6.exchangerate-api.com/v6/{key}/latest/USD', timeout=8)
        response.raise_for_status()
        payload = response.json()
        if payload.get('result') != 'success':
            raise ValueError('Provider rejected request')
        return payload['conversion_rates'], 'live', payload.get('time_last_update_utc')
    except (httpx.HTTPError, ValueError, KeyError):
        raise HTTPException(503, 'Exchange-rate provider unavailable; payment was not processed')


def evaluate(payment, usd, history):
    score, reasons = 0, []
    def add(points, reason):
        nonlocal score
        score += points
        reasons.append({'signal': reason, 'points': points})
    if usd >= 10000:
        add(45, 'High-value payment: $10,000 or more')
    elif usd >= 2500:
        add(20, 'Elevated payment value: $2,500 or more')
    if payment.country != payment.billing_country:
        add(25, 'Payment location differs from billing country')
    if payment.device_new:
        add(15, 'Payment initiated from a new device')
    customer = [x for x in history if x['customer_id'] == payment.customer_id]
    recent = [x for x in customer if datetime.fromisoformat(x['created_at']) > datetime.now(timezone.utc) - timedelta(minutes=10)]
    if len(recent) >= 3:
        add(30, 'High velocity: at least 3 payments in the last 10 minutes')
    if any(x['decision'] == 'deny' for x in customer):
        add(20, 'Customer has a previously denied payment')
    if not customer:
        add(5, 'First payment from this customer')
    score = min(score, 100)
    return score, 'deny' if score >= 70 else 'review' if score >= 35 else 'approve', reasons


@app.get('/api/health')
def health():
    return {'status': 'ok', 'storage': os.getenv('STORAGE_BACKEND', 'sqlite'), 'fx_provider': os.getenv('FX_PROVIDER', 'demo'), 'risk_provider': 'rules-v1'}


@app.get('/api/currencies')
def currencies():
    return {'currencies': [{'code': code, 'name': name} for code, name in CURRENCIES.items()], 'countries': sorted(COUNTRIES)}


@app.post('/api/payments/validate')
def validate(payment: Payment, idempotency_key: str = Header(alias='Idempotency-Key', min_length=8, max_length=128)):
    if payment.currency not in CURRENCIES or payment.country not in COUNTRIES or payment.billing_country not in COUNTRIES:
        raise HTTPException(422, 'Unsupported currency or country')
    fingerprint = hashlib.sha256(payment.model_dump_json().encode()).hexdigest()
    previous = store.previous(idempotency_key)
    if previous:
        if previous[0] != fingerprint:
            raise HTTPException(409, 'Idempotency key already used for a different payment')
        return previous[1]
    exchange, source, as_of = rates()
    try:
        rate = Decimal(str(exchange[payment.currency]))
        if rate <= 0:
            raise ValueError()
        usd = float((payment.amount / rate).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
    except (KeyError, ValueError, ArithmeticError):
        raise HTTPException(503, 'Invalid or missing exchange rate')
    with lock:
        score, decision, reasons = evaluate(payment, usd, store.all())
        body = {**payment.model_dump(mode='json'), 'amount': float(payment.amount), 'id': 'TX-' + uuid.uuid4().hex[:12].upper(), 'created_at': datetime.now(timezone.utc).isoformat(), 'usd_amount': usd, 'exchange_rate': float(1 / rate), 'rate_source': source, 'rate_as_of': as_of, 'risk_score': score, 'decision': decision, 'reasons': reasons, 'risk_provider': 'rules-v1'}
        if not store.put(idempotency_key, fingerprint, body):
            existing = store.previous(idempotency_key)
            if not existing or existing[0] != fingerprint:
                raise HTTPException(409, 'Concurrent request conflict')
            return existing[1]
    return body


@app.get('/api/transactions')
def transactions(search: str = '', decision: Literal['all', 'approve', 'review', 'deny'] = 'all', limit: int = Query(100, ge=1, le=500)):
    items = sorted(store.all(), key=lambda x: x['created_at'], reverse=True)
    items = [x for x in items if (decision == 'all' or x['decision'] == decision) and (not search or search.lower() in ' '.join([x['id'], x['customer_id'], x['merchant'], x['currency']]).lower())]
    return {'items': items[:limit], 'total': len(items)}


@app.get('/api/transactions/{transaction_id}')
def transaction(transaction_id: str):
    for item in store.all():
        if item['id'] == transaction_id:
            return item
    raise HTTPException(404, 'Transaction not found')


@app.get('/api/dashboard')
def dashboard():
    items = store.all()
    counts = {d: sum(x['decision'] == d for x in items) for d in ['approve', 'review', 'deny']}
    days = [(datetime.now(timezone.utc) - timedelta(days=i)).date().isoformat() for i in reversed(range(7))]
    return {'total': len(items), 'volume_usd': round(sum(x['usd_amount'] for x in items), 2), 'counts': counts, 'approval_rate': round(100 * counts['approve'] / len(items), 1) if items else 0, 'avg_risk': round(sum(x['risk_score'] for x in items) / len(items), 1) if items else 0, 'daily': [{'date': day, 'volume': round(sum(x['usd_amount'] for x in items if x['created_at'].startswith(day)), 2), 'count': sum(x['created_at'].startswith(day) for x in items)} for day in days], 'currencies': [{'currency': c, 'count': sum(x['currency'] == c for x in items), 'volume': round(sum(x['usd_amount'] for x in items if x['currency'] == c), 2)} for c in CURRENCIES if any(x['currency'] == c for x in items)], 'fx_provider': 'live' if os.getenv('FX_PROVIDER') == 'exchangerate' else 'demo'}

handler = Mangum(app, lifespan='off')
