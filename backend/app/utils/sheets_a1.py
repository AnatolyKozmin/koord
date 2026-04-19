"""A1-нотация для Google Sheets (Python)."""


def col_index_to_letters(index: int) -> str:
    """Индекс колонки 0-based: 0→A, 25→Z, 26→AA."""
    if index < 0:
        raise ValueError("column index must be >= 0")
    n = index + 1
    letters = ""
    while n:
        n, r = divmod(n - 1, 26)
        letters = chr(65 + r) + letters
    return letters


def quote_sheet_name(name: str) -> str:
    """Экранирование имени листа в диапазоне A1."""
    if "'" in name:
        name = name.replace("'", "''")
    if any(ch in name for ch in " '!") or not name:
        return f"'{name}'"
    return name
