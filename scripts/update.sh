#!/usr/bin/env bash

set -e # Fait en sorte que les prochaines commandes en échec font sortir du script immédiatement

echo "Récupération de la dernière version du code"

git pull

echo "Redémarrage du site"

status=$(curl --basic --user "${ALWAYSDATA_API_TOKEN} account=${ALWAYSDATA_ACCOUNT_NAME}:" --data '' --request POST --silent --output /dev/null --write-out '%{http_code}' "https://api.alwaysdata.com/v1/site/${ALWAYSDATA_SITE_ID}/restart/")

if [ "$status" = 204 ];
then
    echo "Succès"
else
    echo "Une erreur est survenue lors du redémarrage du site"
fi