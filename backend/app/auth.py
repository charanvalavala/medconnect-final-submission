import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import config

bearer = HTTPBearer(auto_error=False)


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 310000).hex()
    return f'pbkdf2_sha256$310000${salt}${digest}'


def verify_password(password, stored):
    try:
        algorithm, rounds, salt, digest = stored.split('$')
        if algorithm != 'pbkdf2_sha256':
            return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), int(rounds)).hex()
        return hmac.compare_digest(actual, digest)
    except (ValueError, AttributeError):
        return False


def create_token(user):
    now = datetime.now(timezone.utc)
    return jwt.encode({**user, 'sub': str(user['id']), 'iat': now, 'exp': now + timedelta(hours=4)},
                      config.JWT_SECRET, algorithm='HS256')


async def current_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials is None:
        raise HTTPException(401, 'Please sign in to continue.')
    try:
        payload = jwt.decode(credentials.credentials, config.JWT_SECRET, algorithms=['HS256'],
                             options={'require': ['sub', 'exp', 'iat', 'role']})
        user = {'id': int(payload['sub']), 'role': payload['role'], 'name': payload['name']}
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(401, 'Your session has expired. Please sign in again.')
    if user['role'] == 'Doctor':
        active = await request.app.state.pool.fetchval(
            "SELECT EXISTS(SELECT 1 FROM Doctors WHERE doctor_id = $1 AND status = 'Active')", user['id'])
        if not active:
            raise HTTPException(401, 'This doctor account is inactive.')
    elif user['role'] != 'Admin':
        raise HTTPException(403, 'This role is not supported.')
    return user


async def admin_user(user=Depends(current_user)):
    if user['role'] != 'Admin':
        raise HTTPException(403, 'This operation is available to clinic administration.')
    return user
