# À propos du fichier `games.csv`

Ce fichier contient les jeux hors Steam ou mods devant être importés dans la base de données, en plus des jeux importés
depuis la boutique de Steam. Il s'agit d'un simple fichier texte au format CSV. La première ligne est l'en-tête du
fichier, contenant le libellé des colonnes dont voici la description :

  - `name` - Le nom du jeu ou du mod
  - `url` - Une URL vers une page permettant d'obtenir le jeu ou le mod

Un identifiant est attributé automatiquement à chaque jeu ou mod de façon décrémentiel à partir de `-1` pour la première
ligne (càd `-2` pour le 2ème jeu, `-3` pour le 3ème, etc).

> [!CAUTION]
> Une fois un jeu / mod inséré dans ce fichier et une fois le fichier traité, **il n'est plus possible de le changer de
> ligne ni de le supprimer**.

Une image associée à chaque jeu ou mod **doit** également être présente dans le dossier `static/images/games/{identifiant}.png`
où `{identifiant}` correspond à l'identifiant qui sera généré pour le jeu (voir ci-dessus). L'image  **doit** avoir une
dimension de 231x87 pixels et **doit** être au format PNG.

> [!WARNING]
>   - Les URLs vers du contenu illégal ne sont pas autorisées.
>   - Ne pas oublier d'entourer la valeur avec des double-quotes (`"`) si elle contient une virgule (`,`).
>   - Ne pas oublier d'échapper les double-quotes avec une autre double-quote (`""`).