import gettext

import pycountry

SWEDISH = gettext.translation("iso639-3", pycountry.LOCALES_DIR, languages=["sv"])


LANG_LABEL_TO_SV = {
    "Albanian": "albanska",
    "Belarussian": "belarusiska",
    "Bosnian": "bosniska",
    "Bulgarian": "bulgariska",
    "Croatian": "kroatiska",
    "Czech": "tjeckiska",
    "Danish": "danska",
    "Dutch": "nederländska",
    "English": "engelska",
    "Esperanto": "esperanto",
    "Estonian": "estniska",
    "Faroese": "färöiska",
    "Finland Swedish": "finlandssvenska",
    "Finnish": "finska",
    "French": "franska",
    "German": "tyska",
    "Greek": "grekiska",
    "Hebrew": "hebreiska",
    "Italian": "italienska",
    "Japanese": "japanska",
    "Kurdish": "kurdiska",
    "Latin": "latin",
    "Latvian": "lettiska",
    "Lithuanian": "litauiska",
    "Lower Sorbian": "lågsorbiska",
    "Macedonian": "makedonska",
    "Maltese": "maltesiska",
    "Molise Slavic": "moliseslaviska",
    "Norwegian": "norska",
    "Old Norse": "fornnordiska",
    "Persian": "persiska",
    "Polish": "polska",
    "Portuguese": "portugisiska",
    "Romanian": "rumänska",
    "Russian": "ryska",
    "Serbian": "serbiska",
    "Slovak": "slovakiska",
    "Slovene": "slovenska",
    "Somali": "somaliska",
    "Spanish": "spanska",
    "Swedish": "svenska",
    "Turkish": "turkiska",
    "Turkmen": "turkmeniska",
    "Ukrainian": "ukrainska",
    "Upper Sorbian": "högsorbiska",
}


def translate(label):
    """Translate an English language label into Swedish."""
    return LANG_LABEL_TO_SV.get(label, "")


def get_lang_names(langcode):
    """Get English and Swedish name for language represented by langcode."""
    l = pycountry.languages.get(alpha_3=langcode)
    if l is None:
        raise LookupError
    english_name = l.name
    swedish_name = SWEDISH.gettext(english_name)
    return english_name, swedish_name
