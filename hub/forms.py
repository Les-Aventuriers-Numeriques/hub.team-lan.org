from wtforms import SearchField, SelectField, StringField, URLField, IntegerField, DecimalField, TextAreaField
from hub.models import LanAccommodationProposal
from flask_wtf import FlaskForm
import wtforms.validators as validators


class LanGamesProposalSearchForm(FlaskForm):
    terms = SearchField(
        'Nom du jeu',
        [validators.DataRequired(), validators.Length(min=2)],
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
        [validators.DataRequired(), validators.Length(max=255)],
        render_kw={
            'placeholder': 'Par exemple "Maison avec grande pièce de vie, billard, piscine, baby-foot, tireuse à bière"',
        }
    )

    photo_url = URLField(
        'Photo représentative',
        [validators.DataRequired(), validators.Length(max=500)],
        render_kw={
            'placeholder': 'URL vers une image aux dimensions respectables',
        }
    )

    listing_url = URLField(
        'Annonce',
        [validators.DataRequired(), validators.Length(max=500)],
        render_kw={
            'placeholder': 'URL vers l\'annonce (Booking, Airbnb, etc)',
        }
    )

    location_name = StringField(
        'Localisation (nom)',
        [validators.DataRequired(), validators.Length(max=255)],
        render_kw={
            'placeholder': 'Par exemple "Montcuq (vers Montauban)"',
        }
    )

    location_url = URLField(
        'Localisation (URL)',
        [validators.DataRequired(), validators.Length(max=500)],
        render_kw={
            'placeholder': 'URL vers Google Maps, Bing Maps, etc',
        }
    )

    bedrooms = IntegerField(
        'Nombre de chambres',
        [validators.DataRequired(), validators.NumberRange(min=1)]
    )

    single_beds = IntegerField(
        'Nombre de lits simples',
        [validators.DataRequired(), validators.NumberRange(min=0)]
    )

    twin_beds = IntegerField(
        'Nombre de lits doubles',
        [validators.DataRequired(), validators.NumberRange(min=0)]
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
            ('', 'Sait pas'),
            ('yes', 'Oui'),
            ('no', 'Non'),
        ]
    )

    has_private_parking = SelectField(
        'Parking privé ?',
        [validators.Optional()],
        choices=[
            ('', 'Sait pas'),
            ('yes', 'Oui'),
            ('no', 'Non'),
        ]
    )

    total_price = DecimalField(
        'Prix total',
        [validators.DataRequired(), validators.NumberRange(min=1.0, max=9999.99)],
        places=2
    )

    notes = TextAreaField(
        'Notes',
        [validators.Optional()],
        render_kw={
            'placeholder': 'Par exemple "Le canapé est assez grand pour Pepsy et sa fratrie"',
        }
    )

    def populate_proposal(self, proposal: LanAccommodationProposal):
        proposal.title = self.title.data
        proposal.photo_url = self.photo_url.data
        proposal.listing_url = self.listing_url.data
        proposal.location_name = self.location_name.data
        proposal.location_url = self.location_url.data
        proposal.bedrooms = self.bedrooms.data
        proposal.single_beds = self.single_beds.data
        proposal.twin_beds = self.twin_beds.data
        proposal.large_tables = self.large_tables.data
        proposal.has_fiber = True if self.has_fiber.data == 'yes' else False if self.has_fiber.data == 'no' else None
        proposal.has_private_parking = True if self.has_private_parking.data == 'yes' else False if self.has_private_parking.data == 'no' else None
        proposal.total_price = self.total_price.data
        proposal.notes = self.notes.data


class LanGamesSettingsForm(FlaskForm):
    lan_games_status = SelectField(
        'Statut de la section',
        [validators.DataRequired()],
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
        [validators.DataRequired()],
        choices=[
            ('disabled', 'Désactivée'),
            ('enabled', 'Activée'),
            ('read_only', 'Lecture seule'),
        ],
        default='disabled',
        description='<strong>Désactivée</strong> : aucun accès, période creuse ; <strong>Activée</strong> : accès normal, période de choix des logements ; <strong>Lecture seule</strong> : consultation uniquement.'
    )
