"""The play token a browser game logs in with: "<name>.<expiry time>.<signature>", issued by the sign-in service
(docker/auth_service.py) after it has checked the password. The signature is an HMAC-SHA256 of "<name>.<expiry time>"
with the key both share (/ot/data/login_secret)."""
import hashlib
import hmac
import time


def nameFromToken(token, secret):
    """The player's name if the token is genuine and has not run out, otherwise None."""
    parts = token.rsplit('.', 2)
    if len(parts) != 3:
        return None
    name, expiry, signature = parts
    expected = hmac.new(secret, ('%s.%s' % (name, expiry)).encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature.encode(), expected.encode()):
        return None
    if not expiry.isdigit() or int(expiry) < time.time():
        return None
    return name
