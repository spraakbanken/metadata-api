#!/usr/bin/env bash

# Set current version number in README.md

# Find version number
APP_VERSION=$(grep -o -P '(?<=__version__ = ")(.*)(?=")' metadata_api/__init__.py) # e.g. 3.0

if [[ -z $APP_VERSION ]]; then
  echo "Couldn't extract version number"; exit 1
fi

MAJOR_VERSION="v$(echo $APP_VERSION | cut -d '.' -f 1)" # e.g. v3

perl -p -i -e "s/\/v\d+/\/$MAJOR_VERSION/g" README.md

echo -e "Version in README.md set to: $MAJOR_VERSION\n"
echo "Lines containing version number:"
grep --color=always "/v[0-9]" README.md
