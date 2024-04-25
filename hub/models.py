from sqlalchemy_utils.types import TSVectorType
from sqlalchemy.orm import mapped_column
from datetime import UTC, datetime
from flask_login import UserMixin
from app import db


class TimestampedMixin:
    created_at = mapped_column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_at = mapped_column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class User(TimestampedMixin, UserMixin, db.Model):
    __tablename__ = 'users'

    discord_id = mapped_column(db.BigInteger, primary_key=True, autoincrement=False)

    display_name = mapped_column(db.String(255), nullable=False)
    avatar_url = mapped_column(db.String(255))

    def get_id(self) -> int:
        return self.discord_id

    def __repr__(self) -> str:
        return f'User:{self.discord_id}'


class Game(db.Model):
    __tablename__ = 'games'

    steam_appid = mapped_column(db.BigInteger, primary_key=True, autoincrement=False)
    name = mapped_column(db.String(255), nullable=False)

    search_vector = db.Column(TSVectorType('name'))

    def __repr__(self) -> str:
        return f'Game:{self.steam_appid}'


db.configure_mappers()
