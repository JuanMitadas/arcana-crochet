"""UUID v7 generation (RFC 9562): sortable by time without revealing volume.

From Python 3.14 on, the standard library's ``uuid.uuid7`` is used.
"""

import os
import time
import uuid


def _uuid7_fallback() -> uuid.UUID:
    timestamp_ms = time.time_ns() // 1_000_000
    aleatorio = int.from_bytes(os.urandom(10), "big")  # 80 bits
    rand_a = aleatorio >> 68  # 12 bits
    rand_b = aleatorio & ((1 << 62) - 1)  # 62 bits
    valor = (timestamp_ms & ((1 << 48) - 1)) << 80
    valor |= 0x7 << 76  # version 7
    valor |= rand_a << 64
    valor |= 0b10 << 62  # RFC 9562 variant
    valor |= rand_b
    return uuid.UUID(int=valor)


uuid7 = getattr(uuid, "uuid7", _uuid7_fallback)
