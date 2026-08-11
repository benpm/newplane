# Mock Swing SSO Server - Test Guide

## Quick Start

```bash
cd scripts/mock_swing_sso_api
.venv/bin/python mock_swing_sso_server.py
```

Server runs at: `http://0.0.0.0:9001`

## Endpoints

| Endpoint                 | Method | Description             |
| ------------------------ | ------ | ----------------------- |
| `/cau/v1/idpw-authorize` | POST   | SSO authentication (main) |
| `/health`                | GET    | Health check            |

## God Mode Config

Configure at `http://localhost:3001/god-mode/authentication/swing-sso/`

| Key                     | Value                                                    |
| ----------------------- | -------------------------------------------------------- |
| SWING_SSO_URL           | `http://host.docker.internal:9001/cau/v1/idpw-authorize` |
| SWING_SSO_CLIENT_ID     | `TEST_CLIENT_ID`                                         |
| SWING_SSO_CLIENT_SECRET | `test-secret-123`                                        |
| SWING_SSO_COMPANY_CODE  | `sh`                                                     |

> **Note:** Use `host.docker.internal` — the Plane API runs inside Docker and needs to reach the host machine.

## Test Users

| Staff ID | Password    | Plane Email            | Name           |
| -------- | ----------- | ---------------------------- | -------------- |
| 10000001 | password123 | sh10000001@swing.local | Nguyen Van A   |
| 10000002 | password123 | sh10000002@swing.local | Tran Thi B     |
| 10000003 | password123 | sh10000003@swing.local | Le Van C       |
| 10000004 | admin@2024  | sh10000004@swing.local | Pham Admin     |
| 10000005 | admin@2024  | sh10000005@swing.local | Hoang Security |

## Testing with curl

```bash
# Health check
curl -s http://0.0.0.0:9001/health | python3 -m json.tool

# Successful auth
PASS_HASH=$(python3 -c "import hashlib; print(hashlib.sha256(b'password123').hexdigest())")
curl -s -X POST http://0.0.0.0:9001/cau/v1/idpw-authorize \
  -H "Content-Type: application/json" \
  -d "{\"common\":{\"companyCode\":\"sh\",\"clientId\":\"TEST_CLIENT_ID\",\"clientSecret\":\"test-secret-123\",\"employeeNo\":\"10000001\"},\"data\":{\"loginPassword\":\"$PASS_HASH\"}}" | python3 -m json.tool

# Auth with the wrong password
curl -s -X POST http://0.0.0.0:9001/cau/v1/idpw-authorize \
  -H "Content-Type: application/json" \
  -d "{\"common\":{\"companyCode\":\"sh\",\"clientId\":\"TEST_CLIENT_ID\",\"clientSecret\":\"test-secret-123\",\"employeeNo\":\"10000001\"},\"data\":{\"loginPassword\":\"wrong\"}}" | python3 -m json.tool
```

## Testing through the Plane UI

1. Open `http://localhost:3000` → the login page
2. Choose **Swing SSO**
3. Enter Staff ID `10000001` and password `password123`
4. On success you are redirected into the workspace

## Adding another user to the Plane DB

```bash
docker exec -i planeso-api-1 python manage.py shell <<'EOF'
from plane.db.models import User
email = "sh99999999@swing.local"
user, created = User.objects.get_or_create(
    email=email,
    defaults={"username": email, "first_name": "New", "last_name": "User", "display_name": "New User", "is_active": True, "is_password_autoset": True}
)
print(f"{'CREATED' if created else 'EXISTS'}: {email}")
EOF
```

Then add the matching user to `MOCK_USERS` in `mock_swing_sso_server.py` and restart the server.

## Reconfiguring the DB (if you need to reset)

```bash
docker exec planeso-api-1 python -c "
import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'plane.settings.local')
import django; django.setup()
from plane.license.models import InstanceConfiguration
configs = {
    'SWING_SSO_URL': 'http://host.docker.internal:9001/cau/v1/idpw-authorize',
    'SWING_SSO_CLIENT_ID': 'TEST_CLIENT_ID',
    'SWING_SSO_CLIENT_SECRET': 'test-secret-123',
    'SWING_SSO_COMPANY_CODE': 'VN',
    'IS_SWING_SSO_ENABLED': '1',
}
for k, v in configs.items():
    InstanceConfiguration.objects.update_or_create(key=k, defaults={'value': v, 'is_encrypted': False})
    print(f'  {k} = {v}')
print('Done!')
"
```

## Files

| File                       | Description                          |
| -------------------------- | ------------------------------------ |
| `mock_swing_sso_server.py` | Mock SSO server (Flask)              |
| `setup_mock_sso_users.py`  | Script that creates users in Plane DB |
| `sso_json_sample.md`       | Original spec from the Swing API docs |
| `.venv/`                   | Python venv with Flask               |
