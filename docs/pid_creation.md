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
* login to DataCite saved in `/home/fksbwww/.netrc` on `k2` (credentials were received from SND and can be found in
  Språkbanken Text's safe)
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
    minute window. But, since 2025Q3 there seems to be an "alternate limit" of 300-500 requests every 5 minutes. To handle this, gen_pids.py pauses for 5 minutes every 300 requests. We also add a User-agent to the header.
    * https://support.datacite.org/reference/introduction#upcoming-changes
    * https://support.datacite.org/docs/api
    * https://support.datacite.org/docs/rate-limit

### Changing id (slug) from A to B

#### Metadata-repository
- rename A.yaml to B.yaml

#### Datacite
- go to datacite.org and "Sign in to Fabrica"
- find metadata record/DOI
- Click "Update DOI (form)"
- Update
	- URL
	- Alternate identifier

#### Check
https://api.datacite.org/dois?client-id=SND.SPRKB&query=identifiers.identifier:<A>%20AND%20identifiers.identifierType:slug&detail=true%22


### Python

* <https://github.com/papis/python-doi>
* Python package [Datacite](https://pypi.org/project/datacite/)

### SND Contacts

<olof.olsson@snd.gu.se>
<andre.jernung@gu.se>
