"""empty message

Revision ID: e7b99e39d141
Revises: 
Create Date: 2024-04-27 21:35:01.067641

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7b99e39d141'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('games',
    sa.Column('steam_id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.PrimaryKeyConstraint('steam_id')
    )
    op.create_table('users',
    sa.Column('discord_id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('display_name', sa.String(length=255), nullable=False),
    sa.Column('avatar_url', sa.String(length=255), nullable=True),
    sa.Column('is_admin', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('discord_id')
    )
    op.create_table('game_proposals',
    sa.Column('discord_id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('steam_id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['discord_id'], ['users.discord_id'], ),
    sa.ForeignKeyConstraint(['steam_id'], ['games.steam_id'], ),
    sa.PrimaryKeyConstraint('discord_id', 'steam_id'),
    sa.UniqueConstraint('discord_id', 'steam_id')
    )
    op.create_table('game_proposal_votes',
    sa.Column('discord_id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('steam_id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['discord_id', 'steam_id'], ['game_proposals.discord_id', 'game_proposals.steam_id'], ),
    sa.PrimaryKeyConstraint('discord_id', 'steam_id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('game_proposal_votes')
    op.drop_table('game_proposals')
    op.drop_table('users')
    op.drop_table('games')
    # ### end Alembic commands ###
