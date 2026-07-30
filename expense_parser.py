import re
from dataclasses import dataclass


BANGLA_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


@dataclass(frozen=True)
class ParsedExpense:
    amount: float
    category: str


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.translate(BANGLA_DIGITS).strip())


def parse_expense(text: str, categories: tuple[str, ...]) -> ParsedExpense | None:
    normalized = normalize(text)
    match = re.fullmatch(r"৳?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s+(.+)", normalized)
    if not match:
        return None

    try:
        amount = float(match.group(1).replace(",", ""))
    except ValueError:
        return None
    if amount <= 0:
        return None

    supplied_category = match.group(2).strip()
    category_lookup = {normalize(category).casefold(): category for category in categories}
    category = category_lookup.get(supplied_category.casefold())
    if not category:
        return None

    return ParsedExpense(amount=amount, category=category)


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
