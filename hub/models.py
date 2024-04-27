from sqlalchemy.orm import mapped_column, relationship
from sqlalchemy_utils.types import TSVectorType
from datetime import UTC, datetime
from sqlalchemy import ForeignKey
from flask_login import UserMixin
from app import db


class CreatedAtMixin:
    created_at = mapped_column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))


class UpdatedAtMixin:
    updated_at = mapped_column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class User(CreatedAtMixin, UpdatedAtMixin, UserMixin, db.Model):
    __tablename__ = 'users'

    discord_id = mapped_column(db.BigInteger, primary_key=True, autoincrement=False)

    display_name = mapped_column(db.String(255), nullable=False)
    avatar_url = mapped_column(db.String(255))
    is_admin = mapped_column(db.Boolean, nullable=False, default=False)

    # game_proposals = relationship('GameProposal', back_populates='proposed_by')
    # game_proposal_votes = relationship('GameProposalVote', back_populates='voted_by')

    def get_id(self) -> int:
        return self.discord_id

    def __repr__(self) -> str:
        return f'User:{self.discord_id}'


class Game(db.Model):
    __tablename__ = 'games'

    steam_id = mapped_column(db.BigInteger, primary_key=True, autoincrement=False)

    name = mapped_column(db.String(255), nullable=False)

    # search_vector = db.Column(TSVectorType('name'))

    def __repr__(self) -> str:
        return f'Game:{self.steam_id}'


class GameProposal(CreatedAtMixin, db.Model):
    __tablename__ = 'game_proposals'

    discord_id = mapped_column(db.BigInteger, primary_key=True, autoincrement=False)
    steam_id = mapped_column(db.BigInteger, primary_key=True, autoincrement=False)

    # game = relationship('Game')
    # proposed_by = relationship('User', back_populates='game_proposals')

    def __repr__(self) -> str:
        return f'GameProposal:{self.discord_id}+{self.steam_id}'


class GameProposalVote(CreatedAtMixin, db.Model):
    __tablename__ = 'game_proposal_votes'

    discord_id = mapped_column(db.BigInteger, primary_key=True, autoincrement=False)
    steam_id = mapped_column(db.BigInteger, primary_key=True, autoincrement=False)

    # TODO Contrainte de clef étrangère composite sur discord_id+steam_id vers game_proposals.discord_id+game_proposals.steam_id

    # voted_by = relationship('User', back_populates='game_proposal_votes')

    def __repr__(self) -> str:
        return f'GameProposalVote:{self.discord_id}+{self.steam_id}'


db.configure_mappers()
