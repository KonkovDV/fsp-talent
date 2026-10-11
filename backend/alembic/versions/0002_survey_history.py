"""Survey history: one row per survey submit (ТЗ 2.1 «история опроса»).

Revision ID: 0002_survey_history
Revises: 0001_initial

A separate revision, so a stand already at 0001_initial gets the table by `alembic upgrade head`
instead of a 500 on PUT /candidates/me/survey. Owner-only row-level policy, like candidate_resumes.
"""
from __future__ import annotations

from alembic import op

revision = "0002_survey_history"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE public.survey_history (
    id uuid NOT NULL,
    participant_id uuid NOT NULL,
    specialization character varying(30) NOT NULL,
    industry character varying(40),
    work_goal character varying(40),
    declared_grade character varying(20) NOT NULL,
    experience_years integer,
    created_at timestamp with time zone NOT NULL,
    CONSTRAINT survey_history_pkey PRIMARY KEY (id),
    CONSTRAINT survey_history_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(id) ON DELETE CASCADE
)""")
    op.execute("""CREATE INDEX ix_survey_history_participant ON public.survey_history USING btree (participant_id, created_at DESC)""")
    op.execute("""ALTER TABLE ONLY public.survey_history FORCE ROW LEVEL SECURITY""")
    op.execute("""ALTER TABLE public.survey_history ENABLE ROW LEVEL SECURITY""")
    op.execute("""CREATE POLICY survey_history_owner ON public.survey_history USING (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR ((participant_id)::text = current_setting('app.participant_id'::text, true)))) WITH CHECK (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR ((participant_id)::text = current_setting('app.participant_id'::text, true))))""")
    # The app role gets table rights from the default privileges of 0001; grant explicitly in case
    # the table owner differs from the role that set those defaults.
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fsp_app') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON public.survey_history TO fsp_app;
        END IF;
    END $$""")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.survey_history")
