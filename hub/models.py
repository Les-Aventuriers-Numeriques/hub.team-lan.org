from __future__ import annotations
from sqlalchemy.orm import mapped_column, relationship
from typing import Optional, Union, List, Dict, Any
from sqlalchemy_utils.types import TSVectorType
from sqlalchemy.util import memoized_property
from sqlalchemy.dialects import postgresql
from urllib.parse import quote_plus
from datetime import UTC, datetime
from flask_login import UserMixin
from enum import StrEnum
from app import db
import sqlalchemy as sa


class CreatedAtMixin:
    created_at = mapped_column(sa.DateTime, nullable=False, default=lambda: datetime.now(UTC))


class UpdatedAtMixin:
    updated_at = mapped_column(sa.DateTime, nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class VotableMixin:
    user_id = mapped_column(sa.BigInteger, sa.ForeignKey('users.id', ondelete='cascade'), nullable=False)

    def votes_by_type(self, type_: VoteType) -> List[Union[LanGameProposalVote, LanAccommodationProposalVote]]:
        return [
            vote for vote in self.votes if vote.type == type_
        ]

    def votes_count(self, type_: VoteType) -> int:
        return len(self.votes_by_type(type_))

    def votes_percentage(self, type_: VoteType) -> float:
        votes_total = len(self.votes)

        if votes_total == 0:
            return 0.0

        return self.votes_count(type_) / votes_total

    @memoized_property
    def score(self) -> int:
        score = 0

        for vote in self.votes:
            if vote.type == VoteType.YES:
                score += 2
            elif vote.type == VoteType.NEUTRAL:
                score += 1
            elif vote.type == VoteType.NO:
                score -= 1

        return score


# ATTENTION : Ne jamais modifier cette liste. Il est possible d'ajouter des éléments, à la fin de la liste uniquement.
class VoteType(StrEnum):
    YES = 'YES'
    NEUTRAL = 'NEUTRAL'
    NO = 'NO'

    @classmethod
    def cslist(cls) -> str:
        return ','.join([
            e.value for e in cls
        ])


# ATTENTION : Ne jamais modifier cette liste. Il est possible d'ajouter des éléments, à la fin de la liste uniquement.
class UserKitchenPreference(StrEnum):
    COOK = 'cook'
    ASSISTANT = 'assistant'
    ANY = 'any'

    def label(self) -> str:
        return {
            UserKitchenPreference.COOK: 'Cuisinier',
            UserKitchenPreference.ASSISTANT: 'Commis',
            UserKitchenPreference.ANY: 'Peu importe',
        }.get(self, '')


# ATTENTION : Ne jamais modifier cette liste. Il est possible d'ajouter des éléments, à la fin de la liste uniquement.
class UserWaterPreference(StrEnum):
    STILL = 'still'
    SPARKLING = 'sparkling'
    ANY = 'any'

    def label(self) -> str:
        return {
            UserWaterPreference.STILL: 'Plate',
            UserWaterPreference.SPARKLING: 'Gazeuse',
            UserWaterPreference.ANY: 'Peu importe',
        }.get(self, '')


# ATTENTION : Ne jamais modifier cette liste. Il est possible d'ajouter des éléments, à la fin de la liste uniquement.
class UserHotDrinksPreference(StrEnum):
    COFFEE = 'coffee'
    TEA = 'tea'
    HOT_CHOCOLATE = 'hot-chocolate'
    ANY = 'any'
    NONE = 'none'

    def label(self) -> str:
        return {
            UserHotDrinksPreference.COFFEE: 'Café',
            UserHotDrinksPreference.TEA: 'Thé',
            UserHotDrinksPreference.HOT_CHOCOLATE: 'Chocolat chaud',
            UserHotDrinksPreference.ANY: 'Peu importe',
            UserHotDrinksPreference.NONE: 'Rien',
        }.get(self, '')


# ATTENTION : Ne jamais modifier cette liste. Il est possible d'ajouter des éléments, à la fin de la liste uniquement.
class UserBreakfastPreference(StrEnum):
    SWEET = 'sweet'
    SALTY = 'salty'
    ANY = 'any'

    def label(self) -> str:
        return {
            UserBreakfastPreference.SWEET: 'Sucré',
            UserBreakfastPreference.SALTY: 'Salé',
            UserBreakfastPreference.ANY: 'Peu importe',
        }.get(self, '')


# ATTENTION : Ne jamais modifier cette liste. Il est possible d'ajouter des éléments, à la fin de la liste uniquement.
class UserBreadsPreference(StrEnum):
    WHITE = 'white'
    WHOLE_GRAIN = 'whole-grain'
    ANY = 'any'

    def label(self) -> str:
        return {
            UserBreadsPreference.WHITE: 'Blanc',
            UserBreadsPreference.WHOLE_GRAIN: 'Complet',
            UserBreadsPreference.ANY: 'Peu importe',
        }.get(self, '')


# ATTENTION : Ne jamais modifier cette liste. Il est possible d'ajouter des éléments, à la fin de la liste uniquement.
class UserAlcoholPreference(StrEnum):
    WINE = 'wine'
    BEER = 'beer'
    ANY = 'any'
    NONE = 'none'

    def label(self) -> str:
        return {
            UserAlcoholPreference.WINE: 'Vin',
            UserAlcoholPreference.BEER: 'Bière',
            UserAlcoholPreference.ANY: 'Peu importe',
            UserAlcoholPreference.NONE: 'Rien',
        }.get(self, '')


# ATTENTION : Ne jamais modifier cette liste. Il est possible d'ajouter des éléments, à la fin de la liste uniquement.
class UserChickenPreference(StrEnum):
    THIGHS = 'thighs'
    BREAST = 'breast'
    ANY = 'any'
    NONE = 'none'

    def label(self) -> str:
        return {
            UserChickenPreference.THIGHS: 'Cuisses',
            UserChickenPreference.BREAST: 'Blanc',
            UserChickenPreference.ANY: 'Peu importe',
            UserChickenPreference.NONE: 'Rien',
        }.get(self, '')


# ATTENTION : Ne jamais modifier cette liste. Il est possible d'ajouter des éléments, à la fin de la liste uniquement.
class UserDrySausagePreference(StrEnum):
    REGULAR = 'regular'
    CHORIZO = 'chorizo'
    ANY = 'any'
    NONE = 'none'

    def label(self) -> str:
        return {
            UserDrySausagePreference.REGULAR: 'Normal',
            UserDrySausagePreference.CHORIZO: 'Chorizo',
            UserDrySausagePreference.ANY: 'Peu importe',
            UserDrySausagePreference.NONE: 'Rien',
        }.get(self, '')


# ATTENTION : Ne jamais modifier cette liste. Il est possible d'ajouter des éléments, à la fin de la liste uniquement.
class UserPatePreference(StrEnum):
    REGULAR = 'regular'
    RILLETTES = 'rillettes'
    ANY = 'any'
    NONE = 'none'

    def label(self) -> str:
        return {
            UserPatePreference.REGULAR: 'Normal',
            UserPatePreference.RILLETTES: 'Rillettes',
            UserPatePreference.ANY: 'Peu importe',
            UserPatePreference.NONE: 'Rien',
        }.get(self, '')


class User(CreatedAtMixin, UpdatedAtMixin, UserMixin, db.Model):
    __tablename__ = 'users'

    id = mapped_column(sa.BigInteger, primary_key=True, autoincrement=False)

    display_name = mapped_column(sa.String(255), nullable=False)
    avatar_url = mapped_column(sa.String(500))
    is_member = mapped_column(sa.Boolean, nullable=False, default=False, server_default=sa.text('false'))
    is_lan_participant = mapped_column(sa.Boolean, nullable=False, default=False, server_default=sa.text('false'))
    is_lan_organizer = mapped_column(sa.Boolean, nullable=False, default=False, server_default=sa.text('false'))
    is_admin = mapped_column(sa.Boolean, nullable=False, default=False, server_default=sa.text('false'))
    must_relogin = mapped_column(sa.Boolean, nullable=False, default=False, server_default=sa.text('false'))

    allergies = mapped_column(sa.String(255))
    special_diet = mapped_column(sa.String(255))
    is_vegetarian = mapped_column(sa.Boolean)
    kitchen = mapped_column(sa.Enum(UserKitchenPreference))
    water = mapped_column(sa.Enum(UserWaterPreference))
    hot_drinks = mapped_column(sa.Enum(UserHotDrinksPreference))
    breakfast = mapped_column(sa.Enum(UserBreakfastPreference))
    breads = mapped_column(sa.Enum(UserBreadsPreference))
    cheeses = mapped_column(sa.String(255))
    spicy_dishes = mapped_column(sa.Boolean)
    alcohol = mapped_column(sa.Enum(UserAlcoholPreference))
    meat = mapped_column(sa.String(255))
    chicken = mapped_column(sa.Enum(UserChickenPreference))
    dry_sausage = mapped_column(sa.Enum(UserDrySausagePreference))
    thai_cuisine = mapped_column(sa.Boolean)
    pate = mapped_column(sa.Enum(UserPatePreference))
    other_preferences = mapped_column(sa.String(255))

    game_proposals = relationship('LanGameProposal', back_populates='user')
    accommodation_proposals = relationship('LanAccommodationProposal', back_populates='user')

    game_votes = relationship('LanGameProposalVote', back_populates='user')
    accommodation_votes = relationship('LanAccommodationProposalVote', back_populates='user')

    def my_vote(self, proposal: Union[LanGameProposal, LanAccommodationProposal]) -> Optional[Union[LanGameProposal, LanAccommodationProposal]]:
        return next((vote for vote in proposal.votes if vote.user_id == self.id), None)

    def __repr__(self) -> str:
        return f'User:{self.id}'


class Game(db.Model):
    __tablename__ = 'games'

    id = mapped_column(sa.BigInteger, primary_key=True, autoincrement=False)

    name = mapped_column(sa.String(255), nullable=False)
    search_vector = mapped_column(TSVectorType('name', regconfig='english_nostop'))
    url = mapped_column(sa.String(255))
    image_id = mapped_column(sa.String(25))
    single_owner_enough = mapped_column(sa.Boolean, nullable=False, default=False, server_default=sa.text('false'))

    proposal = relationship('LanGameProposal', uselist=False, back_populates='game')

    @property
    def image_url(self) -> str:
        if not self.image_id:
            return f'https://placehold.co/264x374/1b212c/8891a4.png?text={quote_plus(self.name)}'

        return f'https://images.igdb.com/igdb/image/upload/t_cover_big/{self.image_id}.png'

    @property
    def image_url_small(self) -> str:
        if not self.image_id:
            return f'https://placehold.co/90x128/1b212c/8891a4.png?text={quote_plus(self.name)}'

        return f'https://images.igdb.com/igdb/image/upload/t_cover_small/{self.image_id}.png'

    def __repr__(self) -> str:
        return f'Game:{self.id}'


class LanGameProposal(VotableMixin, CreatedAtMixin, db.Model):
    __tablename__ = 'lan_game_proposals'

    game_id = mapped_column(sa.BigInteger, sa.ForeignKey('games.id', ondelete='cascade'), primary_key=True, autoincrement=False)
    message_id = mapped_column(sa.BigInteger)

    votes = relationship('LanGameProposalVote', back_populates='proposal')
    game = relationship('Game', uselist=False, back_populates='proposal')
    user = relationship('User', uselist=False, back_populates='game_proposals')

    is_essential: bool = False

    def __repr__(self) -> str:
        return f'LanGameProposal:{self.game_id}'


class LanGameProposalVote(CreatedAtMixin, UpdatedAtMixin, db.Model):
    __tablename__ = 'lan_game_proposal_votes'

    game_proposal_game_id = mapped_column(sa.BigInteger, sa.ForeignKey('lan_game_proposals.game_id', ondelete='cascade'), primary_key=True, autoincrement=False)
    user_id = mapped_column(sa.BigInteger, sa.ForeignKey('users.id', ondelete='cascade'), primary_key=True, autoincrement=False)
    type = mapped_column(sa.Enum(VoteType), nullable=False)

    proposal = relationship('LanGameProposal', uselist=False, back_populates='votes')
    user = relationship('User', uselist=False, back_populates='game_votes')

    @classmethod
    def vote(cls, user: User, game_id: int, vote_type: VoteType):
        query = postgresql.insert(cls).values(
            game_proposal_game_id=game_id,
            user_id=user.id,
            type=vote_type
        )

        db.session.execute(query.on_conflict_do_update(
            index_elements=[
                cls.game_proposal_game_id,
                cls.user_id,
            ],
            set_={
                cls.type: query.excluded.type,
                cls.updated_at: datetime.now(UTC),
            }
        ))

    def __repr__(self) -> str:
        return f'LanGameProposalVote:{self.game_proposal_game_id}+{self.user_id}'


class LanAccommodationProposal(VotableMixin, UpdatedAtMixin, CreatedAtMixin, db.Model):
    __tablename__ = 'lan_accommodation_proposals'

    id = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)

    title = mapped_column(sa.String(255), nullable=False)
    photo_url = mapped_column(sa.String(500), nullable=False)
    listing_url = mapped_column(sa.String(500), nullable=False)
    location_name = mapped_column(sa.String(255), nullable=False)
    location_url = mapped_column(sa.String(500), nullable=False)
    bedrooms = mapped_column(sa.SmallInteger, nullable=False)
    single_beds = mapped_column(sa.SmallInteger, nullable=False)
    twin_beds = mapped_column(sa.SmallInteger, nullable=False)
    large_tables = mapped_column(sa.SmallInteger)
    has_fiber = mapped_column(sa.Boolean)
    has_private_parking = mapped_column(sa.Boolean)
    total_price = mapped_column(sa.Numeric(6, 2), nullable=False)
    notes = mapped_column(sa.Text)
    message_id = mapped_column(sa.BigInteger)

    votes = relationship('LanAccommodationProposalVote', back_populates='proposal')
    user = relationship('User', uselist=False, back_populates='accommodation_proposals')

    @property
    def max_guests(self) -> int:
        return self.single_beds + self.twin_beds * 2

    def __repr__(self) -> str:
        return f'LanAccommodationProposal:{self.id}'


