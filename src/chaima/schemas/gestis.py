# src/chaima/schemas/gestis.py
from pydantic import BaseModel


class GestisResolveResult(BaseModel):
    """Result of resolving a chemical's CAS against the GESTIS index.

    Parameters
    ----------
    zvg : str or None
        GESTIS substance id, zero-padded to 6 chars (e.g. ``"010420"``),
        or None on miss / missing CAS / GESTIS unavailable.
    url : str or None
        Public EN deeplink built from ``zvg``, or None.
    """

    zvg: str | None
    url: str | None
