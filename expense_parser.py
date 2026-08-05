import re
from dataclasses import dataclass


BANGLA_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_AMOUNT_START = re.compile(
    r"(?:^|\s)৳?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s+"
)


@dataclass(frozen=True)
class ParsedExpense:
    amount: float
    category: str


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.translate(BANGLA_DIGITS).strip())


def _clean_category(value: str) -> str | None:
    category = value.strip(" \t\r\n,;|:-–—।.!?")
    category = re.sub(r"\s+", " ", category)
    if not category or len(category) > 80:
        return None
    if not re.search(r"[A-Za-z\u0980-\u09FF]", category):
        return None
    return category


def _canonical_category(supplied: str, categories: tuple[str, ...]) -> str:
    lookup = {normalize(category).casefold(): category for category in categories}
    return lookup.get(normalize(supplied).casefold(), supplied)


def parse_expenses(text: str, categories: tuple[str, ...]) -> tuple[ParsedExpense, ...]:
    """Parse one or multiple `amount category` entries.

    Examples:
      500 খাবার
      500 খরচ 300 খাবার
      500 খরচ\n300 খাবার
    """
    normalized = normalize(text)
    if not normalized:
        return ()

    matches = list(_AMOUNT_START.finditer(normalized))
    if not matches:
        return ()

    # The first amount must begin the message. This avoids silently accepting
    # random prose before an amount.
    prefix = normalized[: matches[0].start()].strip()
    if prefix:
        return ()

    parsed: list[ParsedExpense] = []
    for index, match in enumerate(matches):
        category_end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
        supplied = _clean_category(normalized[match.end():category_end])
        if supplied is None:
            return ()
        try:
            amount = float(match.group(1).replace(",", ""))
        except ValueError:
            return ()
        if amount <= 0:
            return ()
        parsed.append(
            ParsedExpense(
                amount=amount,
                category=_canonical_category(supplied, categories),
            )
        )
    return tuple(parsed)


def parse_expense(text: str, categories: tuple[str, ...]) -> ParsedExpense | None:
    parsed = parse_expenses(text, categories)
    return parsed[0] if len(parsed) == 1 else None


def parse_amount_only(text: str) -> float | None:
    normalized = normalize(text)
    match = re.fullmatch(
        r"৳?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", normalized
    )
    if not match:
        return None
    try:
        amount = float(match.group(1).replace(",", ""))
    except ValueError:
        return None
    return amount if amount > 0 else None
