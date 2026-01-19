from typing import Optional

import pycountry


def flag_to_iso(flag: str) -> Optional[str]:
    """Convert a flag emoji to a two-letter ISO 3166-1 alpha-2 code."""
    if len(flag) != 2:
        return None
    # Regional Indicator Symbol Letter A is 0x1F1E6
    # 'A' is 0x41
    # Offset is 0x1F1E6 - 0x41 = 127397
    OFFSET = 127397
    try:
        code = "".join(chr(ord(c) - OFFSET) for c in flag)
        return code if len(code) == 2 and code.isalpha() else None
    except ValueError:
        return None


def iso_to_flag(iso_code: str) -> str:
    """Convert a two-letter ISO 3166-1 alpha-2 code to a flag emoji."""
    OFFSET = 127397
    return "".join(chr(ord(c) + OFFSET) for c in iso_code.upper())


def country_to_flag(country_name: str) -> Optional[str]:
    """Look up a country by name and return its flag emoji."""
    try:
        # Fuzzy search might be nice, but pycountry provides exact/partial match
        # search_fuzzy returns a list
        results = pycountry.countries.search_fuzzy(country_name)
        if results:
            return iso_to_flag(results[0].alpha_2)
    except LookupError:
        pass
    return None


CUSTOM_FLAGS = {
    "AC": "Ascension Island",
    "CP": "Clipperton Island",
    "DG": "Diego Garcia",
    "EA": "Ceuta & Melilla",
    "EU": "European Union",
    "IC": "Canary Islands",
    "TA": "Tristan da Cunha",
    "XK": "Kosovo",
}


def get_country_name(iso_code: str) -> Optional[str]:
    """Get the common name of a country from its ISO code."""
    code = iso_code.upper()
    if code in CUSTOM_FLAGS:
        return CUSTOM_FLAGS[code]

    try:
        country = pycountry.countries.get(alpha_2=code)
        return country.name if country else None
    except LookupError:
        return None
