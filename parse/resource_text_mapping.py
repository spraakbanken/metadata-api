"""Manual mapping from resource ID (machine name) to one or multiple html files containing resource descriptions.

The resources are stored in https://svn.spraakdata.gu.se/sb-arkiv/pub/resurstext meta-share/resource-texts.
If the description for a resource with machine name 'my-resource' is named 'my-resource_eng.html' or 'my-resource_swe.html'
it is found and used automatically. This mapping is a manual extension for files that do not follow the naming convention
and for resources that have their descriptions in multiple files.
"""

resource_mappings = {
    "abounderrattelser2012": {"sv": ["fisk.html", "fisk-abounderrattelser.html"]},
    "astranova": {"sv": ["fisk.html", "fisk-astranova.html"]},
    "at2012": {"sv": ["fisk.html", "fisk-alandstidningen.html"]},
    "barnlitteratur": {"sv": ["fisk.html", "fisk-barnlitteratur.html"]},
    "bloggmix1998": {"sv": ["bloggmix_swe.html"], "en": ["bloggmix_eng.html"]},
    "bloggmix1999": {"sv": ["bloggmix_swe.html"], "en": ["bloggmix_eng.html"]},
    "bloggmix2000": {"sv": ["bloggmix_swe.html"], "en": ["bloggmix_eng.html"]},
    "bloggmix2001": {"sv": ["bloggmix_swe.html"], "en": ["bloggmix_eng.html"]},
    "bloggmix2002": {"sv": ["bloggmix_swe.html"], "en": ["bloggmix_eng.html"]},
    "bloggmix2003": {"sv": ["bloggmix_swe.html"], "en": ["bloggmix_eng.html"]},
    "bloggmix2004": {"sv": ["bloggmix_swe.html"], "en": ["bloggmix_eng.html"]},
    "bloggmix2005": {"sv": ["bloggmix_swe.html"], "en": ["bloggmix_eng.html"]},
    "bloggmix2006": {"sv": ["bloggmix_swe.html"], "en": ["bloggmix_eng.html"]},
    "bloggmix2007": {"sv": ["bloggmix_swe.html"], "en": ["bloggmix_eng.html"]},
    "bloggmix2008": {"sv": ["bloggmix_swe.html"], "en": ["bloggmix_eng.html"]},
    "bloggmix2009": {"sv": ["bloggmix_swe.html"], "en": ["bloggmix_eng.html"]},
    "bloggmix2010": {"sv": ["bloggmix_swe.html"], "en": ["bloggmix_eng.html"]},
    "bloggmix2011": {"sv": ["bloggmix_swe.html"], "en": ["bloggmix_eng.html"]},
    "bloggmix2012": {"sv": ["bloggmix_swe.html"], "en": ["bloggmix_eng.html"]},
    "bloggmix2013": {"sv": ["bloggmix_swe.html"], "en": ["bloggmix_eng.html"]},
    "bloggmixodat": {"sv": ["bloggmix_swe.html"], "en": ["bloggmix_eng.html"]},
    "borgabladet": {"sv": ["fisk.html", "fisk-borgabladet.html"]},
    "bullen": {"sv": ["fisk.html", "fisk-bullen.html"]},
    "dalin": {"sv": ["dalinm_swe.html"], "en": ["dalinm_eng.html"]},
    "dn1987": {"sv": ["dn87_swe.html"]},
    "fanbararen": {"sv": ["fisk.html", "fisk-fanbararen.html"]},
    "finsktidskrift": {"sv": ["fisk.html", "fisk-finsktidskrift.html"]},
    "fnb1999": {"sv": ["fisk.html", "fisk-fnb.html"]},
    "fnb2000": {"sv": ["fisk.html", "fisk-fnb.html"]},
    "forumfeot": {"sv": ["fisk.html", "fisk-forum.html"]},
    "fsbbloggvuxna": {"sv": ["fisk.html", "fisk-bloggtexter.html"]},
    "fsbessaistik": {"sv": ["fisk.html", "fisk-essaistik.html"]},
    "fsbsakprosa": {"sv": ["fisk.html", "fisk-sakprosa_2006_2013.html"]},
    "fsbskonlit1960-1999": {"sv": ["fisk.html", "fisk-skonlitteratur_1960_1999.html"]},
    "fsbskonlit2000tal": {"sv": ["fisk.html", "fisk-skonlitteratur_2000-2013.html"]},
    "hankeiten": {"sv": ["fisk.html", "fisk-hankeiten.html"]},
    "hanken": {"sv": ["fisk.html", "fisk-hanken.html"]},
    "hbl1991": {"sv": ["fisk.html", "fisk-hufvudstadsbladet.html"]},
    "hbl1998": {"sv": ["fisk.html", "fisk-hufvudstadsbladet.html"]},
    "hbl1999": {"sv": ["fisk.html", "fisk-hufvudstadsbladet.html"]},
    "hbl20122013": {"sv": ["fisk.html", "fisk-hufvudstadsbladet.html"]},
    "informationstidningar": {"sv": ["fisk.html", "fisk-informationstidningar.html"]},
    "interfra": {"sv": ["interfra.html"]},
    "jakobstadstidning1999": {"sv": ["fisk.html", "fisk-jakobstadstidning.html"]},
    "jakobstadstidning2000": {"sv": ["fisk.html", "fisk-jakobstadstidning.html"]},
    "jft": {"sv": ["fisk.html", "fisk-jft.html"]},
    "kallan": {"sv": ["fisk.html", "fisk-kallan.html"]},
    "lagtexter": {"sv": ["fisk.html", "fisk-lagtexter.html"]},
    "magmakolumner": {"sv": ["fisk.html", "fisk-magmakolumner.html"]},
    "meddelanden": {"sv": ["fisk.html", "fisk-meddelanden.html"]},
    "myndighet": {"sv": ["fisk.html", "fisk-myndighetsprosa_1990-2000.html"]},
    "myndighet2": {"sv": ["fisk.html", "fisk-myndighetsprosa_2001-2013.html"]},
    "nyaargus": {"sv": ["fisk.html", "fisk-nyaargus.html"]},
    "osterbottenstidning2011": {"sv": ["fisk.html", "fisk-osterbottenstidning.html"]},
    "osterbottenstidning2012": {"sv": ["fisk.html", "fisk-osterbottenstidning.html"]},
    "osterbottenstidning2013": {"sv": ["fisk.html", "fisk-osterbottenstidning.html"]},
    "ostranyland": {"sv": ["fisk.html", "fisk-ostranyland.html"]},
    "pargaskungorelser2011": {"sv": ["fisk.html", "fisk-pargaskungorelser.html"]},
    "pargaskungorelser2012": {"sv": ["fisk.html", "fisk-pargaskungorelser.html"]},
    "parole": {"sv": ["parolekorpus_swe.html"], "en": ["parolekorpus_eng.html"]},
    "parolelexplus": {"sv": ["paroleplus_swe.html"], "en": ["paroleplus_eng.html"]},
    "press95": {"sv": ["press95_swe.html", "press_avd_swe.html"]},
    "press96": {"sv": ["press96_swe.html", "press_avd_swe.html"]},
    "press97": {"sv": ["press97_swe.html", "press_avd_swe.html"]},
    "press98": {"sv": ["press98_swe.html", "press_avd_swe.html"]},
    "propositioner": {"sv": ["fisk.html", "fisk-propositioner.html"]},
    "rom99": {"sv": ["norstedts_swe.html"]},
    "saltnld": {"sv": ["salt-dut-swe_swe.html"]},
    "soederwall-supp": {"sv": ["soederwall_supp_swe.html"], "en": ["soederwall_supp_eng.html"]},
    "studentbladet": {"sv": ["fisk.html", "fisk-studentbladet.html"]},
    "suc2": {"sv": ["suc_swe.html"], "en": ["suc_eng.html"]},
    "suc3": {"sv": ["suc_swe.html"], "en": ["suc_eng.html"]},
    "sv-treebank": {"sv": ["stb_swe.html"], "en": ["stb_eng.html"]},
    "svenskbygden": {"sv": ["fisk.html", "fisk-svenskbygden.html"]},
    "sydosterbotten2010": {"sv": ["fisk.html", "fisk-sydosterbotten.html"]},
    "sydosterbotten2011": {"sv": ["fisk.html", "fisk-sydosterbotten.html"]},
    "sydosterbotten2012": {"sv": ["fisk.html", "fisk-sydosterbotten.html"]},
    "sydosterbotten2013": {"sv": ["fisk.html", "fisk-sydosterbotten.html"]},
    "ungdomslitteratur": {"sv": ["fisk.html", "fisk-ungdomslitteratur.html"]},
    "vasabladet1991": {"sv": ["fisk.html", "fisk-vasabladet.html"]},
    "vasabladet2012": {"sv": ["fisk.html", "fisk-vasabladet.html"]},
    "vasabladet2013": {"sv": ["fisk.html", "fisk-vasabladet.html"]},
    "vastranyland": {"sv": ["fisk.html", "fisk-vastranyland.html"]},
}