class LanAccommodationProposalVote(CreatedAtMixin, UpdatedAtMixin, db.Model):
    __tablename__ = 'lan_accommodation_proposal_votes'

    accommodation_proposal_id = mapped_column(sa.BigInteger, sa.ForeignKey('lan_accommodation_proposals.id', ondelete='cascade'), primary_key=True, autoincrement=False)
    user_id = mapped_column(sa.BigInteger, sa.ForeignKey('users.id', ondelete='cascade'), primary_key=True, autoincrement=False)
    type = mapped_column(sa.Enum(VoteType, name='accommodationvotetype'), nullable=False)

    proposal = relationship('LanAccommodationProposal', uselist=False, back_populates='votes')
    user = relationship('User', uselist=False, back_populates='accommodation_votes')

    @classmethod
    def vote(cls, user: User, proposal_id: int, vote_type: VoteType) -> None:
        query = postgresql.insert(cls).values(
            accommodation_proposal_id=proposal_id,
            user_id=user.id,
            type=vote_type
        )

        db.session.execute(query.on_conflict_do_update(
            index_elements=[
                cls.accommodation_proposal_id,
                cls.user_id,
            ],
            set_={
                cls.type: query.excluded.type,
                cls.updated_at: datetime.now(UTC),
            }
        ))

    def __repr__(self) -> str:
        return f'LanAccommodationProposalVote:{self.accommodation_proposal_id}+{self.user_id}'


