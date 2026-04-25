from __future__ import annotations

import os


def get_credentials() -> tuple[str, str, str]:
    app_key = os.getenv("LSEG_APP_KEY", "")
    login = os.getenv("LSEG_LDP_LOGIN", "")
    password = os.getenv("LSEG_LDP_PASSWORD", "")

    missing = []
    if not app_key:
        missing.append("LSEG_APP_KEY")
    if not login:
        missing.append("LSEG_LDP_LOGIN")
    if not password:
        missing.append("LSEG_LDP_PASSWORD")

    if missing:
        raise ValueError(f"Missing credentials in .env: {', '.join(missing)}")

    return app_key, login, password


def open_lseg_session():
    import lseg.data as ld

    app_key, username, password = get_credentials()

    try:
        definition = ld.session.platform.Definition(
            app_key=app_key,
            grant=ld.session.platform.GrantPassword(username=username, password=password),
            signon_control=True,
        )
    except TypeError:
        definition = ld.session.platform.Definition(
            app_key=app_key,
            grant=ld.session.platform.GrantPassword(username=username, password=password),
        )

    session = definition.get_session()
    session.open()

    try:
        ld.session.set_default(session)
    except Exception:
        pass

    return session


def close_lseg_session(session) -> None:
    try:
        session.close()
    except Exception:
        pass
