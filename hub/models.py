from sqlalchemy import DateTime, BigInteger, String, Boolean, Column, ForeignKey, Enum
from sqlalchemy.orm import mapped_column, relationship
from sqlalchemy_utils.types import TSVectorType
from enum import Enum as PythonEnum
from datetime import UTC, datetime
from flask_login import UserMixin
from app import db


class CreatedAtMixin:
    created_at = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))


class UpdatedAtMixin:
    updated_at = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class User(CreatedAtMixin, UpdatedAtMixin, UserMixin, db.Model):
    __tablename__ = 'users'

    id = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    display_name = mapped_column(String(255), nullable=False)
    avatar_url = mapped_column(String(255))
    is_lan_participant = mapped_column(Boolean, nullable=False, default=False)
    is_admin = mapped_column(Boolean, nullable=False, default=False)

    @property
    def can_access_lan_section(self) -> bool:
        return self.is_lan_participant or self.is_admin

    def __repr__(self) -> str:
        return f'User:{self.id}'


class Game(db.Model):
    __tablename__ = 'games'

    id = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    name = mapped_column(String(255), nullable=False)
    search_vector = Column(TSVectorType('name'))

    def __repr__(self) -> str:
        return f'Game:{self.id}'


class LanGameProposal(CreatedAtMixin, db.Model):
    __tablename__ = 'lan_game_proposals'

    game_id = mapped_column(BigInteger, ForeignKey('games.id', ondelete='cascade'), primary_key=True, autoincrement=False)
    user_id = mapped_column(BigInteger, ForeignKey('users.id', ondelete='cascade'), nullable=False)

    votes = relationship('LanGameProposalVote', back_populates='proposal')
    game = relationship('Game')
    user = relationship('User')

    def __repr__(self) -> str:
        return f'LanGameProposal:{self.game_id}'


class LanGameProposalVoteType(PythonEnum):
    YES = 'YES'
    NO = 'NO'
    NEUTRAL = 'NEUTRAL'


class LanGameProposalVote(CreatedAtMixin, db.Model):
    __tablename__ = 'lan_game_proposal_votes'

    game_proposal_game_id = mapped_column(BigInteger, ForeignKey('lan_game_proposals.game_id', ondelete='cascade'), primary_key=True, autoincrement=False)
    user_id = mapped_column(BigInteger, ForeignKey('users.id', ondelete='cascade'), primary_key=True, autoincrement=False)
    type = db.Column(Enum(LanGameProposalVoteType), nullable=False)

    proposal = relationship('LanGameProposal', back_populates='votes')

    user = relationship('User')

    def __repr__(self) -> str:
        return f'LanGameProposalVote:{self.game_proposal_game_id}+{self.user_id}'


db.configure_mappers()