class Setting(UpdatedAtMixin, db.Model):
    __tablename__ = 'settings'

    name = mapped_column(sa.String(255), primary_key=True, autoincrement=False)
    value = mapped_column(sa.PickleType)

    @classmethod
    def get(cls, name: Union[str, List[str]], default: Any = None) -> Union[str, Dict[str, Any], Any]:
        if isinstance(name, str):
            return db.session.execute(
                sa.select(cls.value).where(cls.name == name)
            ).scalar() or default
        elif isinstance(name, list):
            result = {
                n: v for n, v in db.session.execute(
                    sa.select(cls.name, cls.value).where(cls.name.in_(name))
                ).all()
            }

            return {
                n: result.get(n, default) for n in name
            }

    @classmethod
    def set(cls, name: Union[str, Dict[str, Any]], value: Optional[Any] = None) -> None:
        query = postgresql.insert(cls)

        if isinstance(name, str):
            query = query.values(
                name=name,
                value=value
            )
        elif isinstance(name, dict):
            query = query.values([
                {
                    'name': n,
                    'value': v
                } for n, v in name.items()
            ])

        db.session.execute(query.on_conflict_do_update(
            index_elements=[
                cls.name,
            ],
            set_={
                cls.value: query.excluded.value,
                cls.updated_at: datetime.now(UTC),
            }
        ))

    @classmethod
    def delete(cls, name: Union[str, List[str]]) -> None:
        query = sa.delete(cls)

        if isinstance(name, str):
            query = query.where(cls.name == name)
        elif isinstance(name, list):
            query = query.where(cls.name.in_(name))

        db.session.execute(query)


db.configure_mappers()
