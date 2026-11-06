"""Transactions that survive Aurora DSQL's optimistic concurrency control.

DSQL doesn't block when two transactions touch the same rows: the one that commits
second fails with SQLSTATE 40001 (codes OC000/OC001 in the message) and has to run
again from the start. ``atomico`` does that for the outermost transaction; on
PostgreSQL it behaves exactly like ``transaction.atomic``.
"""

import random
import time
from functools import wraps

from django.db import DatabaseError, transaction

CODIGOS_OCC = {"40001", "OC000", "OC001"}


def conflito_occ(erro: BaseException) -> bool:
    """True when the error (or the driver error behind it) is an OCC conflict."""
    while erro is not None:
        if getattr(erro, "sqlstate", None) in CODIGOS_OCC or any(
            codigo in str(erro) for codigo in ("OC000", "OC001")
        ):
            return True
        erro = erro.__cause__
    return False


def atomico(func=None, *, tentativas: int = 4):
    """Like ``@transaction.atomic``, retrying the whole function on OCC conflicts.

    Only the outermost call retries: inside another transaction the conflict is
    raised so the outer ``atomico`` restarts everything. The function must be safe
    to run again, i.e. read what it needs from the database inside the transaction.
    """

    def decorador(funcao):
        @wraps(funcao)
        def envolvida(*args, **kwargs):
            if transaction.get_connection().in_atomic_block:
                with transaction.atomic():
                    return funcao(*args, **kwargs)
            for tentativa in range(1, tentativas + 1):
                try:
                    with transaction.atomic():
                        return funcao(*args, **kwargs)
                except DatabaseError as erro:
                    if tentativa == tentativas or not conflito_occ(erro):
                        raise
                    # Exponential backoff with jitter: 20-40 ms, 40-80 ms, 80-160 ms.
                    time.sleep(0.01 * 2**tentativa * (1 + random.random()))  # noqa: S311

        return envolvida

    return decorador(func) if func else decorador
