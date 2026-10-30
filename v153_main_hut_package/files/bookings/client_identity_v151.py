"""IP extraction under an explicit reverse-proxy trust contract.

Trusted proxies must overwrite X-Real-IP with their actual client address.
X-Forwarded-For and arbitrary direct-client headers are never used here.
"""
from ipaddress import ip_address, ip_network

from django.conf import settings


def _address(value):
    try:
        # Scoped IPv6 addresses and proxy chains are not client identities.
        if not value or "%" in value or "," in value:
            return None
        address = ip_address(value.strip())
        return address.ipv4_mapped if getattr(address, "ipv4_mapped", None) else address
    except (ValueError, TypeError, AttributeError):
        return None


def client_ip(request):
    raw_peer = request.META.get("REMOTE_ADDR") or ""
    peer = _address(raw_peer)
    unix_proxy = not raw_peer and getattr(settings, "TRUST_UNIX_PROXY", False)
    trusted_peer = peer is not None and any(peer in ip_network(cidr) for cidr in getattr(settings, "TRUSTED_PROXY_CIDRS", ()))
    if unix_proxy or trusted_peer:
        # A missing/malformed trusted header must not group clients under a proxy IP.
        forwarded = _address(request.META.get("HTTP_X_REAL_IP", ""))
        if forwarded and not (forwarded.is_loopback or forwarded.is_unspecified or forwarded.is_multicast):
            return str(forwarded)
        return None
    if peer and not (peer.is_loopback or peer.is_unspecified or peer.is_multicast):
        return str(peer)
    return None
