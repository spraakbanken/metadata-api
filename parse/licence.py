"""Parsing the licence metadata."""

# Known licences in the META-SHARE standard
LICENCES = {
    'CC-BY': ('CC BY', 'https://creativecommons.org/licenses/by/4.0/'),
    'CC-BY-NC': ('CC BY-NC', 'https://creativecommons.org/licenses/by-nc/4.0/'),
    'CC-BY-NC-SA': ('CC BY-NC-SA', 'https://creativecommons.org/licenses/by-nc-sa/4.0/'),
    'CC-BY-SA': ('CC BY-SA', 'https://creativecommons.org/licenses/by-sa/4.0/'),
    'GFDL': ('GNU FDL', 'https://www.gnu.org/licenses/fdl.html'),
    # ...
}

def licence_name(name):
    if name in LICENCES:
        return LICENCES[name][0]
    return name

def licence_url(name):
    if name in LICENCES:
        return LICENCES[name][1]
