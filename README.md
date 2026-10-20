# Sentinel · Multi-currency Payment Intelligence

A working payment-risk simulator with a React/TypeScript dashboard and a FastAPI backend. Submit synthetic payments in 10 currencies, normalize to USD, receive an explainable approve/review/deny decision, and inspect persistent transaction history.

**This app evaluates risk; it does not move money or authorize real payments.** Default rates are fixed demo references, not current market prices. Risk scores are deterministic heuristics, not trained probabilities. Amazon Fraud Detector is not integrated; its account availability must be verified before choosing that integration.

## Run locally

Requires Python 3.12+ and Node 22+.

```bash
python -m venv .venv
.venv/bin/pip install -r backend/requirements.lock.txt
npm ci --prefix frontend
./scripts/dev.sh
```

The development frontend runs on port 5173 and proxies `/api` to FastAPI on port 8000. The UI starts empty: use **Validate payment** to create data. SQLite persists to `.local/sentinel.db` (ignored by Git). OpenAPI documentation is served by the backend at `/docs`. Stop the development launcher with Ctrl-C.

## Verify

```bash
.venv/bin/python -m pytest backend/tests -q
npm run build --prefix frontend
```

Tests cover conversion, all three decisions, persistence, validation, idempotency, missing resources, payment velocity, API authentication, and fail-closed live-provider configuration.

## Features

- Overview with actual persisted volume, approval rate, average risk, 7-day activity, and decision distribution.
- Payment validation with amount/currency, customer reference, merchant, payment/billing countries, method, and device signal.
- Searchable transaction history, status filters, and detailed decision explanations.
- Duplicate-request protection: reuse an `Idempotency-Key` for a retry; changed payload with the same key returns 409.
- SQLite locally, DynamoDB on AWS; Lambda entry point via Mangum.
- Responsive layout, loading/error/empty states, accessible labels, keyboard-operable transaction rows.

## Try these scenarios

Use a different synthetic customer for each scenario to isolate history signals:

| Amount | Currency | Payment / billing country | New device | Expected |
|---|---|---|---|---|
| 100 | USD | US / US | No | Approve, score 5 |
| 3,000 | EUR | DE / DE | Yes | Review, score 40 |
| 15,000 | USD | GB / US | Yes | Deny, score 90 |

Thresholds: approve below 35, review 35–69, deny 70+. See the Risk insights screen or `backend/app.py` for every rule. Velocity uses the customer's prior persisted requests in the last 10 minutes. Idempotent retries do not add transactions.

## Configuration

`.env.example` documents names only. The backend reads process environment variables; it does not automatically load a `.env` file. Export configuration or supply it through your process manager. Never commit secrets.

- `FX_PROVIDER=demo` (default) or `exchangerate`.
- `EXCHANGE_RATE_API_KEY`: required for live conversion using ExchangeRate API's HTTPS v6 endpoint. Provider errors return 503 without recording the payment; no silent demo fallback.
- `DATABASE_PATH`: local SQLite path; default `.local/sentinel.db`.
- `STORAGE_BACKEND=dynamodb` and `TRANSACTIONS_TABLE`: enable AWS SDK storage. Uses the SDK's normal role/credential chain.
- `APP_API_KEY`: optional locally; when set, API requests require `X-API-Key`. Health remains public. Enter the key through the UI's Connection settings; it is stored only in session storage.
- `CORS_ORIGINS`: comma-separated exact frontend origins.
- `VITE_API_URL`: build-time frontend API base, configured in `frontend/.env.local` for separate hosting. No trailing slash. Never put secrets in Vite variables.

## AWS hosting and deployment

Use the prebuilt **CloudShell deployment package** to publish the frontend and backend without installing anything on your laptop. Read [deployment/README.md](deployment/README.md). It creates private S3 + CloudFront hosting, API Gateway, Lambda, DynamoDB, scoped IAM access, and CloudWatch logs. A single HTTPS domain serves the UI and `/api/*`.

The application uses a workspace access key for its restricted demonstration. The deployment script runs under the CloudShell AWS session; it never asks for AWS keys. It prints a public URL only after functional readiness checks pass. This is a prepared deployment path; no AWS deployment has been completed by this development session.

To reproduce the downloadable package from source, run `./scripts/package-cloudshell.sh`. The built artifact is `.deploy/sentinel-cloudshell.zip`. The script builds the frontend, installs dependencies for Lambda's Linux x86_64 / Python 3.12 runtime, and packages the deployment script, which uses CloudShell’s installed AWS CLI. The complete hosting template is `infra/hosting.yaml`; `infra/template.yaml` remains the optional API-only SAM example.

Live rates are optional. Configure an ExchangeRate API key in AWS Secrets Manager and pass its ARN as described in the deployment guide. The key is read on the backend and never bundled into the frontend.

For the recording script and service explanation, read [docs/FACULTY_DEMO.md](docs/FACULTY_DEMO.md).

## Current limits and next steps

- Shared workspace key access is suitable for a restricted demonstration, not multi-tenant production. Add Cognito/OIDC, per-user authorization, and audit records before exposing real customer data.
- DynamoDB listing/dashboard currently scans the table and aggregates in application memory. This is for small MVP datasets; add customer/time indexes, cursor pagination, and aggregate records before scaling.
- DynamoDB history reads use strong consistency, but velocity scoring is not atomic across Lambda instances. Idempotency writes are conditional, but high-concurrency fraud decisions require transactional counters or a dedicated risk service.
- No payment processor, human review workflow, chargebacks, trained fraud model, or real card-data collection is included.
- Live FX integration and AWS deployment require credentials and have not been validated locally. API responses intentionally avoid leaking provider credentials or upstream URLs.
- Retained DynamoDB tables survive stack deletion. Remove retained data separately only when intended.

Keep credentials in secure environment settings or use an AWS role. Never paste credentials into chat.

## Browser smoke test

With both development servers running and Chromium available:

```bash
CHROMIUM_PATH=/usr/bin/chromium npm run test:e2e --prefix frontend
```

Alternatively install Playwright's browser with `cd frontend && npx playwright install chromium` and omit `CHROMIUM_PATH`. Set `APP_URL` if the frontend uses a different port. The test creates one clearly named synthetic transaction and verifies its decision, searchable history, and mobile navigation. It does not delete application data.

## Automatic deployment

GitHub Actions tests every pull request and automatically publishes passing `main` changes through short-lived AWS OIDC credentials. One-time setup instructions are in [docs/AUTO_DEPLOY.md](docs/AUTO_DEPLOY.md). After activation, no recurring deployment ZIP uploads are needed; the existing website URL and transactions are preserved when deploying to the same account, region, and stack.
