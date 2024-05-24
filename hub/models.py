from __future__ import annotations
from sqlalchemy.orm import mapped_column, relationship
from typing import Optional, Union, List, Dict, Any
from sqlalchemy_utils.types import TSVectorType
from sqlalchemy.util import memoized_property
from sqlalchemy.dialects import postgresql
from enum import Enum as PythonEnum
from datetime import UTC, datetime
from flask_login import UserMixin
from app import db
import sqlalchemy as sa


class CreatedAtMixin:
    created_at = mapped_column(sa.DateTime, nullable=False, default=lambda: datetime.now(UTC))


class UpdatedAtMixin:
    updated_at = mapped_column(sa.DateTime, nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class User(CreatedAtMixin, UpdatedAtMixin, UserMixin, db.Model):
    __tablename__ = 'users'

    id = mapped_column(sa.BigInteger, primary_key=True, autoincrement=False)

    display_name = mapped_column(sa.String(255), nullable=False)
    avatar_url = mapped_column(sa.String(255))
    is_member = mapped_column(sa.Boolean, nullable=False, default=False, server_default=sa.text('false'))
    is_lan_participant = mapped_column(sa.Boolean, nullable=False, default=sa.text('false'))
    is_admin = mapped_column(sa.Boolean, nullable=False, default=sa.text('false'))

    proposals = relationship('LanGameProposal', back_populates='user')
    votes = relationship('LanGameProposalVote', back_populates='user')

    def my_vote(self, proposal: LanGameProposal) -> Optional[LanGameProposalVote]:
        return next((vote for vote in proposal.votes if vote.user_id == self.id), None)

    def __repr__(self) -> str:
        return f'User:{self.id}'


class Game(db.Model):
    __tablename__ = 'games'

    id = mapped_column(sa.BigInteger, primary_key=True, autoincrement=False)

    name = mapped_column(sa.String(255), nullable=False)
    search_vector = mapped_column(TSVectorType('name', regconfig='english_nostop'))

    proposal = relationship('LanGameProposal', uselist=False, back_populates='game')

    @property
    def store_url(self) -> str:
        return f'https://store.steampowered.com/app/{self.id}'

    @property
    def image_url(self) -> str:
        return f'https://cdn.cloudflare.steamstatic.com/steam/apps/{self.id}/capsule_231x87.jpg'

    def __repr__(self) -> str:
        return f'Game:{self.id}'


class LanGameProposal(CreatedAtMixin, db.Model):
    __tablename__ = 'lan_game_proposals'

    game_id = mapped_column(sa.BigInteger, sa.ForeignKey('games.id', ondelete='cascade'), primary_key=True, autoincrement=False)
    user_id = mapped_column(sa.BigInteger, sa.ForeignKey('users.id', ondelete='cascade'), nullable=False)

    votes = relationship('LanGameProposalVote', back_populates='proposal')
    game = relationship('Game', uselist=False, back_populates='proposal')
    user = relationship('User', uselist=False, back_populates='proposals')

    def votes_count(self, type_: LanGameProposalVoteType) -> int:
        return len([
            vote for vote in self.votes if vote.type == type_
        ])

    def votes_percentage(self, type_: LanGameProposalVoteType) -> float:
        votes_total = len(self.votes)

        if votes_total == 0:
            return 0.0

        return self.votes_count(type_) / votes_total

    @memoized_property
    def score(self) -> int:
        score = 0

        for vote in self.votes:
            if vote.type == LanGameProposalVoteType.YES:
                score += 2
            elif vote.type == LanGameProposalVoteType.NEUTRAL:
                score += 1
            elif vote.type == LanGameProposalVoteType.NO:
                score -= 1

        return score

    def __repr__(self) -> str:
        return f'LanGameProposal:{self.game_id}'


# ATTENTION : Ne jamais modifier cette liste. Il est possible d'ajouter des éléments, à la fin de la liste uniquement.
class LanGameProposalVoteType(PythonEnum):
    YES = 'YES'
    NEUTRAL = 'NEUTRAL'
    NO = 'NO'

    @classmethod
    def cslist(cls) -> str:
        return ','.join([
            e.value for e in cls
        ])


class LanGameProposalVote(CreatedAtMixin, UpdatedAtMixin, db.Model):
    __tablename__ = 'lan_game_proposal_votes'

    game_proposal_game_id = mapped_column(sa.BigInteger, sa.ForeignKey('lan_game_proposals.game_id', ondelete='cascade'), primary_key=True, autoincrement=False)
    user_id = mapped_column(sa.BigInteger, sa.ForeignKey('users.id', ondelete='cascade'), primary_key=True, autoincrement=False)
    type = mapped_column(sa.Enum(LanGameProposalVoteType), nullable=False)

    proposal = relationship('LanGameProposal', uselist=False, back_populates='votes')
    user = relationship('User', uselist=False, back_populates='votes')

    @classmethod
    def vote(cls, user: User, game_id: int, vote_type: LanGameProposalVoteType):
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
