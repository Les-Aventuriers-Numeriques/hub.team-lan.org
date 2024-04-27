# Les Aventuriers Numériques / Hub

L'[intranet](https://hub.team-lan.org/) utilisé par la team multigaming [Les Aventuriers Numériques](https://team-lan.org/).

Il s'agit d'une application web propulsée par [Flask](https://flask.palletsprojects.com/en/3.0.x/).

## Prérequis

  - Python >= 3.10 (développé sous 3.12)
  - Un navigateur web moderne
  - (Production **et** développement) Un serveur PostgreSQL
  - (Production) Un serveur web compatible WSGI

## Installation

  1. Clonez ce dépôt quelque part 
  2. Copiez `.env.example` vers `.env` et remplissez les variables requises / souhaitées. Elles peuvent également être définies dans l'environnement
  3. `pip install -r requirements-dev.txt`. `requirements-prod.txt` est à utiliser dans un environnement de production
  4. `flask db upgrade`

## Configuration

> [!NOTE]
> TODO