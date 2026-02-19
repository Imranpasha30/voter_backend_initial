"""updated the voter table with form foreign key and form table and family memebers tablle

Revision ID: 49817a59e11e
Revises: e3122eda5795
Create Date: 2026-02-17 16:15:19.262817

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '49817a59e11e'
down_revision: Union[str, Sequence[str], None] = 'e3122eda5795'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    
    # ========================================
    # FAMILY MEMBERS TABLE
    # ========================================
    
    # Add is_voter_verified column with server_default
    op.add_column('family_members', 
        sa.Column('is_voter_verified', sa.Boolean(), 
                  nullable=False, server_default='false'))
    
    # ✅ Handle existing NULL values before making columns NOT NULL
    op.execute("UPDATE family_members SET name = '' WHERE name IS NULL")
    op.alter_column('family_members', 'name',
                    existing_type=sa.VARCHAR(length=255),
                    nullable=False)
    
    op.execute("UPDATE family_members SET age = 0 WHERE age IS NULL")
    op.alter_column('family_members', 'age',
                    existing_type=sa.INTEGER(),
                    nullable=False)
    
    op.execute("UPDATE family_members SET gender = 'Other' WHERE gender IS NULL")
    op.alter_column('family_members', 'gender',
                    existing_type=sa.VARCHAR(length=50),
                    nullable=False)
    
    op.execute("UPDATE family_members SET is_eligible_to_vote = false WHERE is_eligible_to_vote IS NULL")
    op.alter_column('family_members', 'is_eligible_to_vote',
                    existing_type=sa.BOOLEAN(),
                    nullable=False)
    
    # Create indexes
    op.create_index('idx_family_member_aadhar', 'family_members', ['aadhar_id'], unique=False)
    op.create_index('idx_family_member_eligible', 'family_members', ['is_eligible_to_vote'], unique=False)
    op.create_index('idx_family_member_form_data_id', 'family_members', ['form_data_id'], unique=False)
    op.create_index('idx_family_member_voter_id', 'family_members', ['voter_id'], unique=False)
    op.create_index(op.f('ix_family_members_voter_id'), 'family_members', ['voter_id'], unique=False)
    
    # ========================================
    # FORM DATA TABLE
    # ========================================
    
    # Add head of family voter columns
    op.add_column('form_data', sa.Column('head_voter_id', sa.String(length=50), nullable=True))
    op.add_column('form_data', sa.Column('head_aadhar', sa.String(length=12), nullable=True))
    op.add_column('form_data', sa.Column('head_voter_name', sa.String(length=200), nullable=True))
    op.add_column('form_data', sa.Column('head_voter_age', sa.String(length=10), nullable=True))
    op.add_column('form_data', sa.Column('head_voter_relation', sa.String(length=50), nullable=True))
    
    # Create indexes
    op.create_index('idx_form_data_head_voter_id', 'form_data', ['head_voter_id'], unique=False)
    op.create_index(op.f('ix_form_data_head_voter_id'), 'form_data', ['head_voter_id'], unique=False)
    
    # ========================================
    # VOTERS TABLE
    # ========================================
    
    # Add form_id column (nullable)
    op.add_column('voters', sa.Column('form_id', sa.Integer(), nullable=True))
    
    # ✅ Add is_surveyed with server_default to handle existing rows
    op.add_column('voters', 
        sa.Column('is_surveyed', sa.Boolean(), 
                  nullable=False, server_default='false'))
    
    # Add survey_date (nullable)
    op.add_column('voters', sa.Column('survey_date', sa.DateTime(timezone=True), nullable=True))
    
    # Create indexes
    op.create_index('idx_voters_form_id', 'voters', ['form_id'], unique=False)
    op.create_index('idx_voters_is_surveyed', 'voters', ['is_surveyed'], unique=False)
    op.create_index(op.f('ix_voters_form_id'), 'voters', ['form_id'], unique=False)
    op.create_index(op.f('ix_voters_is_surveyed'), 'voters', ['is_surveyed'], unique=False)
    
    # Create foreign key constraint
    op.create_foreign_key(
        'fk_voters_form_id',  # ✅ Named constraint
        'voters', 'form_data', 
        ['form_id'], ['id'], 
        ondelete='SET NULL'
    )


def downgrade() -> None:
    """Downgrade schema."""
    
    # ========================================
    # VOTERS TABLE
    # ========================================
    
    # Drop foreign key constraint
    op.drop_constraint('fk_voters_form_id', 'voters', type_='foreignkey')
    
    # Drop indexes
    op.drop_index(op.f('ix_voters_is_surveyed'), table_name='voters')
    op.drop_index(op.f('ix_voters_form_id'), table_name='voters')
    op.drop_index('idx_voters_is_surveyed', table_name='voters')
    op.drop_index('idx_voters_form_id', table_name='voters')
    
    # Drop columns
    op.drop_column('voters', 'survey_date')
    op.drop_column('voters', 'is_surveyed')
    op.drop_column('voters', 'form_id')
    
    # ========================================
    # FORM DATA TABLE
    # ========================================
    
    # Drop indexes
    op.drop_index(op.f('ix_form_data_head_voter_id'), table_name='form_data')
    op.drop_index('idx_form_data_head_voter_id', table_name='form_data')
    
    # Drop columns
    op.drop_column('form_data', 'head_voter_relation')
    op.drop_column('form_data', 'head_voter_age')
    op.drop_column('form_data', 'head_voter_name')
    op.drop_column('form_data', 'head_aadhar')
    op.drop_column('form_data', 'head_voter_id')
    
    # ========================================
    # FAMILY MEMBERS TABLE
    # ========================================
    
    # Drop indexes
    op.drop_index(op.f('ix_family_members_voter_id'), table_name='family_members')
    op.drop_index('idx_family_member_voter_id', table_name='family_members')
    op.drop_index('idx_family_member_form_data_id', table_name='family_members')
    op.drop_index('idx_family_member_eligible', table_name='family_members')
    op.drop_index('idx_family_member_aadhar', table_name='family_members')
    
    # Revert NOT NULL constraints
    op.alter_column('family_members', 'is_eligible_to_vote',
                    existing_type=sa.BOOLEAN(),
                    nullable=True)
    op.alter_column('family_members', 'gender',
                    existing_type=sa.VARCHAR(length=50),
                    nullable=True)
    op.alter_column('family_members', 'age',
                    existing_type=sa.INTEGER(),
                    nullable=True)
    op.alter_column('family_members', 'name',
                    existing_type=sa.VARCHAR(length=255),
                    nullable=True)
    
    # Drop column
    op.drop_column('family_members', 'is_voter_verified')
