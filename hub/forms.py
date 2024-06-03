from wtforms import SearchField, SelectField, TextAreaField
from sqlalchemy import func as sa_func
from hub.models import LanGameProposal
from flask_wtf import FlaskForm
from app import db
import wtforms.validators as validators
import sqlalchemy as sa


class LanGamesProposalSearchForm(FlaskForm):
    terms = SearchField(
        'Nom du jeu',
        [validators.DataRequired(),
         validators.Length(min=2)],
        render_kw={
            'placeholder': 'Tape le nom d\'un jeu...',
        }
    )


class LanGamesSettings(FlaskForm):
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

    lan_games_excluded = TextAreaField(
        'Jeux exclus',
        description='Identifiants de jeux Steam séparés par des virgules qui ne seront pas disponibles à la proposition.'
    )

    def validate_lan_games_excluded(self, field):
        if field.data:
            try:
                data = [
                    int(value.strip()) for value in field.data.split(',')
                ]
            except ValueError:
                raise validators.ValidationError('Format invalide : lis donc ce qu\'il y a écrit ci-dessous.')

            count = db.session.execute(
                sa.select(sa_func.count('*')).select_from(LanGameProposal)
                .where(LanGameProposal.game_id.in_(data))
            ).scalar()

            if count > 0:
                raise validators.ValidationError('Impossible d\'exclure un jeu déjà proposé (il faut le supprimer des propositions avant).')

            field.data = data
