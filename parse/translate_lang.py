"""Module for translating iso639-3 language codes into language names."""

import gettext

import pycountry

SWEDISH = gettext.translation("iso639-3", pycountry.LOCALES_DIR, languages=["sv"])


def get_lang_names(langcode: str) -> tuple[str, str]:
    """Get English and Swedish name for language represented by langcode.

    Args:
        langcode: The ISO 639-3 language code.

    Returns:
        A tuple containing the English and Swedish names of the language.
    """
    l = pycountry.languages.get(alpha_3=langcode)
    if l is None:
        raise LookupError
    english_name = l.name
    swedish_name = SWEDISH.gettext(english_name).lower()
    return english_name, swedish_name
