"""receiving evidence"""
from alembic import op
import sqlalchemy as sa

revision = '0002_receiving'
down_revision = '0001_legacy'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('receiving_sites',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('timezone', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('receiving_actors',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('site_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('role', sa.String(), nullable=False),
    sa.Column('key_hash', sa.String(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['site_id'], ['receiving_sites.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('key_hash')
    )
    with op.batch_alter_table('receiving_actors', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_receiving_actors_site_id'), ['site_id'], unique=False)

    op.create_table('receiving_audit',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('site_id', sa.String(), nullable=False),
    sa.Column('actor_id', sa.String(), nullable=False),
    sa.Column('action', sa.String(), nullable=False),
    sa.Column('target', sa.String(), nullable=False),
    sa.Column('details', sa.JSON(), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['site_id'], ['receiving_sites.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('receiving_audit', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_receiving_audit_site_id'), ['site_id'], unique=False)

    op.create_table('receipts',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('site_id', sa.String(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('mutation', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['receiving_actors.id'], ),
    sa.ForeignKeyConstraint(['site_id'], ['receiving_sites.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('receipts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_receipts_site_id'), ['site_id'], unique=False)

    op.create_table('receiving_plans',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('site_id', sa.String(), nullable=False),
    sa.Column('reference', sa.String(), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('created_by', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['receiving_actors.id'], ),
    sa.ForeignKeyConstraint(['site_id'], ['receiving_sites.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('site_id', 'reference', name='uq_receiving_plan_ref')
    )
    with op.batch_alter_table('receiving_plans', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_receiving_plans_site_id'), ['site_id'], unique=False)

    op.create_table('evidence_grants',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('site_id', sa.String(), nullable=False),
    sa.Column('receipt_id', sa.String(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('key_hash', sa.String(), nullable=False),
    sa.Column('recipient', sa.String(), nullable=False),
    sa.Column('purpose', sa.String(), nullable=False),
    sa.Column('consent_reference', sa.String(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked', sa.Boolean(), nullable=False),
    sa.Column('actor_id', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['receiving_actors.id'], ),
    sa.ForeignKeyConstraint(['receipt_id'], ['receipts.id'], ),
    sa.ForeignKeyConstraint(['site_id'], ['receiving_sites.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('key_hash')
    )
    with op.batch_alter_table('evidence_grants', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_evidence_grants_site_id'), ['site_id'], unique=False)

    op.create_table('receipt_revisions',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('receipt_id', sa.String(), nullable=False),
    sa.Column('site_id', sa.String(), nullable=False),
    sa.Column('operation_id', sa.String(), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('digest', sa.String(), nullable=False),
    sa.Column('request_digest', sa.String(), nullable=False),
    sa.Column('actor_id', sa.String(), nullable=False),
    sa.Column('reason', sa.String(), nullable=True),
    sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['receiving_actors.id'], ),
    sa.ForeignKeyConstraint(['receipt_id'], ['receipts.id'], ),
    sa.ForeignKeyConstraint(['site_id'], ['receiving_sites.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('receipt_id', 'number', name='uq_receipt_revision'),
    sa.UniqueConstraint('site_id', 'operation_id', name='uq_receipt_operation')
    )
    with op.batch_alter_table('receipt_revisions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_receipt_revisions_receipt_id'), ['receipt_id'], unique=False)

    op.create_table('receiving_documents',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('site_id', sa.String(), nullable=False),
    sa.Column('plan_id', sa.String(), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('actor_id', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['receiving_actors.id'], ),
    sa.ForeignKeyConstraint(['plan_id'], ['receiving_plans.id'], ),
    sa.ForeignKeyConstraint(['site_id'], ['receiving_sites.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('receiving_documents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_receiving_documents_site_id'), ['site_id'], unique=False)

    op.create_table('receipt_attachments',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('revision_id', sa.String(), nullable=False),
    sa.Column('site_id', sa.String(), nullable=False),
    sa.Column('actor_id', sa.String(), nullable=False),
    sa.Column('digest', sa.String(), nullable=False),
    sa.Column('content_type', sa.String(), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('content', sa.LargeBinary(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['receiving_actors.id'], ),
    sa.ForeignKeyConstraint(['revision_id'], ['receipt_revisions.id'], ),
    sa.ForeignKeyConstraint(['site_id'], ['receiving_sites.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('revision_id', 'digest', name='uq_receipt_attachment')
    )
    with op.batch_alter_table('receipt_attachments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_receipt_attachments_revision_id'), ['revision_id'], unique=False)

    op.create_table('receipt_attestations',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('revision_id', sa.String(), nullable=False),
    sa.Column('site_id', sa.String(), nullable=False),
    sa.Column('actor_id', sa.String(), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('digest', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['receiving_actors.id'], ),
    sa.ForeignKeyConstraint(['revision_id'], ['receipt_revisions.id'], ),
    sa.ForeignKeyConstraint(['site_id'], ['receiving_sites.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('receipt_attestations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_receipt_attestations_revision_id'), ['revision_id'], unique=False)



def downgrade():
    raise RuntimeError("Receiving evidence downgrade is destructive; restore a verified backup into a separate target")
