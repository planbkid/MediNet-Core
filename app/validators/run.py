import re


def normalize_run(value: str) -> str:
    """Valida formato y Módulo 11; no acredita identidad ni existencia."""
    value = value.strip()
    if not re.fullmatch(
        r"(?:[1-9][0-9]{6,7}-?[0-9Kk]|[1-9][0-9]?\.[0-9]{3}\.[0-9]{3}-?[0-9Kk])",
        value,
    ):
        raise ValueError("RUN: usar cuerpo de 7 u 8 dígitos sin ceros iniciales y DV")
    compact = value.replace(".", "").replace("-", "").upper()
    body, dv = compact[:-1], compact[-1]
    total = sum(int(digit) * (2 + index % 6) for index, digit in enumerate(reversed(body)))
    result = 11 - total % 11
    expected = "0" if result == 11 else "K" if result == 10 else str(result)
    if dv != expected:
        raise ValueError("RUN: dígito verificador incorrecto")
    return f"{body}-{dv}"
