"""The whole schema in one step.

Revision ID: 0001_initial
Revises:

Tables, checks, partial indexes, the answer-count function and row-level
policies. Extensions are created here. The role fsp_app is created, or stripped
of superuser rights if it already exists.

Contact columns are text. Login looks up email_bindex, not the address itself.
A fresh database is created in that shape. A database that already has this
schema must be stamped onto this revision: upgrade would try to create the
objects again and the transaction would roll back. Objects added here later reach
such a database through app.core.schema_sync, which runs after upgrade.
"""
from __future__ import annotations

import re

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

_SCHEMA = """
CREATE FUNCTION public.app_answer_counts(session_ids uuid[]) RETURNS TABLE(session_id uuid, n bigint, correct bigint)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
        DECLARE
            prev text;
        BEGIN
            prev := current_setting('app.bypass_rls', true);
            PERFORM set_config('app.bypass_rls', 'on', true);
            BEGIN
                RETURN QUERY
                    SELECT i.session_id,
                           count(*)::bigint,
                           count(*) FILTER (WHERE i.is_correct IS TRUE)::bigint
                    FROM test_session_items AS i
                    WHERE i.session_id = ANY(session_ids)
                      AND i.answered_at IS NOT NULL
                      AND i.excluded IS FALSE
                    GROUP BY i.session_id;
            EXCEPTION
                WHEN OTHERS THEN
                    PERFORM set_config('app.bypass_rls', coalesce(prev, ''), true);
                    RAISE;
            END;
            PERFORM set_config('app.bypass_rls', coalesce(prev, ''), true);
        END;
        $$;





CREATE TABLE public.access_logs (
    id uuid NOT NULL,
    employer_id uuid NOT NULL,
    participant_id uuid NOT NULL,
    access_type character varying(50) NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now()
);



CREATE TABLE public.applications (
    id uuid NOT NULL,
    vacancy_id uuid NOT NULL,
    candidate_id uuid NOT NULL,
    status character varying(20) DEFAULT 'applied'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    viewed_at timestamp with time zone
);



CREATE TABLE public.category_assignments (
    id uuid NOT NULL,
    participant_id uuid NOT NULL,
    primary_role character varying(50) NOT NULL,
    grade character varying(20) NOT NULL,
    grade_source character varying(20) DEFAULT 'default'::character varying NOT NULL,
    stack jsonb DEFAULT '[]'::jsonb NOT NULL,
    explanation jsonb DEFAULT '[]'::jsonb NOT NULL,
    rules_version character varying(20) DEFAULT 'v2.0.0'::character varying NOT NULL,
    assigned_at timestamp with time zone DEFAULT now()
);



CREATE TABLE public.consent_logs (
    id uuid NOT NULL,
    participant_id uuid NOT NULL,
    event_type character varying(50) NOT NULL,
    actor_id uuid NOT NULL,
    ip_hash character varying(64),
    "timestamp" timestamp with time zone DEFAULT now(),
    meta jsonb DEFAULT '{}'::jsonb NOT NULL
);



CREATE TABLE public.consents (
    id uuid NOT NULL,
    subject_type character varying(20) NOT NULL,
    subject_id uuid NOT NULL,
    kind character varying(40) NOT NULL,
    version character varying(20) NOT NULL,
    sha256 character varying(64) NOT NULL,
    given_at timestamp with time zone DEFAULT now() NOT NULL,
    withdrawn_at timestamp with time zone,
    ip_hash character varying(64),
    user_agent character varying(300),
    CONSTRAINT ck_consent_subject CHECK (((subject_type)::text = ANY ((ARRAY['participant'::character varying, 'employer'::character varying])::text[])))
);



CREATE TABLE public.discipline_scores (
    id uuid NOT NULL,
    participant_id uuid NOT NULL,
    discipline character varying(50) NOT NULL,
    score double precision NOT NULL,
    sigma double precision NOT NULL,
    lcb double precision NOT NULL,
    confidence double precision NOT NULL,
    events_count integer DEFAULT 0 NOT NULL,
    team_events_count integer DEFAULT 0 NOT NULL,
    best_rank character varying(10),
    rank_assigned_at date,
    rank_order_ref character varying(64),
    top_event_ids jsonb DEFAULT '[]'::jsonb NOT NULL,
    scoring_version character varying(20) NOT NULL,
    computed_at timestamp with time zone DEFAULT now()
);



CREATE TABLE public.email_verifications (
    id uuid NOT NULL,
    subject_type character varying(20) NOT NULL,
    subject_id uuid NOT NULL,
    purpose character varying(20) NOT NULL,
    email text NOT NULL,
    email_bindex character varying(64),
    code_hash character varying(64) NOT NULL,
    token_hash character varying(64) NOT NULL,
    attempts integer DEFAULT 0 NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    consumed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_email_verification_purpose CHECK (((purpose)::text = ANY ((ARRAY['verify'::character varying, 'reset'::character varying])::text[]))),
    CONSTRAINT ck_email_verification_subject CHECK (((subject_type)::text = ANY ((ARRAY['participant'::character varying, 'employer'::character varying])::text[])))
);



CREATE TABLE public.employer_tasks (
    id uuid NOT NULL,
    employer_id uuid NOT NULL,
    vacancy_id uuid,
    title character varying(200) NOT NULL,
    statement text NOT NULL,
    answer_type character varying(10) NOT NULL,
    options jsonb DEFAULT '[]'::jsonb NOT NULL,
    correct_index integer,
    reference_number character varying(40),
    visibility character varying(10) NOT NULL,
    specialization character varying(30),
    candidate_id uuid,
    deadline timestamp with time zone,
    is_open boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_employer_tasks_answer_type CHECK (((answer_type)::text = ANY ((ARRAY['number'::character varying, 'choice'::character varying, 'open'::character varying])::text[]))),
    CONSTRAINT ck_employer_tasks_audience CHECK (((((visibility)::text = 'public'::text) AND (specialization IS NOT NULL) AND (candidate_id IS NULL)) OR (((visibility)::text = 'addressed'::text) AND (candidate_id IS NOT NULL))))
);



CREATE TABLE public.employers (
    id uuid NOT NULL,
    company_name character varying(200) NOT NULL,
    email text NOT NULL,
    email_bindex character varying(64),
    password_hash character varying(200) NOT NULL,
    inn character varying(12),
    website character varying(200),
    subscription_tier character varying(20) DEFAULT 'free'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    description text,
    industry character varying(200),
    email_verified_at timestamp with time zone,
    token_epoch integer DEFAULT 0 NOT NULL,
    refresh_nonce integer DEFAULT 0 NOT NULL,
    invites_paused_at timestamp with time zone,
    guest_until timestamp with time zone,
    totp_secret text,
    totp_last_step bigint,
    totp_verified_at timestamp with time zone,
    fsp_partner boolean DEFAULT false NOT NULL,
    is_methodist boolean DEFAULT false NOT NULL,
    suspended_at timestamp with time zone
);



CREATE TABLE public.grade_confirmations (
    id uuid NOT NULL,
    participant_id uuid NOT NULL,
    specialization character varying(30) NOT NULL,
    grade character varying(20) NOT NULL,
    p_pass double precision,
    theta double precision,
    se double precision,
    session_id uuid,
    confirmed_at timestamp with time zone DEFAULT now() NOT NULL,
    locked_until timestamp with time zone,
    CONSTRAINT ck_grade_confirmation_grade CHECK (((grade)::text = ANY ((ARRAY['intern'::character varying, 'junior'::character varying, 'middle'::character varying, 'senior'::character varying, 'lead'::character varying])::text[])))
);

ALTER TABLE ONLY public.grade_confirmations FORCE ROW LEVEL SECURITY;



CREATE TABLE public.item_stats (
    item_key character varying(80) NOT NULL,
    family_id character varying(40) NOT NULL,
    level integer NOT NULL,
    n integer DEFAULT 0 NOT NULL,
    correct integer DEFAULT 0 NOT NULL,
    expected double precision DEFAULT '0'::double precision NOT NULL,
    variance double precision DEFAULT '0'::double precision NOT NULL,
    sessions integer DEFAULT 0 NOT NULL,
    b_offset double precision DEFAULT '0'::double precision NOT NULL,
    status character varying(20) DEFAULT 'active'::character varying NOT NULL,
    z double precision DEFAULT '0'::double precision NOT NULL,
    quarantined_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    cusum double precision DEFAULT '0'::double precision NOT NULL,
    CONSTRAINT ck_item_stats_status CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'quarantined'::character varying])::text[])))
);


CREATE TABLE public.item_drafts (
    id uuid NOT NULL,
    spec character varying(30) NOT NULL,
    topic character varying(40) NOT NULL,
    level integer NOT NULL,
    stem text NOT NULL,
    key character varying(200) NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    note character varying(500),
    created_at timestamp with time zone NOT NULL,
    reviewed_at timestamp with time zone,
    CONSTRAINT item_drafts_pkey PRIMARY KEY (id),
    CONSTRAINT ck_item_drafts_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'approved'::character varying, 'rejected'::character varying])::text[])))
);

CREATE INDEX ix_item_drafts_status ON public.item_drafts USING btree (status);


CREATE TABLE public.ai_providers (
    id uuid NOT NULL,
    kind character varying(20) NOT NULL,
    label character varying(80) NOT NULL,
    model character varying(100) NOT NULL,
    check_model character varying(100),
    params jsonb NOT NULL,
    secret text NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp with time zone NOT NULL,
    activated_at timestamp with time zone,
    CONSTRAINT ai_providers_pkey PRIMARY KEY (id),
    CONSTRAINT ck_ai_providers_kind CHECK (((kind)::text = ANY ((ARRAY['gigachat'::character varying, 'yandex'::character varying, 'cloudru'::character varying, 'mws'::character varying])::text[])))
);

CREATE UNIQUE INDEX uq_ai_providers_active ON public.ai_providers USING btree (is_active) WHERE is_active;


CREATE TABLE public.employer_favorites (
    id uuid NOT NULL,
    employer_id uuid NOT NULL,
    participant_id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    CONSTRAINT employer_favorites_pkey PRIMARY KEY (id),
    CONSTRAINT uq_employer_favorites_pair UNIQUE (employer_id, participant_id),
    CONSTRAINT employer_favorites_employer_id_fkey FOREIGN KEY (employer_id) REFERENCES public.employers(id) ON DELETE CASCADE,
    CONSTRAINT employer_favorites_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(id) ON DELETE CASCADE
);

ALTER TABLE ONLY public.employer_favorites FORCE ROW LEVEL SECURITY;

ALTER TABLE public.employer_favorites ENABLE ROW LEVEL SECURITY;

CREATE TABLE public.candidate_resumes (
    id uuid NOT NULL,
    participant_id uuid NOT NULL,
    specialization character varying(30) NOT NULL,
    grade character varying(20) NOT NULL,
    stack text[] DEFAULT '{}'::text[] NOT NULL,
    summary text,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    CONSTRAINT candidate_resumes_pkey PRIMARY KEY (id),
    CONSTRAINT uq_candidate_resumes_spec UNIQUE (participant_id, specialization),
    CONSTRAINT candidate_resumes_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(id) ON DELETE CASCADE
);

ALTER TABLE ONLY public.candidate_resumes FORCE ROW LEVEL SECURITY;

ALTER TABLE public.candidate_resumes ENABLE ROW LEVEL SECURITY;

CREATE POLICY candidate_resumes_owner ON public.candidate_resumes USING (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR ((participant_id)::text = current_setting('app.participant_id'::text, true)))) WITH CHECK (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR ((participant_id)::text = current_setting('app.participant_id'::text, true))));

CREATE POLICY candidate_resumes_search ON public.candidate_resumes FOR SELECT USING ((current_setting('app.employer_id'::text, true) <> ''::text));

CREATE POLICY employer_favorites_actor ON public.employer_favorites USING (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR ((employer_id)::text = current_setting('app.employer_id'::text, true)))) WITH CHECK (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR ((employer_id)::text = current_setting('app.employer_id'::text, true))));

CREATE TABLE public.need_hidden (
    id uuid NOT NULL,
    need_id uuid NOT NULL,
    participant_id uuid NOT NULL,
    version integer NOT NULL,
    hidden_at timestamp with time zone NOT NULL,
    CONSTRAINT need_hidden_pkey PRIMARY KEY (id),
    CONSTRAINT uq_need_hidden UNIQUE (need_id, participant_id),
    CONSTRAINT need_hidden_need_id_fkey FOREIGN KEY (need_id) REFERENCES public.needs(id) ON DELETE CASCADE,
    CONSTRAINT need_hidden_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(id) ON DELETE CASCADE
);

ALTER TABLE ONLY public.need_hidden FORCE ROW LEVEL SECURITY;

ALTER TABLE public.need_hidden ENABLE ROW LEVEL SECURITY;

CREATE POLICY need_hidden_actor ON public.need_hidden USING (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR (need_id IN ( SELECT needs.id FROM public.needs)))) WITH CHECK (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR (need_id IN ( SELECT needs.id FROM public.needs))));

CREATE TABLE public.offer_flags (
    id uuid NOT NULL,
    offer_id uuid NOT NULL,
    flag character varying(20) NOT NULL,
    company_name character varying(200) NOT NULL,
    role_title character varying(100) NOT NULL,
    salary_from_gross integer NOT NULL,
    salary_to_gross integer NOT NULL,
    created_at timestamp with time zone NOT NULL,
    CONSTRAINT offer_flags_pkey PRIMARY KEY (id),
    CONSTRAINT uq_offer_flags UNIQUE (offer_id, flag),
    CONSTRAINT ck_offer_flags_flag CHECK (((flag)::text = ANY ((ARRAY['below_market'::character varying, 'suspicious'::character varying])::text[]))),
    CONSTRAINT offer_flags_offer_id_fkey FOREIGN KEY (offer_id) REFERENCES public.offers(id) ON DELETE CASCADE
);

CREATE TABLE public.webhook_endpoints (
    id uuid NOT NULL,
    employer_id uuid NOT NULL,
    url text NOT NULL,
    secret text NOT NULL,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone NOT NULL,
    CONSTRAINT webhook_endpoints_pkey PRIMARY KEY (id),
    CONSTRAINT webhook_endpoints_employer_id_fkey FOREIGN KEY (employer_id) REFERENCES public.employers(id) ON DELETE CASCADE
);

ALTER TABLE ONLY public.webhook_endpoints FORCE ROW LEVEL SECURITY;

ALTER TABLE public.webhook_endpoints ENABLE ROW LEVEL SECURITY;

CREATE POLICY webhook_endpoints_actor ON public.webhook_endpoints USING (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR ((employer_id)::text = current_setting('app.employer_id'::text, true)))) WITH CHECK (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR ((employer_id)::text = current_setting('app.employer_id'::text, true))));

CREATE TABLE public.webhook_deliveries (
    id uuid NOT NULL,
    endpoint_id uuid NOT NULL,
    event_type character varying(40) NOT NULL,
    payload text NOT NULL,
    attempt integer DEFAULT 0 NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    next_at timestamp with time zone NOT NULL,
    last_code integer,
    last_error character varying(300),
    created_at timestamp with time zone NOT NULL,
    CONSTRAINT webhook_deliveries_pkey PRIMARY KEY (id),
    CONSTRAINT webhook_deliveries_endpoint_id_fkey FOREIGN KEY (endpoint_id) REFERENCES public.webhook_endpoints(id) ON DELETE CASCADE
);

ALTER TABLE ONLY public.webhook_deliveries FORCE ROW LEVEL SECURITY;

ALTER TABLE public.webhook_deliveries ENABLE ROW LEVEL SECURITY;

CREATE POLICY webhook_deliveries_actor ON public.webhook_deliveries USING (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR (endpoint_id IN ( SELECT webhook_endpoints.id FROM public.webhook_endpoints)))) WITH CHECK (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR (endpoint_id IN ( SELECT webhook_endpoints.id FROM public.webhook_endpoints))));

CREATE TABLE public.methodist_log (
    id uuid NOT NULL,
    employer_id uuid NOT NULL,
    action character varying(40) NOT NULL,
    subject character varying(80) NOT NULL,
    note character varying(500) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    CONSTRAINT methodist_log_pkey PRIMARY KEY (id),
    CONSTRAINT methodist_log_employer_id_fkey FOREIGN KEY (employer_id) REFERENCES public.employers(id) ON DELETE CASCADE
);

CREATE TABLE public.candidate_blocks (
    id uuid NOT NULL,
    participant_id uuid NOT NULL,
    employer_id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    CONSTRAINT candidate_blocks_pkey PRIMARY KEY (id),
    CONSTRAINT uq_candidate_blocks UNIQUE (participant_id, employer_id),
    CONSTRAINT candidate_blocks_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(id) ON DELETE CASCADE,
    CONSTRAINT candidate_blocks_employer_id_fkey FOREIGN KEY (employer_id) REFERENCES public.employers(id) ON DELETE CASCADE
);

ALTER TABLE ONLY public.candidate_blocks FORCE ROW LEVEL SECURITY;

ALTER TABLE public.candidate_blocks ENABLE ROW LEVEL SECURITY;

CREATE POLICY candidate_blocks_actor ON public.candidate_blocks USING (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR ((participant_id)::text = current_setting('app.participant_id'::text, true)) OR ((employer_id)::text = current_setting('app.employer_id'::text, true)))) WITH CHECK (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR ((participant_id)::text = current_setting('app.participant_id'::text, true))));



CREATE TABLE public.need_shortlist (
    id uuid NOT NULL,
    need_id uuid NOT NULL,
    participant_id uuid NOT NULL,
    version integer NOT NULL,
    score double precision,
    status character varying(20) DEFAULT 'shortlisted'::character varying NOT NULL,
    note character varying(500),
    added_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_need_shortlist_status CHECK (((status)::text = ANY ((ARRAY['shortlisted'::character varying, 'invited'::character varying, 'rejected'::character varying])::text[])))
);

ALTER TABLE ONLY public.need_shortlist FORCE ROW LEVEL SECURITY;



CREATE TABLE public.need_versions (
    id uuid NOT NULL,
    need_id uuid NOT NULL,
    version integer NOT NULL,
    params jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.need_versions FORCE ROW LEVEL SECURITY;



CREATE TABLE public.needs (
    id uuid NOT NULL,
    employer_id uuid NOT NULL,
    title character varying(200) NOT NULL,
    version integer DEFAULT 1 NOT NULL,
    archived boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.needs FORCE ROW LEVEL SECURITY;



CREATE TABLE public.notifications (
    id uuid NOT NULL,
    recipient_role character varying(20) NOT NULL,
    recipient_id uuid NOT NULL,
    kind character varying(40) NOT NULL,
    title character varying(200) NOT NULL,
    body text,
    link character varying(200),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    read_at timestamp with time zone
);



CREATE TABLE public.offer_messages (
    id uuid NOT NULL,
    offer_id uuid NOT NULL,
    author_role character varying(20) NOT NULL,
    body text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    read_at timestamp with time zone
);

ALTER TABLE ONLY public.offer_messages FORCE ROW LEVEL SECURITY;



CREATE TABLE public.offers (
    id uuid NOT NULL,
    employer_id uuid NOT NULL,
    candidate_id uuid NOT NULL,
    salary_from_gross integer NOT NULL,
    salary_to_gross integer NOT NULL,
    currency character varying(3) DEFAULT 'RUB'::character varying NOT NULL,
    role character varying(100) NOT NULL,
    work_format character varying(20) NOT NULL,
    practice_stage character varying(20),
    message text,
    perks jsonb DEFAULT '[]'::jsonb NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    contacts_revealed_at timestamp with time zone,
    employer_viewed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    expires_at timestamp with time zone,
    contact_method text,
    candidate_viewed_at timestamp with time zone,
    decline_reason character varying(20),
    contacts_revoked_at timestamp with time zone,
    responded_at timestamp with time zone,
    CONSTRAINT ck_offer_decline_reason CHECK (((decline_reason IS NULL) OR ((decline_reason)::text = ANY ((ARRAY['salary'::character varying, 'format'::character varying, 'stack'::character varying, 'not_looking'::character varying, 'other'::character varying])::text[]))))
);

ALTER TABLE ONLY public.offers FORCE ROW LEVEL SECURITY;



CREATE TABLE public.participants (
    id uuid NOT NULL,
    fsp_id character varying(64),
    display_name character varying(200),
    email text,
    email_bindex character varying(64),
    telegram text,
    phone text,
    birth_date date,
    region character varying(100),
    show_city boolean DEFAULT true NOT NULL,
    show_stack boolean DEFAULT true NOT NULL,
    show_fsp boolean DEFAULT true NOT NULL,
    show_experience boolean DEFAULT true NOT NULL,
    category_opened_at timestamp with time zone,
    soft_skills jsonb DEFAULT '[]'::jsonb NOT NULL,
    excluded_industries jsonb DEFAULT '[]'::jsonb NOT NULL,
    work_formats jsonb DEFAULT '[]'::jsonb NOT NULL,
    experience_years integer,
    declared_grade character varying(20),
    is_visible boolean DEFAULT true NOT NULL,
    public_profile boolean DEFAULT false NOT NULL,
    is_minor boolean DEFAULT false NOT NULL,
    minor_consent_given boolean DEFAULT false NOT NULL,
    guardian_email text,
    guardian_consent_at timestamp with time zone,
    job_search character varying(20) DEFAULT 'open'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    grade_locked_until timestamp with time zone,
    assessed_grade character varying(20),
    assessed_at timestamp with time zone,
    password_hash character varying(200),
    email_verified_at timestamp with time zone,
    last_login_at timestamp with time zone,
    guest_until timestamp with time zone,
    fsp_linked_at timestamp with time zone,
    specialization character varying(30),
    industry character varying(40),
    work_goal character varying(20),
    survey_at timestamp with time zone,
    practice_topic character varying(40),
    practice_ok boolean,
    practice_at timestamp with time zone,
    deleted_at timestamp with time zone,
    suspended_at timestamp with time zone,
    token_epoch integer DEFAULT 0 NOT NULL,
    profile_version integer DEFAULT 0 NOT NULL,
    salary_from_gross integer,
    salary_to_gross integer,
    employer_task_title character varying(200),
    employer_task_passed boolean,
    employer_task_at timestamp with time zone,
    refresh_nonce integer DEFAULT 0 NOT NULL,
    CONSTRAINT ck_participants_assessed_grade CHECK (((assessed_grade IS NULL) OR ((assessed_grade)::text = ANY ((ARRAY['intern'::character varying, 'junior'::character varying, 'middle'::character varying, 'senior'::character varying, 'lead'::character varying])::text[])))),
    CONSTRAINT ck_participants_job_search CHECK (((job_search)::text = ANY ((ARRAY['active'::character varying, 'open'::character varying, 'not_looking'::character varying])::text[])))
);



CREATE TABLE public.practice_attempts (
    id uuid NOT NULL,
    participant_id uuid NOT NULL,
    vacancy_id uuid,
    topic character varying(40) NOT NULL,
    family_id character varying(40) NOT NULL,
    stem text NOT NULL,
    code text,
    language character varying(20),
    options jsonb NOT NULL,
    correct_index integer NOT NULL,
    explanation text DEFAULT ''::text NOT NULL,
    answer_index integer,
    is_correct boolean,
    created_at timestamp with time zone NOT NULL,
    answered_at timestamp with time zone
);



CREATE TABLE public.profile_embeddings (
    participant_id uuid NOT NULL,
    embedding public.vector(1024) NOT NULL,
    model_version character varying(100) NOT NULL,
    computed_at timestamp with time zone DEFAULT now()
);



CREATE TABLE public.profile_search_index (
    participant_id uuid NOT NULL,
    skills_text text NOT NULL,
    skills_tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple'::regconfig, skills_text)) STORED,
    role character varying(50),
    grade character varying(20),
    region character varying(100),
    updated_at timestamp with time zone DEFAULT now()
);



CREATE TABLE public.qualifications (
    id uuid NOT NULL,
    participant_id uuid NOT NULL,
    discipline character varying(50) NOT NULL,
    rank character varying(10) NOT NULL,
    issued_date date,
    certificate_number character varying(50)
);



CREATE TABLE public.results (
    id uuid NOT NULL,
    participant_id uuid NOT NULL,
    event_id character varying(100) NOT NULL,
    event_name character varying(300) NOT NULL,
    discipline character varying(50) NOT NULL,
    competition_status character varying(30) NOT NULL,
    place integer NOT NULL,
    total_participants integer NOT NULL,
    regions_count integer,
    is_team boolean DEFAULT false NOT NULL,
    team_size integer DEFAULT 1 NOT NULL,
    role character varying(20) DEFAULT 'participant'::character varying NOT NULL,
    event_date date NOT NULL,
    protocol_url character varying(500),
    trust_level character varying(20) DEFAULT 'verified_fsp'::character varying NOT NULL,
    raw_data jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);



CREATE TABLE public.skills (
    id uuid NOT NULL,
    participant_id uuid NOT NULL,
    name character varying(100) NOT NULL,
    raw_name character varying(200),
    source_quote text,
    trust_level character varying(20) DEFAULT 'self_reported'::character varying NOT NULL,
    confirmed boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    confirmed_at timestamp with time zone
);



CREATE TABLE public.task_submissions (
    id uuid NOT NULL,
    task_id uuid NOT NULL,
    participant_id uuid NOT NULL,
    answer_text text,
    answer_index integer,
    status character varying(10) NOT NULL,
    passed boolean,
    comment character varying(1000),
    submitted_at timestamp with time zone DEFAULT now() NOT NULL,
    reviewed_at timestamp with time zone
);



CREATE TABLE public.test_session_items (
    id uuid NOT NULL,
    session_id uuid NOT NULL,
    seq integer NOT NULL,
    item_key character varying(80) NOT NULL,
    family_id character varying(40) NOT NULL,
    level integer NOT NULL,
    topic character varying(30) NOT NULL,
    kind character varying(10) NOT NULL,
    skills jsonb DEFAULT '[]'::jsonb NOT NULL,
    stem text NOT NULL,
    code text,
    language character varying(20),
    options jsonb NOT NULL,
    correct_index integer NOT NULL,
    explanation text,
    a double precision NOT NULL,
    b double precision NOT NULL,
    c double precision NOT NULL,
    time_limit_s integer NOT NULL,
    served_at timestamp with time zone DEFAULT now() NOT NULL,
    answered_at timestamp with time zone,
    answer_index integer,
    is_correct boolean,
    timed_out boolean DEFAULT false NOT NULL,
    excluded boolean DEFAULT false NOT NULL,
    typed boolean DEFAULT false NOT NULL,
    answer_text character varying(32),
    draft_index integer,
    draft_text character varying(32),
    draft_version integer DEFAULT 0 NOT NULL,
    answer_mac character varying(64)
);

ALTER TABLE ONLY public.test_session_items FORCE ROW LEVEL SECURITY;



CREATE TABLE public.test_sessions (
    id uuid NOT NULL,
    participant_id uuid NOT NULL,
    target_grade character varying(20) NOT NULL,
    discipline character varying(80),
    status character varying(20) DEFAULT 'in_progress'::character varying NOT NULL,
    irt_theta double precision,
    score double precision,
    questions_json jsonb DEFAULT '[]'::jsonb NOT NULL,
    grade_assigned character varying(20),
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    completed_at timestamp with time zone,
    specialization character varying(30),
    engine character varying(20) DEFAULT 'fixed_v1'::character varying NOT NULL,
    p_pass double precision,
    p_upgrade double precision,
    theta_se double precision,
    items_count integer,
    stop_reason character varying(30),
    flags jsonb DEFAULT '{}'::jsonb NOT NULL,
    seed bigint,
    CONSTRAINT ck_session_grade CHECK (((target_grade)::text = ANY ((ARRAY['intern'::character varying, 'junior'::character varying, 'middle'::character varying, 'senior'::character varying, 'lead'::character varying])::text[]))),
    CONSTRAINT ck_session_status CHECK (((status)::text = ANY ((ARRAY['in_progress'::character varying, 'completed'::character varying, 'expired'::character varying, 'abandoned'::character varying])::text[])))
);

ALTER TABLE ONLY public.test_sessions FORCE ROW LEVEL SECURITY;



CREATE TABLE public.vacancies (
    id uuid NOT NULL,
    employer_id uuid NOT NULL,
    title character varying(200) NOT NULL,
    role character varying(50),
    grade character varying(20),
    discipline character varying(50),
    min_rank character varying(10),
    skills jsonb DEFAULT '[]'::jsonb NOT NULL,
    salary_from_gross integer,
    salary_to_gross integer,
    work_format character varying(20) DEFAULT 'remote'::character varying NOT NULL,
    allows_minors boolean DEFAULT false NOT NULL,
    is_open boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    description text
);



CREATE TABLE public.verifiable_credentials (
    id uuid NOT NULL,
    participant_id uuid NOT NULL,
    result_id uuid,
    credential_json jsonb NOT NULL,
    proof_value character varying(200) NOT NULL,
    issued_at timestamp with time zone DEFAULT now(),
    revoked_at timestamp with time zone
);



ALTER TABLE ONLY public.access_logs
    ADD CONSTRAINT access_logs_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.applications
    ADD CONSTRAINT applications_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.category_assignments
    ADD CONSTRAINT category_assignments_participant_id_key UNIQUE (participant_id);



ALTER TABLE ONLY public.category_assignments
    ADD CONSTRAINT category_assignments_pkey PRIMARY KEY (id);



ALTER TABLE public.offers
    ADD CONSTRAINT ck_offers_salary_range CHECK ((salary_to_gross >= salary_from_gross)) NOT VALID;



ALTER TABLE public.results
    ADD CONSTRAINT ck_results_place_in_field CHECK ((place <= total_participants)) NOT VALID;



ALTER TABLE public.results
    ADD CONSTRAINT ck_results_place_positive CHECK ((place >= 1)) NOT VALID;



ALTER TABLE public.results
    ADD CONSTRAINT ck_results_team_size_positive CHECK ((team_size >= 1)) NOT VALID;



ALTER TABLE public.results
    ADD CONSTRAINT ck_results_total_positive CHECK ((total_participants >= 1)) NOT VALID;



ALTER TABLE ONLY public.consent_logs
    ADD CONSTRAINT consent_logs_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.consents
    ADD CONSTRAINT consents_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.discipline_scores
    ADD CONSTRAINT discipline_scores_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.email_verifications
    ADD CONSTRAINT email_verifications_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.email_verifications
    ADD CONSTRAINT email_verifications_token_hash_key UNIQUE (token_hash);



ALTER TABLE ONLY public.employer_tasks
    ADD CONSTRAINT employer_tasks_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.employers
    ADD CONSTRAINT employers_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.grade_confirmations
    ADD CONSTRAINT grade_confirmations_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.item_stats
    ADD CONSTRAINT item_stats_pkey PRIMARY KEY (item_key);



ALTER TABLE ONLY public.need_shortlist
    ADD CONSTRAINT need_shortlist_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.need_versions
    ADD CONSTRAINT need_versions_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.needs
    ADD CONSTRAINT needs_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.offer_messages
    ADD CONSTRAINT offer_messages_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.offers
    ADD CONSTRAINT offers_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.participants
    ADD CONSTRAINT participants_fsp_id_key UNIQUE (fsp_id);



ALTER TABLE ONLY public.participants
    ADD CONSTRAINT participants_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.practice_attempts
    ADD CONSTRAINT practice_attempts_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.profile_embeddings
    ADD CONSTRAINT profile_embeddings_pkey PRIMARY KEY (participant_id);



ALTER TABLE ONLY public.profile_search_index
    ADD CONSTRAINT profile_search_index_pkey PRIMARY KEY (participant_id);



ALTER TABLE ONLY public.qualifications
    ADD CONSTRAINT qualifications_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.results
    ADD CONSTRAINT results_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.skills
    ADD CONSTRAINT skills_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.task_submissions
    ADD CONSTRAINT task_submissions_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.test_session_items
    ADD CONSTRAINT test_session_items_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.test_sessions
    ADD CONSTRAINT test_sessions_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.applications
    ADD CONSTRAINT uq_application_pair UNIQUE (vacancy_id, candidate_id);



ALTER TABLE ONLY public.grade_confirmations
    ADD CONSTRAINT uq_grade_confirmation_spec UNIQUE (participant_id, specialization);



ALTER TABLE ONLY public.need_shortlist
    ADD CONSTRAINT uq_need_shortlist UNIQUE (need_id, participant_id);



ALTER TABLE ONLY public.need_versions
    ADD CONSTRAINT uq_need_version UNIQUE (need_id, version);



ALTER TABLE ONLY public.discipline_scores
    ADD CONSTRAINT uq_participant_discipline UNIQUE (participant_id, discipline);



ALTER TABLE ONLY public.skills
    ADD CONSTRAINT uq_participant_skill UNIQUE (participant_id, name);



ALTER TABLE ONLY public.results
    ADD CONSTRAINT uq_result_participant_event UNIQUE (participant_id, event_id);



ALTER TABLE ONLY public.test_session_items
    ADD CONSTRAINT uq_session_item_seq UNIQUE (session_id, seq);



ALTER TABLE ONLY public.task_submissions
    ADD CONSTRAINT uq_task_submission UNIQUE (task_id, participant_id);



ALTER TABLE ONLY public.vacancies
    ADD CONSTRAINT vacancies_pkey PRIMARY KEY (id);



ALTER TABLE ONLY public.verifiable_credentials
    ADD CONSTRAINT verifiable_credentials_pkey PRIMARY KEY (id);



CREATE INDEX ix_access_logs_participant_id ON public.access_logs USING btree (participant_id);



CREATE INDEX ix_applications_candidate_id ON public.applications USING btree (candidate_id);



CREATE INDEX ix_applications_vacancy_id ON public.applications USING btree (vacancy_id);



CREATE INDEX ix_consent_logs_participant_id ON public.consent_logs USING btree (participant_id);



CREATE INDEX ix_consents_subject ON public.consents USING btree (subject_type, subject_id, kind);



CREATE INDEX ix_discipline_scores_participant_id ON public.discipline_scores USING btree (participant_id);



CREATE INDEX ix_email_verifications_bindex ON public.email_verifications USING btree (email_bindex);



CREATE INDEX ix_email_verifications_email ON public.email_verifications USING btree (email);



CREATE INDEX ix_email_verifications_subject ON public.email_verifications USING btree (subject_type, subject_id);



CREATE UNIQUE INDEX uq_employers_email_bindex ON public.employers USING btree (email_bindex);



CREATE INDEX ix_employer_tasks_candidate ON public.employer_tasks USING btree (candidate_id);



CREATE INDEX ix_employer_tasks_employer_id ON public.employer_tasks USING btree (employer_id);



CREATE INDEX ix_employer_tasks_public ON public.employer_tasks USING btree (visibility, specialization, is_open);



CREATE INDEX ix_needs_employer_id ON public.needs USING btree (employer_id);



CREATE INDEX ix_notifications_recipient ON public.notifications USING btree (recipient_role, recipient_id, read_at);



CREATE INDEX ix_offer_messages_offer_id ON public.offer_messages USING btree (offer_id);



CREATE INDEX ix_offers_candidate_id ON public.offers USING btree (candidate_id);



CREATE INDEX ix_offers_employer_id ON public.offers USING btree (employer_id);



CREATE UNIQUE INDEX uq_participants_email_bindex ON public.participants USING btree (email_bindex);



CREATE INDEX ix_participants_fsp_id ON public.participants USING btree (fsp_id);



CREATE INDEX ix_participants_is_visible ON public.participants USING btree (is_visible);



CREATE INDEX ix_participants_region ON public.participants USING btree (region);



CREATE INDEX ix_participants_specialization ON public.participants USING btree (specialization);



CREATE INDEX ix_practice_attempts_participant_id ON public.practice_attempts USING btree (participant_id);



CREATE INDEX ix_profile_embeddings_hnsw ON public.profile_embeddings USING hnsw (embedding public.vector_cosine_ops);



CREATE INDEX ix_psi_grade ON public.profile_search_index USING btree (grade);



CREATE INDEX ix_psi_role ON public.profile_search_index USING btree (role);



CREATE INDEX ix_psi_skills_trgm ON public.profile_search_index USING gin (skills_text public.gin_trgm_ops);



CREATE INDEX ix_psi_skills_tsv ON public.profile_search_index USING gin (skills_tsv);



CREATE INDEX ix_results_participant_id ON public.results USING btree (participant_id);



CREATE INDEX ix_skills_participant_id ON public.skills USING btree (participant_id);



CREATE INDEX ix_task_submissions_participant_id ON public.task_submissions USING btree (participant_id);



CREATE INDEX ix_task_submissions_task_id ON public.task_submissions USING btree (task_id);



CREATE INDEX ix_test_session_items_key ON public.test_session_items USING btree (item_key);



CREATE INDEX ix_test_session_items_session ON public.test_session_items USING btree (session_id);



CREATE INDEX ix_test_sessions_participant_id ON public.test_sessions USING btree (participant_id);



CREATE INDEX ix_vacancies_employer_id ON public.vacancies USING btree (employer_id);



CREATE INDEX ix_verifiable_credentials_participant_id ON public.verifiable_credentials USING btree (participant_id);



CREATE INDEX ix_offers_pair_rejected ON public.offers USING btree (employer_id, candidate_id) WHERE ((status)::text = 'rejected'::text);



CREATE UNIQUE INDEX uix_one_active_session ON public.test_sessions USING btree (participant_id) WHERE ((status)::text = 'in_progress'::text);



CREATE UNIQUE INDEX uq_applications_open_pair ON public.applications USING btree (vacancy_id, candidate_id) WHERE ((status)::text = 'applied'::text);



CREATE UNIQUE INDEX uq_consents_active ON public.consents USING btree (subject_type, subject_id, kind) WHERE (withdrawn_at IS NULL);



CREATE UNIQUE INDEX uq_offers_pending_pair ON public.offers USING btree (employer_id, candidate_id) WHERE ((status)::text = 'pending'::text);



ALTER TABLE ONLY public.access_logs
    ADD CONSTRAINT access_logs_employer_id_fkey FOREIGN KEY (employer_id) REFERENCES public.employers(id);



ALTER TABLE ONLY public.access_logs
    ADD CONSTRAINT access_logs_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(id);



ALTER TABLE ONLY public.applications
    ADD CONSTRAINT applications_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.participants(id);



ALTER TABLE ONLY public.applications
    ADD CONSTRAINT applications_vacancy_id_fkey FOREIGN KEY (vacancy_id) REFERENCES public.vacancies(id);



ALTER TABLE ONLY public.category_assignments
    ADD CONSTRAINT category_assignments_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(id) ON DELETE CASCADE;



ALTER TABLE ONLY public.consent_logs
    ADD CONSTRAINT consent_logs_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(id);



ALTER TABLE ONLY public.discipline_scores
    ADD CONSTRAINT discipline_scores_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(id) ON DELETE CASCADE;



ALTER TABLE ONLY public.employer_tasks
    ADD CONSTRAINT employer_tasks_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.participants(id) ON DELETE CASCADE;



ALTER TABLE ONLY public.employer_tasks
    ADD CONSTRAINT employer_tasks_employer_id_fkey FOREIGN KEY (employer_id) REFERENCES public.employers(id) ON DELETE CASCADE;



ALTER TABLE ONLY public.employer_tasks
    ADD CONSTRAINT employer_tasks_vacancy_id_fkey FOREIGN KEY (vacancy_id) REFERENCES public.vacancies(id) ON DELETE SET NULL;



ALTER TABLE ONLY public.grade_confirmations
    ADD CONSTRAINT grade_confirmations_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(id) ON DELETE CASCADE;



ALTER TABLE ONLY public.need_shortlist
    ADD CONSTRAINT need_shortlist_need_id_fkey FOREIGN KEY (need_id) REFERENCES public.needs(id) ON DELETE CASCADE;



ALTER TABLE ONLY public.need_shortlist
    ADD CONSTRAINT need_shortlist_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(id) ON DELETE CASCADE;



ALTER TABLE ONLY public.need_versions
    ADD CONSTRAINT need_versions_need_id_fkey FOREIGN KEY (need_id) REFERENCES public.needs(id) ON DELETE CASCADE;



ALTER TABLE ONLY public.needs
    ADD CONSTRAINT needs_employer_id_fkey FOREIGN KEY (employer_id) REFERENCES public.employers(id) ON DELETE CASCADE;



ALTER TABLE ONLY public.offer_messages
    ADD CONSTRAINT offer_messages_offer_id_fkey FOREIGN KEY (offer_id) REFERENCES public.offers(id) ON DELETE CASCADE;



ALTER TABLE ONLY public.offers
    ADD CONSTRAINT offers_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.participants(id);



ALTER TABLE ONLY public.offers
    ADD CONSTRAINT offers_employer_id_fkey FOREIGN KEY (employer_id) REFERENCES public.employers(id);



ALTER TABLE ONLY public.practice_attempts
    ADD CONSTRAINT practice_attempts_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(id) ON DELETE CASCADE;



ALTER TABLE ONLY public.profile_embeddings
    ADD CONSTRAINT profile_embeddings_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(id) ON DELETE CASCADE;



ALTER TABLE ONLY public.profile_search_index
    ADD CONSTRAINT profile_search_index_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(id) ON DELETE CASCADE;



ALTER TABLE ONLY public.qualifications
    ADD CONSTRAINT qualifications_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(id) ON DELETE CASCADE;



ALTER TABLE ONLY public.results
    ADD CONSTRAINT results_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(id);



ALTER TABLE ONLY public.skills
    ADD CONSTRAINT skills_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(id) ON DELETE CASCADE;



ALTER TABLE ONLY public.task_submissions
    ADD CONSTRAINT task_submissions_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(id) ON DELETE CASCADE;



ALTER TABLE ONLY public.task_submissions
    ADD CONSTRAINT task_submissions_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.employer_tasks(id) ON DELETE CASCADE;



ALTER TABLE ONLY public.test_session_items
    ADD CONSTRAINT test_session_items_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.test_sessions(id) ON DELETE CASCADE;



ALTER TABLE ONLY public.test_sessions
    ADD CONSTRAINT test_sessions_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(id) ON DELETE CASCADE;



ALTER TABLE ONLY public.vacancies
    ADD CONSTRAINT vacancies_employer_id_fkey FOREIGN KEY (employer_id) REFERENCES public.employers(id);



ALTER TABLE ONLY public.verifiable_credentials
    ADD CONSTRAINT verifiable_credentials_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(id);



ALTER TABLE ONLY public.verifiable_credentials
    ADD CONSTRAINT verifiable_credentials_result_id_fkey FOREIGN KEY (result_id) REFERENCES public.results(id);



ALTER TABLE public.grade_confirmations ENABLE ROW LEVEL SECURITY;


CREATE POLICY grade_confirmations_actor ON public.grade_confirmations USING (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR ((participant_id)::text = current_setting('app.participant_id'::text, true)) OR (current_setting('app.employer_id'::text, true) <> ''::text)));



ALTER TABLE public.need_shortlist ENABLE ROW LEVEL SECURITY;


CREATE POLICY need_shortlist_actor ON public.need_shortlist USING (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR (need_id IN ( SELECT needs.id
   FROM public.needs))));



ALTER TABLE public.need_versions ENABLE ROW LEVEL SECURITY;


CREATE POLICY need_versions_actor ON public.need_versions USING (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR (need_id IN ( SELECT needs.id
   FROM public.needs))));



ALTER TABLE public.needs ENABLE ROW LEVEL SECURITY;


CREATE POLICY needs_actor ON public.needs USING (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR ((employer_id)::text = current_setting('app.employer_id'::text, true))));



ALTER TABLE public.offer_messages ENABLE ROW LEVEL SECURITY;


CREATE POLICY offer_messages_actor ON public.offer_messages USING (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR (offer_id IN ( SELECT offers.id
   FROM public.offers))));



ALTER TABLE public.offers ENABLE ROW LEVEL SECURITY;


CREATE POLICY offers_actor ON public.offers USING (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR ((employer_id)::text = current_setting('app.employer_id'::text, true)) OR ((candidate_id)::text = current_setting('app.participant_id'::text, true))));



ALTER TABLE public.test_session_items ENABLE ROW LEVEL SECURITY;


CREATE POLICY test_session_items_actor ON public.test_session_items USING (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR (session_id IN ( SELECT test_sessions.id
   FROM public.test_sessions
  WHERE ((test_sessions.participant_id)::text = current_setting('app.participant_id'::text, true))))));



ALTER TABLE public.test_sessions ENABLE ROW LEVEL SECURITY;


CREATE POLICY test_sessions_actor ON public.test_sessions USING (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR ((participant_id)::text = current_setting('app.participant_id'::text, true)) OR (current_setting('app.employer_id'::text, true) <> ''::text)));



CREATE TABLE public.complaints (
    id uuid NOT NULL,
    offer_id uuid,
    vacancy_id uuid,
    participant_id uuid NOT NULL,
    reason character varying(32) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT complaints_pkey PRIMARY KEY (id),
    CONSTRAINT ck_complaints_one_object CHECK ((((offer_id IS NOT NULL) AND (vacancy_id IS NULL)) OR ((offer_id IS NULL) AND (vacancy_id IS NOT NULL)))),
    CONSTRAINT ck_complaints_reason CHECK (((reason)::text = ANY ((ARRAY['не_вакансия'::character varying, 'сбор_данных'::character varying, 'зарплата_не_та'::character varying, 'оскорбление'::character varying, 'другое'::character varying])::text[]))),
    CONSTRAINT uq_complaints_participant_offer UNIQUE (participant_id, offer_id),
    CONSTRAINT uq_complaints_participant_vacancy UNIQUE (participant_id, vacancy_id),
    CONSTRAINT complaints_offer_id_fkey FOREIGN KEY (offer_id) REFERENCES public.offers(id),
    CONSTRAINT complaints_vacancy_id_fkey FOREIGN KEY (vacancy_id) REFERENCES public.vacancies(id),
    CONSTRAINT complaints_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(id)
);



CREATE INDEX ix_complaints_participant_id ON public.complaints USING btree (participant_id);



ALTER TABLE public.complaints ENABLE ROW LEVEL SECURITY;


CREATE POLICY complaints_actor ON public.complaints USING (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR ((participant_id)::text = current_setting('app.participant_id'::text, true)))) WITH CHECK (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR ((participant_id)::text = current_setting('app.participant_id'::text, true))));



CREATE TABLE public.grade_disputes (
    id uuid NOT NULL,
    participant_id uuid NOT NULL,
    session_id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    CONSTRAINT grade_disputes_pkey PRIMARY KEY (id),
    CONSTRAINT uq_grade_dispute_session UNIQUE (session_id),
    CONSTRAINT grade_disputes_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(id) ON DELETE CASCADE,
    CONSTRAINT grade_disputes_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.test_sessions(id) ON DELETE CASCADE
);



CREATE INDEX ix_grade_disputes_participant ON public.grade_disputes USING btree (participant_id);



ALTER TABLE public.grade_disputes ENABLE ROW LEVEL SECURITY;


CREATE POLICY grade_disputes_actor ON public.grade_disputes USING (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR ((participant_id)::text = current_setting('app.participant_id'::text, true)))) WITH CHECK (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR ((participant_id)::text = current_setting('app.participant_id'::text, true))));



CREATE TABLE public.interview_slots (
    id uuid NOT NULL,
    offer_id uuid NOT NULL,
    starts_at timestamp with time zone NOT NULL,
    format character varying(20) NOT NULL,
    place text,
    chosen boolean DEFAULT false NOT NULL,
    outcome character varying(20),
    outcome_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT interview_slots_pkey PRIMARY KEY (id),
    CONSTRAINT ck_interview_format CHECK (((format)::text = ANY ((ARRAY['online'::character varying, 'office'::character varying, 'phone'::character varying])::text[]))),
    CONSTRAINT ck_interview_outcome CHECK (((outcome IS NULL) OR (chosen AND ((outcome)::text = ANY ((ARRAY['passed'::character varying, 'failed'::character varying, 'no_show'::character varying])::text[]))))),
    CONSTRAINT interview_slots_offer_id_fkey FOREIGN KEY (offer_id) REFERENCES public.offers(id) ON DELETE CASCADE
);



CREATE INDEX ix_interview_slots_offer_id ON public.interview_slots USING btree (offer_id);



CREATE UNIQUE INDEX uq_interview_slots_chosen ON public.interview_slots USING btree (offer_id) WHERE chosen;



ALTER TABLE public.interview_slots ENABLE ROW LEVEL SECURITY;


CREATE POLICY interview_slots_actor ON public.interview_slots USING (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR (offer_id IN ( SELECT offers.id
   FROM public.offers
  WHERE (((offers.employer_id)::text = current_setting('app.employer_id'::text, true)) OR ((offers.candidate_id)::text = current_setting('app.participant_id'::text, true))))))) WITH CHECK (((current_setting('app.bypass_rls'::text, true) = 'on'::text) OR (offer_id IN ( SELECT offers.id
   FROM public.offers
  WHERE (((offers.employer_id)::text = current_setting('app.employer_id'::text, true)) OR ((offers.candidate_id)::text = current_setting('app.participant_id'::text, true)))))));

"""


