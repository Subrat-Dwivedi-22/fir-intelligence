import re


def normalize_name(
    value: str | None,
) -> str | None:

    if not value:
        return None

    value = value.lower().strip()

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value


def normalize_phone(
    value: str | None,
) -> str | None:

    if not value:
        return None

    digits = re.sub(
        r"\D",
        "",
        value,
    )

    if (
        digits.startswith("91")
        and len(digits) == 12
    ):
        digits = digits[2:]

    if (
        digits.startswith("0")
        and len(digits) == 11
    ):
        digits = digits[1:]

    return digits