from wtforms import SearchField
from flask_wtf import FlaskForm
import wtforms.validators as validators


class LanGamesProposeSearchForm(FlaskForm):
    search_terms = SearchField('Nom du jeu', [validators.DataRequired(), validators.Length(min=2)])
