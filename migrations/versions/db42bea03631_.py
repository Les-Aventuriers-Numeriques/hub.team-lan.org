"""empty message

Revision ID: db42bea03631
Revises: 
Create Date: 2024-04-28 14:34:33.336745

"""
from sqlalchemy_searchable import sync_trigger, drop_trigger
from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils


# revision identifiers, used by Alembic.
revision = 'db42bea03631'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('games',
    sa.Column('id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('search_vector', sqlalchemy_utils.types.ts_vector.TSVectorType(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('games', schema=None) as batch_op:
        batch_op.create_index('ix_games_search_vector', ['search_vector'], unique=False, postgresql_using='gin')

    sync_trigger(op.get_bind(), 'games', 'search_vector', ['name'])

    op.create_table('users',
    sa.Column('id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('display_name', sa.String(length=255), nullable=False),
    sa.Column('avatar_url', sa.String(length=255), nullable=True),
    sa.Column('is_lan_participant', sa.Boolean(), nullable=False),
    sa.Column('is_admin', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('lan_game_proposals',
    sa.Column('game_id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['game_id'], ['games.id'], ondelete='cascade'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='cascade'),
    sa.PrimaryKeyConstraint('game_id')
    )
    op.create_table('lan_game_proposal_votes',
    sa.Column('game_proposal_game_id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('user_id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('type', sa.Enum('YES', 'NO', 'NEUTRAL', name='langameproposalvotetype'), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['game_proposal_game_id'], ['lan_game_proposals.game_id'], ondelete='cascade'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='cascade'),
    sa.PrimaryKeyConstraint('game_proposal_game_id', 'user_id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('lan_game_proposal_votes')
    op.drop_table('lan_game_proposals')
    op.drop_table('users')
    with op.batch_alter_table('games', schema=None) as batch_op:
        batch_op.drop_index('ix_games_search_vector', postgresql_using='gin')

    drop_trigger(op.get_bind(), 'games', 'search_vector')

    op.drop_table('games')
    # ### end Alembic commands ###
