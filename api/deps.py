"""
Dependency condivisa: verifica DASHBOARD_TOKEN su ogni route API.
Il token può arrivare come:
  - Header:       X-Dashboard-Token: <token>
  - Query param:  ?token=<token>

Se DASHBOARD_TOKEN non è impostato nel .env, l'autenticazione è disabilitata
(utile in sviluppo locale senza .env configurato).
"""

import os
from fastapi import Header, Query, HTTPException, status
from typing import Optional

DASHBOARD_TOKEN = os.getenv("DASHBOARD_TOKEN", "")


def verify_token(
    x_dashboard_token: Optional[str] = Header(default=None),
    token: Optional[str] = Query(default=None),
):
    """Verifica il token di accesso alla dashboard."""
    # Se non è configurato nessun token, lascia passare tutto
    if not DASHBOARD_TOKEN:
        return

    provided = x_dashboard_token or token
    if not provided or provided != DASHBOARD_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token non valido o mancante.",
        )
