"""Update number of sentences and tokens in META-SHARE corpus files."""

import sys
import os
from urllib import request, parse
import json
from lxml import etree

BASE_URL = "https://ws.spraakbanken.gu.se/ws/korp/v8"


def get_corpus_info(corpora=None):
    if corpora:
        corpora = [c.upper() for c in corpora]
        data = {"corpus": ",".join(corpora)}
        req = request.Request(BASE_URL + "/corpus_info", parse.urlencode(data).encode("UTF-8"), method="POST")
    else:
        req = request.Request(BASE_URL + "/info")

    response = request.urlopen(req).read()
    response = json.loads(response)
    return response["corpora"]


def update_sizes(size_infos, metadata, corpus):
    updated = False

    for s in size_infos:
        size_unit = s.find("{http://www.ilsp.gr/META-XMLSchema}sizeUnit").text
        old_size = s.find("{http://www.ilsp.gr/META-XMLSchema}size")
        if size_unit == "tokens":
            new_size = metadata[corpus]["info"]["Size"]
        elif size_unit == "sentences":
            new_size = metadata[corpus]["info"]["Sentences"]

        if not old_size.text == new_size:
            updated = True
            print("[%s] Updating %s: %s --> %s" % (corpus, size_unit, old_size.text, new_size))
            old_size.text = new_size

    return updated


# Get filenames from command line
files = sys.argv[1:]
assert files, "Missing filename(s)."

# Most corpora names can be parsed from the filenames
requested_corpora = [os.path.basename(f).rsplit(".")[0].upper() for f in files]
available_corpora = get_corpus_info()
corpora = set(requested_corpora).intersection(set(available_corpora))
corpus_metadata = get_corpus_info(corpora)

updated_count = 0
error_count = 0

for f in files:
    corpus = os.path.basename(f).rsplit(".")[0].upper()
    tree = etree.parse(f)
    updated = False
    skip = False

    # Some corpora names need to be parsed from the XML files (normally only applies to parallel corpora)
    if corpus not in corpus_metadata:
        corpus_names = tree.findall(".//{http://www.ilsp.gr/META-XMLSchema}resourceShortName")
        corpus_languages = {}
        for cn in corpus_names:
            if cn.text.upper() in available_corpora:
                corpus_languages[cn.get("lang")] = cn.text.upper()
            else:
                print("Corpus %s not found." % cn.text.upper())
                error_count += 1
                skip = True
                break

        if skip:
            continue

        corpus_metadata2 = get_corpus_info(c.upper() for c in corpus_languages.values())
        language_infos = tree.findall(".//{http://www.ilsp.gr/META-XMLSchema}languageInfo")

        for li in language_infos:
            lang = li.find("{http://www.ilsp.gr/META-XMLSchema}languageId").text
            size_infos = li.findall(".//{http://www.ilsp.gr/META-XMLSchema}sizeInfo")
            updated_this = update_sizes(size_infos, corpus_metadata2, corpus_languages[lang])
            if updated_this:
                updated = True

        if updated:
            # Update the total sizes
            total_tokens = str(sum(int(corpus_metadata2[c]["info"]["Size"]) for c in corpus_languages.values()))
            total_sentences = str(sum(int(corpus_metadata2[c]["info"]["Sentences"]) for c in corpus_languages.values()))
            textinfo = tree.find(".//{http://www.ilsp.gr/META-XMLSchema}corpusTextInfo")
            size_infos = textinfo.findall("{http://www.ilsp.gr/META-XMLSchema}sizeInfo")
            update_sizes(size_infos, {corpus: {"info": {"Size": total_tokens, "Sentences": total_sentences}}}, corpus)
    else:
        size_infos = tree.findall(".//{http://www.ilsp.gr/META-XMLSchema}sizeInfo")
        updated = update_sizes(size_infos, corpus_metadata, corpus)

    if updated:
        updated_count += 1
        with open(f, mode="w") as outfile:
            outfile.write(etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding="UTF-8").decode("UTF-8"))

print("%d of %d files updated." % (updated_count, len(files)))
if error_count:
    print("%d unknown corpora." % error_count)
