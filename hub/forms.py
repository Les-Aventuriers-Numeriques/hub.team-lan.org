from wtforms import SearchField, SelectField, StringField, URLField, IntegerField, DecimalField, TextAreaField
from flask_wtf import FlaskForm
import wtforms.validators as validators


def coerce_nullable_boolean(value):
    if isinstance(value, str):
        return value == 'True' if value != 'None' else None
    elif isinstance(value, bool):
        return value

    return None


class LanGamesProposalSearchForm(FlaskForm):
    terms = SearchField(
        'Nom du jeu',
        [validators.InputRequired(), validators.Length(min=2)],
        render_kw={
            'placeholder': 'Tapes le nom d\'un jeu...',
        }
    )


class LanGamesVoteFilterForm(FlaskForm):
    filter = SelectField(
        'Filtre',
        choices=[
            ('', 'Afficher uniquement les jeux...'),
            ('voted', '...pour lesquels j\'ai voté'),
            ('not-voted', '...pour lesquels je n\'ai PAS voté'),
            ('all-voted', '...pour lesquels tout le monde a voté'),
            ('not-all-voted', '...pour lesquels tout le monde n\'a PAS voté'),
        ]
    )


class LanAccommodationsVoteFilterForm(FlaskForm):
    filter = SelectField(
        'Filtre',
        choices=[
            ('', 'Afficher uniquement les logements...'),
            ('voted', '...pour lesquels j\'ai voté'),
            ('not-voted', '...pour lesquels je n\'ai PAS voté'),
            ('all-voted', '...pour lesquels tout le monde a voté'),
            ('not-all-voted', '...pour lesquels tout le monde n\'a PAS voté'),
        ]
    )


class LanGamesProposalForm(FlaskForm):
    title = StringField(
        'Titre',
        [validators.InputRequired(), validators.Length(max=255)],
        render_kw={
            'placeholder': 'Par exemple "Maison avec grande pièce de vie, billard, piscine, baby-foot, tireuse à bière"',
        }
    )

    photo_url = URLField(
        'Photo représentative',
        [validators.InputRequired(), validators.Length(max=500)],
        render_kw={
            'placeholder': 'URL vers une image aux dimensions respectables',
        }
    )

    listing_url = URLField(
        'Annonce',
        [validators.InputRequired(), validators.Length(max=500)],
        render_kw={
            'placeholder': 'URL vers l\'annonce (Booking, Airbnb, etc)',
        }
    )

    location_name = StringField(
        'Localisation (nom)',
        [validators.InputRequired(), validators.Length(max=255)],
        render_kw={
            'placeholder': 'Par exemple "Montcuq (vers Montauban)"',
        }
    )

    location_url = URLField(
        'Localisation (URL)',
        [validators.InputRequired(), validators.Length(max=500)],
        render_kw={
            'placeholder': 'URL vers Google Maps, Bing Maps, etc',
        }
    )

    bedrooms = IntegerField(
        'Nombre de chambres',
        [validators.InputRequired(), validators.NumberRange(min=1)]
    )

    single_beds = IntegerField(
        'Nombre de lits simples',
        [validators.InputRequired(), validators.NumberRange(min=0)]
    )

    twin_beds = IntegerField(
        'Nombre de lits doubles',
        [validators.InputRequired(), validators.NumberRange(min=0)]
    )

    large_tables = IntegerField(
        'Nombre de grandes tables',
        [validators.Optional(), validators.NumberRange(min=0)],
        render_kw={
            'placeholder': 'Laisse vide si tu sait pas',
        }
    )

    has_fiber = SelectField(
        'Fibre optique ?',
        [validators.Optional()],
        choices=[
            (None, 'Sait pas'),
            (True, 'Oui'),
            (False, 'Non'),
        ],
        coerce=coerce_nullable_boolean
    )

    has_private_parking = SelectField(
        'Parking privé ?',
        [validators.Optional()],
        choices=[
            (None, 'Sait pas'),
            (True, 'Oui'),
            (False, 'Non'),
        ],
        coerce=coerce_nullable_boolean
    )

    total_price = DecimalField(
        'Prix total',
        [validators.InputRequired(), validators.NumberRange(min=1.0, max=9999.99)],
        places=2
    )

    notes = TextAreaField(
        'Notes',
        [validators.Optional()],
        render_kw={
            'placeholder': 'Par exemple "Le canapé est assez grand pour Pepsy et sa fratrie"',
            'rows': 6
        }
    )


class LanGamesSettingsForm(FlaskForm):
    lan_games_status = SelectField(
        'Statut de la section',
        [validators.InputRequired()],
        choices=[
            ('disabled', 'Désactivée'),
            ('enabled', 'Activée'),
            ('read_only', 'Lecture seule'),
        ],
        default='disabled',
        description='<strong>Désactivée</strong> : aucun accès, période creuse ; <strong>Activée</strong> : accès normal, période de choix des jeux ; <strong>Lecture seule</strong> : consultation uniquement, date de la LAN proche.'
    )


class LanAccommodationsSettingsForm(FlaskForm):
    lan_accommodations_status = SelectField(
        'Statut de la section',
        [validators.InputRequired()],
        choices=[
            ('disabled', 'Désactivée'),
            ('enabled', 'Activée'),
            ('read_only', 'Lecture seule'),
        ],
        default='disabled',
        description='<strong>Désactivée</strong> : aucun accès, période creuse ; <strong>Activée</strong> : accès normal, période de choix des logements ; <strong>Lecture seule</strong> : consultation uniquement.'
    )
