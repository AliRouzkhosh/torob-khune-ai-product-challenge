"""Illustrative contact only. Never derives contact data from imported descriptions."""
from hashlib import sha256
from urllib.parse import urlsplit
from django.conf import settings


def demo_bale_url():
    url = settings.DEMO_BALE_URL
    try:
        parsed = urlsplit(url)
        # Never render script/data URLs or embedded credentials.
        return url if parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password else ''
    except ValueError:
        return ''


def get_demo_contact(listing):
    digest = sha256(str(listing.source_id or listing.pk).encode()).digest()
    return {'display_phone': f'09xx xxx xx{int.from_bytes(digest[:2], "big") % 100:02d}',
            'bale_url': demo_bale_url()}
