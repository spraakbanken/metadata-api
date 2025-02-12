# PID/DOI

Comments from SND are marked "SND:".

## Terminology - different sets of metadata

* data sets: previously called resources
* PID/DOI: the same thing in this project
* Datacite Metadata Schema: what we construct and send to Datacite to get (or update) a DOI
* [Metadata API]((https://github.com/spraakbanken/metadata-api)): Språkbanken Text's API for getting information out of
  our repo
* [SweClarin repository (Utter)](https://repo.spraakbanken.gu.se/xmlui/)

## Goal

* add PIDs to resource metadata (including collections)
* show them on spraakbanken.gu.se

## Method

* check Github Metadata repo for DOI
  * if not existing, add to Metadata YAML file by creating DMS
  * (add existing Handle if possible) No - Marcus' decision
  * update DMS and fix relation between Collection and members

In more technical detail:

* `update_metadata.sh` is called periodically by cron on k2
* calls `gen_pids.py`
* `gen_pids.py` should
  * read all data sets incl collections
  * iterate over all data sets incl collections
    * if data set has no AlternateIdentifier, lookup if it already has a Handle and set it
    * if data set has no PID generate a DOI (API call, see below)
  * iterate over all collections
    * collection: set DMS-12-RelatedIdentifier to HasPart for all members (found in resources field in YAML)
    * members: set DMS-12-RelatedIdentifier to IsPartOf for all collections
    * update DOI metadata (API call)

### gen_pids.py

* "unlisted" is respected
* update records at DataCite (check "updated" date)
* login saved in /home/fksbwww/.netrc.
* tag ”identifiers” in JSON is called ”alternateIdentifiers” in XML-formatet (<https://support.datacite.org/docs/what-is-the-identifiers-attribute-in-the-rest-api>)

### Datacite Metadata Schema (DMS)

This is what WE have to generate to get a DOI. Shouldn't be a problem as the Metadata in our repository is generously
populated. (Source: [DataCite Metadata Schema
Documentation](https://datacite-metadata-schema.readthedocs.io/_/downloads/en/4.5/pdf/))

M - Mandatory. R - recommended. 1 - 1 value allowed. n - multiple values allowed.

1. M1. Identifier. (10.21384/foo; "DOI"). Let DataCite autogen a DOI (4-4 chars)
   (<https://support.datacite.org/docs/api-create-dois>)
2. Mn. Creator. May be a corporate/institutional or personal name. (+ROR/ORCID) SND: "även där blir det nog Språkbanken
   Text"
3. Mn. Title. Title of dataset in multiple languages.
4. M1. Publisher. "Språkbanken Text"? Eller "Språkbanken"? (+ROR) SND: organisationen ansvarig för att tillhandlahålla
   resursen så i ert fall borde det vara Språkbanken Text då resurserna ligger i erat repositorie.
5. M1. PublicationYear. Not in YAML, but add it. Update later. Possibly weClarin repos can provide some dates.
6. Rn. Subject. språkteknologi; nyckelord (see below). Choose the 1st ("Svenska ...")
7. Rn. Contributor. The institution and/or person responsible for... (+ROR/ORCID). Wait.
8. Rn. Date. Several types. Wait.
9. O1. Language. Primary language. <https://en.wikipedia.org/wiki/List_of_ISO_639_language_codes>. Use 39.3!
10. M1. ResourceType. +subtype. Dataset/Collection; "Dataset"/"lexicon"
11. On. AlternateIdentifier: ex Handle. From SweClarin repos.
12. Rn. RelatedIdentifier. Id or related resources. Ex: IsVersionOf, HasPart/IsPartOf (collection - and vice versa),
    Obsoletes/IsObsoletedBy (successor!)
13. On. Size. Free format. State bytes and tokens.
14. On. Format. File ext or MIME type.
15. O1. Version. (leave out for now) Suggested practice: track major_version.minor_version. Register a new identifier
    for a major version change. Use with 11 and 12.
16. On. Rights.
17. Rn. Description. Take short description. Filter HTML.
18. Rn. GeoLocation. Named place or coord. SND: skulle nog skippa att fylla i något där.
19. On. Funding reference. VR?
20. On. RelatedItem. Where resource does not have an id.

Also see [the SND guide](https://zenodo.org/records/8355878).

#### Property ID 6. Subject/ämnesord

Mail from Olof:

Tog fram ett par förslag på ämnesord, några som vi använder i vår katalog och några andra som fungerar rent allmänt:

Allmänna ämesord för att beskriva att datasetet är inom språkteknologi:

```.xml
<subject subjectScheme="Standard för svensk indelning av forskningsämnen 2011" classificationCode="10208" xml:lang="en">Language Technology (Computational Linguistics)</subject>
<subject subjectScheme="ALLFO" valueURI="http://www.yso.fi/onto/yso/p6071" classificationCode="p6071" xml:lang="en">language technology</subject>
<subject subjectScheme="Wikidata" schemeURI="https://www.wikidata.org/wiki" valueURI="https://www.wikidata.org/wiki/Q1976109" xml:lang="en">language technology</subject>
```

Korpusar:

```.xml
<subject subjectScheme="ALLFO" valueURI="http://www.yso.fi/onto/yso/p21436" classificationCode="p21436" xml:lang="en">corpus linguistics</subject>
<subject subjectScheme="Wikidata" schemeURI="https://www.wikidata.org/wiki" valueURI="https://www.wikidata.org/wiki/Q865083" xml:lang="en">corpus linguistics</subject>
```

Lexikon:

```.xml
<subject subjectScheme="ALLFO" valueURI="http://www.yso.fi/onto/yso/p29365" classificationCode="p29365" xml:lang="en">lexical semantics</subject>
och/eller:
<subject subjectScheme="ALLFO" valueURI="http://www.yso.fi/onto/yso/p5183" classificationCode="p5183" xml:lang="en">lexicology</subject>
<subject subjectScheme="Wikidata" schemeURI="https://www.wikidata.org/wiki" valueURI="https://www.wikidata.org/wiki/Q18168594" xml:lang="en">lexicon</subject>
```

## Questions and things to fix

* Leif-Jöran:
  * map to Handles in Clarin repo. Create "lookup table" from Utter/SweClarin repo: en csv med kolumnerna
    dc.identifier.uri, dc.source.uri; urval: dc.publisher == "Språkbanken Text" men om du tar med alla så gör det inget
  * Leif-Jöran, Datacite credentials: user + login
  * DataCite Fabrica, add more about Språkbanken Text and add SM as contact
  * test account
* publication year (5): <https://github.com/spraakbanken/metadata-api/issues/21>
* ROR: <https://ror.org>, <https://ror.org/registry/>
* versioning?

## Drupal

* New fields (Drupal, Metadata API):
  * creator (list of free text "förnamn, efternamn")
  * created (text, 2025-06-09): do not set but use "updated" if necessary
  * updated (text, 2025-06-09)
* display: citation; show PID/link, or citation BibTex (can be autogenerated)
* start thinking about analysis (<https://github.com/spraakbanken/sbwebb-cms/issues/341#issue-2110221129>)

## Documentation

### Metadata repo and API

* find successors in directory YAML: grep -lzrP "successors:\n  - .+\n" .

### SND

* <https://snd.gu.se/sv/beskriv-och-dela-data/pid-tjanster-doi-epic>
* <https://snd.gu.se/sv/hantera-data/fardigstalla-tillgangliggora/PID>

### DataCite

* show record:
  <https://api.datacite.org/dois?client-id=SND.SPRKB&query=identifiers.identifier:standsriksdagen-adelsstandet%20AND%20identifiers.identifierType:slug&detail=true%22>
* REST API
  * create: <https://support.datacite.org/docs/api-create-dois>
  * update: <https://support.datacite.org/docs/updating-metadata-with-the-rest-api>
  * [test-prefix](https://support.datacite.org/docs/testing-guide), Support > Datacite.org > Support > Testing DOI
    domain, testprefix
  * create code examples: <https://support.datacite.org/reference/put_dois-id>
  * [API guide](https://support.datacite.org/docs/mds-api-guide)
  * SND: För API-anrop så har DataCite relativt snälla regler med en ganska hög gräns:
    <https://support.datacite.org/docs/is-there-a-rate-limit-for-making-requests-against-the-datacite-apis>. Ibland kan
    API:et ha väldigt hög belastning så kan ta lite tid med första körningen. Det går göra flera anrop för att updatera
    metadatan så om metadatan för en collection ska updateras med nya relatedIdentifier så är det bara att köra en nytt
    anrop med den nya metadatan.
* Datacite Metadata Schema
  * <https://datacite-metadata-schema.readthedocs.io/en/4.5/>
  * <https://schema.datacite.org/meta/kernel-4.5/>, inspiration snd.gu.se, använd 4.5 (inte 4.4)
* DataCite firewall limit:
  * 3000 requests in a 5 minute window. requests that come via doi.org Content Negotiation of 1000 requests in a 5
    minute window.

### Python

* <https://github.com/papis/python-doi>
* Python package [Datacite](https://pypi.org/project/datacite/)

### SND Contacts

<olof.olsson@snd.gu.se>
<andre.jernung@gu.se>
