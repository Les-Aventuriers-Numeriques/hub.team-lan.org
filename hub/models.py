from sqlalchemy.orm import mapped_column, relationship
from sqlalchemy_utils.types import TSVectorType
from datetime import UTC, datetime
from flask_login import UserMixin
from app import db


class CreatedAtMixin:
    created_at = mapped_column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))


class UpdatedAtMixin:
    updated_at = mapped_column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class User(CreatedAtMixin, UpdatedAtMixin, UserMixin, db.Model):
    __tablename__ = 'users'

    id = mapped_column(db.BigInteger, primary_key=True, autoincrement=False)

    display_name = mapped_column(db.String(255), nullable=False)
    avatar_url = mapped_column(db.String(255))
    is_admin = mapped_column(db.Boolean, nullable=False, default=False)

    game_proposals = relationship('GameProposal', back_populates='user')
    game_proposal_votes = relationship('GameProposalVote', back_populates='user')

    def __repr__(self) -> str:
        return f'User:{self.id}'


class Game(db.Model):
    __tablename__ = 'games'

    id = mapped_column(db.BigInteger, primary_key=True, autoincrement=False)

    name = mapped_column(db.String(255), nullable=False)

    # search_vector = db.Column(TSVectorType('name'))

    proposals = relationship('GameProposal', back_populates='game')
    # votes = relationship('GameProposalVote', back_populates='game')

    def __repr__(self) -> str:
        return f'Game:{self.id}'


class GameProposal(CreatedAtMixin, db.Model):
    __tablename__ = 'game_proposals'

    game_id = mapped_column(db.BigInteger, db.ForeignKey('games.id', ondelete='cascade'), primary_key=True, autoincrement=False)
    user_id = mapped_column(db.BigInteger, db.ForeignKey('users.id', ondelete='cascade'), nullable=False)

    votes = relationship('GameProposalVote', back_populates='proposal')

    game = relationship('Game', back_populates='proposals')
    user = relationship('User', back_populates='game_proposals')

    def __repr__(self) -> str:
        return f'GameProposal:{self.game_id}'


class GameProposalVote(CreatedAtMixin, db.Model):
    __tablename__ = 'game_proposal_votes'

    game_proposal_game_id = mapped_column(db.BigInteger, db.ForeignKey('game_proposals.game_id', ondelete='cascade'), primary_key=True, autoincrement=False)
    user_id = mapped_column(db.BigInteger, db.ForeignKey('users.id', ondelete='cascade'), primary_key=True, autoincrement=False)

    proposal = relationship('GameProposal', back_populates='votes')

    # game = relationship('Game', back_populates='votes', foreign_keys='GameProposalVote.game_proposal_game_id')
    user = relationship('User', back_populates='game_proposal_votes')

    def __repr__(self) -> str:
        return f'GameProposalVote:{self.game_proposal_game_id}+{self.user_id}'


db.configure_mappers()
