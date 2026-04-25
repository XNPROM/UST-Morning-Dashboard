# Source Generated with Decompyle++
# File: lseg_session.cpython-311.pyc (Python 3.11)

from __future__ import annotations
import os
import time

def get_credentials():
    app_key = os.getenv('LSEG_APP_KEY', '')
    login = os.getenv('LSEG_LDP_LOGIN', '')
    password = os.getenv('LSEG_LDP_PASSWORD', '')
    missing = []
    if not app_key:
        missing.append('LSEG_APP_KEY')
    if not login:
        missing.append('LSEG_LDP_LOGIN')
    if not password:
        missing.append('LSEG_LDP_PASSWORD')
    if missing:
        raise ValueError(f'Missing credentials in .env: {", ".join(missing)}')
    return (app_key, login, password)


def open_lseg_session():
    """Open an LSEG data session with retry."""
    ld = None
    try:
        import lseg.data
        ld = lseg.data
    except ImportError:
        raise ImportError('lseg.data package not available')
    (app_key, username, password) = get_credentials()
    definition = ld.session.platform.Definition(
        app_key=app_key,
        grant=ld.session.platform.GrantPassword(username=username, password=password),
        signon_control=True
    )
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            session = definition.get_open_platform_session()
            if session is not None:
                print(f'LSEG session opened (attempt {attempt}).')
                return session
        except Exception as e:
            print(f'LSEG session attempt {attempt} failed: {e}')
            if attempt < max_retries:
                time.sleep(5 * attempt)
    raise RuntimeError(f'Failed to open LSEG session after {max_retries} attempts.')


def close_lseg_session(session = None):
    if session is not None:
        try:
            session.close()
            print('LSEG session closed.')
        except Exception as e:
            print(f'Error closing LSEG session: {e}')
