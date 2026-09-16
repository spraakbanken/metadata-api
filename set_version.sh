#!/usr/bin/env bash

# Set current version number in README.md and openapi_info.yaml

# Find version number in pyproject.toml
APP_VERSION=$(grep -o -P '(?<=^version = ")(.*)(?=")' pyproject.toml) # e.g. 3.1

if [[ -z $APP_VERSION ]]; then
  echo "Couldn't extract version number"; exit 1
fi

MAJOR_VERSION="v$(echo $APP_VERSION | cut -d '.' -f 1)" # e.g. v3

# Fix README.md
perl -p -i -e "s/\/v\d+/\/$MAJOR_VERSION/g" README.md

echo -e "Version in README.md set to: $MAJOR_VERSION\n"
echo "Lines containing version number:"
grep --color=always "/v[0-9]" README.md

# Fix production server in openapi_info.yaml
perl -p -i -e "s/\/v\d+/\/$MAJOR_VERSION/g" metadata_api/openapi_info.yaml

echo -e "\nVersion in openapi_info.yaml set to: $MAJOR_VERSION\n"
echo "Lines containing version number:"
grep --color=always "/v[0-9]" metadata_api/openapi_info.yaml
