from wtforms import SearchField, SelectField
from flask_wtf import FlaskForm
import wtforms.validators as validators


class LanGamesProposalSearchForm(FlaskForm):
    terms = SearchField(
        'Nom du jeu',
        [validators.DataRequired(), validators.Length(min=2)],
        render_kw={
            'placeholder': 'Tape le nom d\'un jeu...',
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
