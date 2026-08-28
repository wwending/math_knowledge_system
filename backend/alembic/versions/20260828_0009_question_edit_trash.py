"""question edit and trash lifecycle (#116)"""
from alembic import op
import sqlalchemy as sa
revision='20260828_0009'
down_revision='20260825_0008'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('questions', sa.Column('answer', sa.Text(), nullable=True))
    op.add_column('questions', sa.Column('analysis', sa.Text(), nullable=True))
    op.add_column('questions', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('questions', sa.Column('purge_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('questions', sa.Column('purged_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('questions', sa.Column('metadata_generation', sa.Integer(), nullable=False, server_default='0'))
    for name,col in [('ix_questions_deleted_at','deleted_at'),('ix_questions_purge_at','purge_at'),('ix_questions_purged_at','purged_at')]: op.create_index(name,'questions',[col])

def downgrade():
    for name in ['ix_questions_purged_at','ix_questions_purge_at','ix_questions_deleted_at']: op.drop_index(name,'questions')
    for col in ['metadata_generation','purged_at','purge_at','deleted_at','analysis','answer']: op.drop_column('questions',col)
