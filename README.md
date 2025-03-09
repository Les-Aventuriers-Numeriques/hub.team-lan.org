<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://team-lan.org/images/logo_full_dark.png">
    <img src="https://team-lan.org/images/logo_full_light.png">
  </picture>
</p>

# Les Aventuriers Numériques / Hub

L'[intranet](https://hub.team-lan.org/) utilisé par la team multigaming [Les Aventuriers Numériques](https://team-lan.org/).

Il s'agit d'une application web propulsée par [Flask](https://flask.palletsprojects.com/en/3.0.x/). Elle permet :

  - De nous aider à choisir les jeux pour notre prochaine [LAN annuelle](https://team-lan.org/lan)
  - D'envoyer sur notre Discord des messages à propos de nos Chicken Dinner [PUBG](https://www.pubg.com/fr/main)

## Prérequis

  - Python >= 3.10 (développé sous 3.12)
  - Un navigateur web moderne
  - (Production **et** développement) Un serveur PostgreSQL
  - (Production) Un serveur WSGI

## Installation

  1. Clonez ce dépôt quelque part 
  2. Copiez `.env.example` vers `.env` puis remplissez les variables requises / souhaitées (elles peuvent également être définies dans l'environnement)
  3. `pip install -r requirements-dev.txt` (`requirements-prod.txt` est à utiliser dans un environnement de production)
  4. `docker compose up -d`
  5. `flask db upgrade`
  6. `flask update-games` (c'est long)

## Déploiement

Configurer un serveur web / WSGI est hors du périmètre de ce document, toutefois voici les choses à connaître :

  - Le fichier WSGI est `./app.py`
  - Le "callable" WSGI est `app` ou `application`
  - N'oubliez pas de définir `FLASK_DEBUG` à `false` (ou de le supprimer carrément, c'est désactivé par défaut)
  - Mappez le répertoire des fichiers statiques `./static` vers `/static`
  - Mappez les fichiers statiques suivants (ils ne sont pas situés dans le répertoire des fichiers statiques et doivent être trouvés dans la racine de l'URL du site) :
    - `./static/favicon.ico` vers `/favicon.ico` pour qu'une belle icône soit affichée dans votre navigateur
    - `./static/robots.txt` vers `/robots.txt` pour que rien ne soit indexé par les moteurs de recherche