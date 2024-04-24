#!/usr/bin/env bash

set -e # Makes any subsequent failing commands to exit the script immediately

echo "Loading env variables from dotenv files"

if [ -f .env ]; then
    export $(cat .env | xargs)
fi

if [ -f .flaskenv ]; then
    export $(cat .flaskenv | xargs)
fi

# Activate Python env
. venv/bin/activate

echo "Pulling latest code version"

git pull

echo "Restarting site"

status=$(curl --basic --user "${ALWAYSDATA_API_TOKEN} account=${ALWAYSDATA_ACCOUNT_NAME}:" --data '' --request POST --silent --output /dev/null --write-out '%{http_code}' "https://api.alwaysdata.com/v1/site/${ALWAYSDATA_SITE_ID}/restart/")

if [ "$status" = 204 ];
then
    echo "Success"
else
    echo "Error occured while restarting site"
fi