# Automatic deployment from GitHub

After the one-time AWS/GitHub setup, merging or pushing a tested change to `main` publishes the existing website automatically. A laptop server, recurring CloudShell session, or ZIP upload is not required. Changes in a Codex workspace must still be committed and pushed to GitHub; unsaved or unpublished edits do not deploy.

## Pipeline

`.github/workflows/deploy.yml` runs backend/deployment tests, a production frontend build, and browser workflow checks for pull requests and pushes to `main`. Only trusted `main` runs can deploy. The deployment job is skipped until its AWS role variable is configured, so the initial pull request can be tested before AWS setup.

After checks pass, GitHub builds the Lambda package and frontend, exchanges its OIDC identity for a short-lived AWS session, updates the CloudFormation application stack, uploads frontend assets, invalidates CloudFront's cache, and checks the public payment workflow. The Actions run summary contains the website URL. Deployments run one at a time and are not canceled halfway through by a later push.

The AWS trust policy permits exactly `repo:ajay2005k/Multicurrency:ref:refs/heads/main` with audience `sts.amazonaws.com`. Pull requests and other repositories/branches cannot assume this role. Workflow dependencies are pinned to verified Git commit hashes. No workflow uses `pull_request_target`, and only the deployment job has `id-token: write`.

## One-time setup in AWS CloudShell

Once this code is on `main`, sign in to AWS, select **Mumbai (ap-south-1)**, open CloudShell, and run:

```bash
git clone https://github.com/ajay2005k/Multicurrency.git sentinel-ci
cd sentinel-ci
python3 deployment/bootstrap_github.py --region ap-south-1
```

Use a fresh destination folder if `sentinel-ci` already exists. For subsequent bootstrap updates, from the existing clean clone run `git pull --ff-only` and rerun the bootstrap script. Do not reset or discard local changes to update it.

For a private GitHub repository, use an authenticated clone through your existing GitHub login; do not paste credentials into chat or put a token in the clone URL. Alternatively use GitHub's Download ZIP once to obtain the setup script in CloudShell. Recurring application deployments will still use GitHub Actions without uploads.

Your CloudShell identity needs permission to create IAM OIDC providers, roles, inline policies, a managed permissions boundary, and a CloudFormation bootstrap stack. The script reuses an existing GitHub OIDC provider, preserving its audiences and adding `sts.amazonaws.com` only if needed. A provider created by this stack stays owned by that stack on repeat runs. AWS Academy/Learner Lab restrictions may require an instructor or account administrator to run this one-time setup.

The bootstrap creates:

- A GitHub deployment role restricted to this repository's `main` branch.
- A CloudFormation execution role for the application infrastructure.
- A permissions boundary limiting the Lambda role to the application's table, logs, and optional explicitly selected FX secret. The CloudFormation role cannot create an application role without this boundary or remove the boundary.

The deployment role does not have AdministratorAccess or permission to delete the application stack. S3, DynamoDB, Lambda, IAM role, and log access is limited by project resource names. CloudFront control-plane permissions and API Gateway management have broader scope within the account/region because AWS generates their resource identifiers. Protect `main`, review workflow/template changes, and limit repository write access: trusted main-branch code can change cloud infrastructure and read application data within these grants.

## Configure GitHub once

The bootstrap prints a JSON object containing **non-secret repository variables** and writes `github-variables.json`. These are role ARNs and settings, not credentials. You may share this JSON in the Codex task to have the repository variables configured, if GitHub write access is available.

In GitHub, open **Settings → Secrets and variables → Actions**.

Under **Variables**, add the printed values:

| Variable | Purpose |
|---|---|
| `AWS_DEPLOY_ROLE_ARN` | Role GitHub assumes using OIDC |
| `AWS_CLOUDFORMATION_ROLE_ARN` | Role CloudFormation uses to manage application resources |
| `AWS_RUNTIME_BOUNDARY_ARN` | Boundary applied to the application Lambda role |
| `AWS_REGION` | `ap-south-1` |
| `AWS_STACK_NAME` | `sentinel-payments`, or your existing application stack name |
| `FX_PROVIDER` | `demo`, or `exchangerate` when explicitly configured |
| `FX_SECRET_ARN` | Empty for reference rates; exact Secrets Manager ARN for live FX |

Under **Secrets**, create **`SENTINEL_WORKSPACE_ACCESS_KEY`**, with at least 24 characters. This is the application's workspace access key, not an AWS secret access key. Use the same key chosen during an earlier CloudShell application deployment to preserve access. Enter it directly into GitHub's secure secret editor; do not share it in chat or commit it.

No `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, or `AWS_SESSION_TOKEN` GitHub secrets are needed.

For live FX, run the bootstrap with `--fx-secret-arn YOUR_SECRET_ARN` so the boundary allows that specific secret, and set the printed variables. The secret must be a plain-text ExchangeRate API key in Secrets Manager in Mumbai, as described in `deployment/README.md`. Provider keys remain on the backend. Do not set live FX variables without updating the boundary.

If the initial application was deployed with a different stack name, pass that exact name to bootstrap with `--stack EXISTING_NAME` and use it in `AWS_STACK_NAME`. The same AWS account, region, and application stack preserve the CloudFront URL and DynamoDB table. Changing those settings can create another application.

## First deployment

Go to **Actions → Test and deploy Sentinel → Run workflow**, choose **main**, and run it. Subsequent pushes or merges to main start it automatically.

The first automatic deployment may create the application if it does not exist yet, or update the existing CloudShell-created stack. It adds the bounded Lambda role policy without replacing the database or CloudFront distribution. It creates three synthetic launch-verification payments each time it succeeds. Application AWS resources are billable; existing cleanup instructions still apply.

A green test job alone does not mean the website was published. The **Publish to AWS** job must also pass; it is intentionally skipped while the role variable is absent. The public URL appears in the successful deployment's run summary.

If a deployment fails, inspect the Actions run and CloudFormation Events. Do not delete retained data or change checks to make it pass. Correct the underlying configuration, rerun, and verify the live site.

## Daily use

1. Make and test a change in the repository.
2. Push a branch and open a pull request.
3. Merge it to main after checks pass.
4. Watch the Actions deployment; refresh the same website URL when it succeeds.

To pause automatic publication, remove `AWS_DEPLOY_ROLE_ARN` from repository variables. Tests continue running and deployment is skipped. Deleting the bootstrap stack does not delete the application stack, and deleting the application stack does not remove the GitHub bootstrap roles. The bootstrap stack has termination protection; disable it explicitly before removing those roles. A provider created by this stack is retained on deletion to protect other repositories that may use it. Check whether any other repository uses the shared OIDC provider before deleting that retained provider separately.
