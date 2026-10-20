#!/usr/bin/env python3
"""Display only non-secret OIDC identity metadata for trust-policy diagnosis.

The decoded claims are diagnostic data, not an authorization decision. AWS STS
verifies the actual token in the subsequent authentication step.
"""
import base64
import json
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


def main():
    parts = urlsplit(os.environ['ACTIONS_ID_TOKEN_REQUEST_URL'])
    query = dict(parse_qsl(parts.query))
    query['audience'] = 'sts.amazonaws.com'
    url = urlunsplit(parts._replace(query=urlencode(query)))
    request = Request(url, headers={'Authorization': 'Bearer ' + os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']})
    with urlopen(request, timeout=20) as response:
        token = json.load(response)['value']
    payload = token.split('.')[1]
    claims = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
    allowed = {name: claims.get(name) for name in ['iss', 'aud', 'sub', 'repository', 'ref', 'job_workflow_ref']}
    allowed['target_role'] = os.environ['TARGET_ROLE_ARN']
    text = json.dumps(allowed, separators=(',', ':'))
    text = text.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
    print('::notice title=GitHub OIDC identity metadata::' + text)


if __name__ == '__main__':
    main()
