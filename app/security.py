"""Webhook signatures — how a receiver knows a request is genuine.

This implements GitHub's scheme exactly:

    X-Hub-Signature-256: sha256=<hex of HMAC-SHA256(secret, raw body)>

The same idea is used by Shopify, Slack, Stripe, and the Standard Webhooks
spec — learn these two functions and you can verify most webhooks on the
internet. Unlike Twilio's scheme the URL is *not* signed, so it works
unchanged through tunnels and proxies.
"""

import hashlib
import hmac


def sign(secret: str, body: bytes) -> str:
    """Compute the signature a provider sends for a request body."""
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify(secret: str, body: bytes, signature: str | None) -> bool:
    """Check a received signature.

    compare_digest does a constant-time comparison — a naive ``==`` leaks
    how many leading characters were correct via response timing, which is
    enough to forge a signature byte by byte.
    """
    if not signature:
        return False
    return hmac.compare_digest(sign(secret, body), signature)
