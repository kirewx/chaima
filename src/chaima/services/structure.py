"""Rendering helpers for chemical structure SVGs via RDKit."""

from __future__ import annotations

import re


class InvalidSmilesError(ValueError):
    """Raised when RDKit cannot parse the provided SMILES string."""


_RE_BLACK_HEX_LONG = re.compile(r"#000000\b", re.IGNORECASE)
_RE_BLACK_HEX_SHORT = re.compile(r"#000\b", re.IGNORECASE)
_RE_BLACK_RGB = re.compile(r"rgb\s*\(\s*0\s*,\s*0\s*,\s*0\s*\)", re.IGNORECASE)
_RE_BLACK_WORD = re.compile(
    r"(stroke|fill)\s*[:=]\s*['\"]?black['\"]?", re.IGNORECASE
)
_RE_OPAQUE_BG_RECT = re.compile(
    r"<rect[^>]*fill\s*=\s*['\"]#FFFFFF['\"][^>]*/>",
    re.IGNORECASE,
)
_RE_OPAQUE_BG_RECT_STYLE = re.compile(
    r"<rect[^>]*style\s*=\s*['\"][^'\"]*fill\s*:\s*#FFFFFF[^'\"]*['\"][^>]*/>",
    re.IGNORECASE,
)


def render_structure_svg(
    smiles: str,
    *,
    width: int = 300,
    height: int = 300,
) -> str:
    """Render a SMILES string to a theme-friendly SVG.

    The returned SVG has a transparent background and uses
    ``currentColor`` for stroke/fill instead of hard-coded black, so it
    adapts to light and dark mode through CSS.

    Parameters
    ----------
    smiles : str
        A SMILES string describing the molecule. Leading/trailing
        whitespace is stripped before parsing.
    width : int, optional
        Canvas width in pixels. Defaults to 300.
    height : int, optional
        Canvas height in pixels. Defaults to 300.

    Returns
    -------
    str
        An SVG document ready to serve with ``image/svg+xml``.

    Raises
    ------
    InvalidSmilesError
        If ``smiles`` is empty or RDKit cannot parse it.
    """
    from rdkit import Chem
    from rdkit.Chem.Draw import rdMolDraw2D

    if not smiles or not smiles.strip():
        raise InvalidSmilesError("SMILES is empty")

    mol = Chem.MolFromSmiles(smiles.strip())
    if mol is None:
        raise InvalidSmilesError(f"Unparseable SMILES: {smiles!r}")

    drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
    drawer.drawOptions().clearBackground = False
    drawer.DrawMolecule(mol)
    drawer.FinishDrawing()
    svg = drawer.GetDrawingText()

    svg = _RE_OPAQUE_BG_RECT.sub("", svg)
    svg = _RE_OPAQUE_BG_RECT_STYLE.sub("", svg)
    svg = _RE_BLACK_HEX_LONG.sub("currentColor", svg)
    svg = _RE_BLACK_HEX_SHORT.sub("currentColor", svg)
    svg = _RE_BLACK_RGB.sub("currentColor", svg)
    svg = _RE_BLACK_WORD.sub(r"\1:currentColor", svg)

    return svg
