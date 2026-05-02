def find_first_json_object(text: str) -> str | None:
    """Devuelve el primer objeto JSON balanceado encontrado en text, o None."""
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                return text[start:i + 1]
    return None
