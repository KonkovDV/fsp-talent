"""Page policy. Scripts come only from this host: the static page has no inline script to nonce.

Style attributes stay allowed because a few layout widths are set on the element.
"""

POLICY = (
    "default-src 'self'; script-src 'self'; script-src-attr 'none'; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; "
    "font-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'self'; "
    "frame-ancestors 'none'"
)
