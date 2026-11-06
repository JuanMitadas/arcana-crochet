"""Text helpers for search.

Aurora DSQL has no ``unaccent`` or ``pg_trgm`` extensions, so accent-insensitive
search works on a column that is already normalized in Python (lowercase, no
accents) and typo suggestions are computed with ``difflib``.
"""

import difflib
import unicodedata


def normalizar(texto: str) -> str:
    """Lowercase, strip accents and collapse whitespace: "Coração  Azul" -> "coracao azul"."""
    decomposto = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return " ".join(sem_acento.casefold().split())


def semelhanca(termo: str, texto: str) -> float:
    """How close the closest word of ``texto`` is to any word of ``termo`` (0 to 1)."""
    palavras_termo = normalizar(termo).split()
    palavras_texto = normalizar(texto).split()
    melhor = 0.0
    for a in palavras_termo:
        for b in palavras_texto:
            melhor = max(melhor, difflib.SequenceMatcher(None, a, b).ratio())
    return melhor
