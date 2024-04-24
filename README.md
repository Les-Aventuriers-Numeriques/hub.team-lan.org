# Les Aventuriers Numériques / Hub

L'[intranet](https://hub.team-lan.org/) utilisé pour les [LAN parties](https://team-lan.org/lan) organisées par la team
multigaming Les Aventuriers Numériques.

Il s'agit d'une application web propulsée par [Flask](https://flask.palletsprojects.com/en/3.0.x/).

## Prérequis

  - Python >= 3.10 (développé sous 3.12)
  - Un navigateur web moderne
  - (Production **et** développement) Un serveur PostgreSQL
  - (Production) Un serveur web compatible WSGI

## Installation

  1. Clonez ce dépôt quelque part 
  2. Copiez `.env.example` vers `.env` et remplissez les variables requises / souhaitées
  3. `pip install -r requirements-dev.txt`
  4. `flask db upgrade`