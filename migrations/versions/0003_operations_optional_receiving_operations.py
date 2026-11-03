"""optional receiving operations"""
from alembic import op
import sqlalchemy as sa

revision = '0003_operations'
down_revision = '0002_receiving'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('receiving_resources',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('site_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('kind', sa.String(), nullable=False),
    sa.Column('mutation', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['site_id'], ['receiving_sites.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('site_id', 'name', name='uq_receiving_resource_name')
    )
    with op.batch_alter_table('receiving_resources', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_receiving_resources_site_id'), ['site_id'], unique=False)

    op.create_table('receiving_notifications',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('site_id', sa.String(), nullable=False),
    sa.Column('actor_id', sa.String(), nullable=False),
    sa.Column('event_key', sa.String(), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['receiving_actors.id'], ),
    sa.ForeignKeyConstraint(['site_id'], ['receiving_sites.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('actor_id', 'event_key', name='uq_receiving_notification')
    )
    with op.batch_alter_table('receiving_notifications', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_receiving_notifications_actor_id'), ['actor_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_receiving_notifications_site_id'), ['site_id'], unique=False)

    op.create_table('receiving_slots',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('site_id', sa.String(), nullable=False),
    sa.Column('resource_id', sa.String(), nullable=False),
    sa.Column('plan_id', sa.String(), nullable=True),
    sa.Column('start_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('end_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('actor_id', sa.String(), nullable=False),
    sa.Column('request_digest', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['receiving_actors.id'], ),
    sa.ForeignKeyConstraint(['plan_id'], ['receiving_plans.id'], ),
    sa.ForeignKeyConstraint(['resource_id'], ['receiving_resources.id'], ),
    sa.ForeignKeyConstraint(['site_id'], ['receiving_sites.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('receiving_slots', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_receiving_slots_resource_id'), ['resource_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_receiving_slots_site_id'), ['site_id'], unique=False)



def downgrade():
    raise RuntimeError("Receiving evidence downgrade is destructive; restore a verified backup into a separate target")
