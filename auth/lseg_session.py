from __future__ import annotations

import os
import time


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
    deadline = time.monotonic() + 8.0
    state_name = getattr(getattr(session, "open_state", None), "name", "Unknown")
    while time.monotonic() < deadline:
        state_name = getattr(getattr(session, "open_state", None), "name", "Unknown")
        if state_name == "Opened":
            break
        if state_name in {"Closed", "Error"}:
            break
        time.sleep(0.1)

    if state_name != "Opened":
        try:
            session.close()
        except Exception:
            pass
        raise RuntimeError(f"LSEG session did not open successfully (state={state_name})")

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
