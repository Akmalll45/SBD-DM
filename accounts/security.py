import base64
import hashlib
import hmac
import re
import secrets
import struct
import time


def new_totp_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode('ascii').rstrip('=')


def matching_totp_counter(secret, code, now=None):
    if not re.fullmatch(r'\d{6}', code or ''):
        return None

    try:
        key = base64.b32decode(secret + '=' * (-len(secret) % 8), casefold=True)
    except (ValueError, TypeError):
        return None

    current_counter = int((time.time() if now is None else now) // 30)
    for counter in (current_counter - 1, current_counter, current_counter + 1):
        digest = hmac.new(key, struct.pack('>Q', counter), hashlib.sha1).digest()
        offset = digest[-1] & 0x0F
        value = struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7FFFFFFF
        if hmac.compare_digest(f'{value % 1_000_000:06d}', code):
            return counter
    return None


def session_key_hash(session_key, secret_key):
    return hmac.new(
        secret_key.encode('utf-8'),
        session_key.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
