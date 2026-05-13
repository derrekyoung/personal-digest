import ssl

import certifi


def _build_ssl_context() -> ssl.SSLContext:
    """
    Build an SSL context pinned to certifi's CA bundle.

    This avoids platform-specific certificate store issues (common on macOS
    Python installs) that can cause CERTIFICATE_VERIFY_FAILED errors.
    """
    return ssl.create_default_context(cafile=certifi.where())


SSL_CONTEXT = _build_ssl_context()
