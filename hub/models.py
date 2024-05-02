from __future__ import annotations
from sqlalchemy.orm import mapped_column, relationship
from sqlalchemy_utils.types import TSVectorType
from enum import Enum as PythonEnum
from datetime import UTC, datetime
from flask_login import UserMixin
from typing import Optional
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

    def my_vote(self, proposal: LanGameProposal) -> Optional[LanGameProposalVote]:
        return next((vote for vote in proposal.votes if vote.user_id == self.id), None)

    def __repr__(self) -> str:
        return f'User:{self.id}'


class Game(db.Model):
    __tablename__ = 'games'

    id = mapped_column(sa.BigInteger, primary_key=True, autoincrement=False)

    name = mapped_column(sa.String(255), nullable=False)
    search_vector = sa.Column(TSVectorType('name'))

    proposal = relationship('LanGameProposal', uselist=False, back_populates='game')

    def __repr__(self) -> str:
        return f'Game:{self.id}'


class LanGameProposal(CreatedAtMixin, db.Model):
    __tablename__ = 'lan_game_proposals'

    game_id = mapped_column(sa.BigInteger, sa.ForeignKey('games.id', ondelete='cascade'), primary_key=True, autoincrement=False)
    user_id = mapped_column(sa.BigInteger, sa.ForeignKey('users.id', ondelete='cascade'), nullable=False)

    votes = relationship('LanGameProposalVote', back_populates='proposal')
    game = relationship('Game', uselist=False, back_populates='proposal')
    user = relationship('User', uselist=False)

    def votes_count(self, type_: LanGameProposalVoteType) -> int:
        return len([
            vote for vote in self.votes if vote.type == type_
        ])

    def votes_percentage(self, type_: LanGameProposalVoteType) -> float:
        votes_total = len(self.votes)

        if votes_total == 0:
            return 0.0

        return self.votes_count(type_) / votes_total

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
    type = sa.Column(sa.Enum(LanGameProposalVoteType), nullable=False)

    proposal = relationship('LanGameProposal', uselist=False, back_populates='votes')

    user = relationship('User', uselist=False)

    def __repr__(self) -> str:
        return f'LanGameProposalVote:{self.game_proposal_game_id}+{self.user_id}'


db.configure_mappers()