def _statements(script: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    i = 0
    dollar: str | None = None
    in_single = False
    while i < len(script):
        if dollar is not None:
            if script.startswith(dollar, i):
                buf.append(dollar)
                i += len(dollar)
                dollar = None
            else:
                buf.append(script[i])
                i += 1
            continue
        if in_single:
            buf.append(script[i])
            if script[i:i + 2] == "''":
                buf.append("'")
                i += 2
                continue
            if script[i] == "'":
                in_single = False
            i += 1
            continue
        if script[i] == "'":
            in_single = True
            buf.append("'")
            i += 1
            continue
        if script[i] == "$":
            match = re.match(r"\$[A-Za-z0-9_]*\$", script[i:])
            if match:
                dollar = match.group(0)
                buf.append(dollar)
                i += len(dollar)
                continue
        if script[i] == ";":
            statement = "".join(buf).strip()
            if statement:
                parts.append(statement)
            buf = []
            i += 1
            continue
        buf.append(script[i])
        i += 1
    tail = "".join(buf).strip()
    if tail:
        raise RuntimeError(tail[:200])
    return parts


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for statement in _statements(_SCHEMA):
        op.execute(statement)
    op.execute("REVOKE ALL ON FUNCTION public.app_answer_counts(uuid[]) FROM PUBLIC")
    # CREATE ROLE is rejected inside Alembic's transaction.
    with op.get_context().autocommit_block():
        op.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fsp_app') THEN
                    CREATE ROLE fsp_app NOLOGIN NOSUPERUSER NOBYPASSRLS;
                END IF;
            END $$;
            """
        )
        op.execute("ALTER ROLE fsp_app NOLOGIN NOSUPERUSER NOBYPASSRLS")
    op.execute("GRANT USAGE ON SCHEMA public TO fsp_app")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO fsp_app"
    )
    op.execute("GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO fsp_app")
    op.execute("GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO fsp_app")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO fsp_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO fsp_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO fsp_app"
    )


def downgrade() -> None:
    # alembic_version stays: Alembic deletes its row after this function returns.
    # fsp_app stays too. The role is cluster-wide and the stand already uses it.
    op.execute(
        """
        DO $$
        DECLARE
            name text;
        BEGIN
            FOR name IN
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public' AND tablename <> 'alembic_version'
            LOOP
                EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE', name);
            END LOOP;
        END $$;
        """
    )
    op.execute("DROP FUNCTION IF EXISTS public.app_answer_counts(uuid[])")
    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
