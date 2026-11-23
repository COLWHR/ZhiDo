-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    credits_balance INTEGER DEFAULT 1000,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- God Logs table
CREATE TABLE IF NOT EXISTS god_logs (
    id SERIAL PRIMARY KEY,
    god_user_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    details TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (god_user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Personas table
CREATE TABLE IF NOT EXISTS personas (
    id SERIAL PRIMARY KEY,
    owner_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    title VARCHAR(255),
    bio TEXT,
    theories JSONB, -- JSON string in SQLite, JSONB in PG
    stance TEXT,
    system_prompt TEXT,
    is_public BOOLEAN DEFAULT FALSE,
    avatar TEXT,
    skills JSONB DEFAULT '[]'::jsonb,
    skill_policy JSONB DEFAULT '{}'::jsonb,
    modalities JSONB DEFAULT '["text"]'::jsonb,
    capabilities_version INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Moderators table
CREATE TABLE IF NOT EXISTS moderators (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    title VARCHAR(255) DEFAULT '主持人',
    bio TEXT,
    system_prompt TEXT,
    greeting_template TEXT,
    closing_template TEXT,
    summary_template TEXT,
    creator_id INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (creator_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Forums table
CREATE TABLE IF NOT EXISTS forums (
    id SERIAL PRIMARY KEY,
    topic TEXT NOT NULL,
    creator_id INTEGER NOT NULL,
    moderator_id INTEGER,
    status VARCHAR(50) DEFAULT 'active',
    summary_history JSONB DEFAULT '[]',
    start_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP WITH TIME ZONE,
    duration_minutes INTEGER DEFAULT 30,
    FOREIGN KEY (creator_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (moderator_id) REFERENCES moderators(id)
);

-- Forum Participants table
CREATE TABLE IF NOT EXISTS forum_participants (
    forum_id INTEGER NOT NULL,
    persona_id INTEGER NOT NULL,
    thoughts_history JSONB DEFAULT '[]',
    PRIMARY KEY (forum_id, persona_id),
    FOREIGN KEY (forum_id) REFERENCES forums(id) ON DELETE CASCADE,
    FOREIGN KEY (persona_id) REFERENCES personas(id) ON DELETE CASCADE
);

-- Messages table
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    forum_id INTEGER NOT NULL,
    persona_id INTEGER,
    moderator_id INTEGER,
    speaker_name VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    turn_count INTEGER DEFAULT 0,
    thought TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (forum_id) REFERENCES forums(id) ON DELETE CASCADE,
    FOREIGN KEY (persona_id) REFERENCES personas(id),
    FOREIGN KEY (moderator_id) REFERENCES moderators(id)
);

-- Observations table
CREATE TABLE IF NOT EXISTS observations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    forum_id INTEGER NOT NULL,
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    left_at TIMESTAMP WITH TIME ZONE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (forum_id) REFERENCES forums(id) ON DELETE CASCADE
);

-- System Logs table
CREATE TABLE IF NOT EXISTS system_logs (
    id SERIAL PRIMARY KEY,
    forum_id INTEGER NOT NULL,
    level VARCHAR(50) DEFAULT 'info',
    source VARCHAR(255),
    content TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (forum_id) REFERENCES forums(id) ON DELETE CASCADE
);

-- RAAMS Round Scheduling Records table
CREATE TABLE IF NOT EXISTS round_schedule_records (
    id SERIAL PRIMARY KEY,
    forum_id INTEGER NOT NULL,
    turn_count INTEGER DEFAULT 0,
    risk_level VARCHAR(10) DEFAULT 'L0',
    risk_signals JSONB DEFAULT '[]'::jsonb,
    escalated BOOLEAN DEFAULT FALSE,
    gate_action VARCHAR(20) DEFAULT 'normal',
    turn_mode VARCHAR(20) DEFAULT 'transition',
    uncertainty VARCHAR(10) DEFAULT 'low',
    interrupted_by_user BOOLEAN DEFAULT FALSE,
    selected_speaker VARCHAR(255),
    candidates JSONB DEFAULT '[]'::jsonb,
    speak_tokens INTEGER DEFAULT 0,
    latency_ms INTEGER DEFAULT 0,
    ablation JSONB DEFAULT '{}'::jsonb,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (forum_id) REFERENCES forums(id) ON DELETE CASCADE
);

-- Chat Messages table
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    persona_id INTEGER NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    message_type VARCHAR(50) DEFAULT 'text',
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (persona_id) REFERENCES personas(id) ON DELETE CASCADE
);

-- Skills catalog
CREATE TABLE IF NOT EXISTS skills (
    id SERIAL PRIMARY KEY,
    skill_key VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(255) DEFAULT 'general',
    description TEXT,
    input_modalities JSONB DEFAULT '[]'::jsonb,
    output_types JSONB DEFAULT '[]'::jsonb,
    required_models JSONB DEFAULT '[]'::jsonb,
    required_tools JSONB DEFAULT '[]'::jsonb,
    params_schema JSONB DEFAULT '{}'::jsonb,
    permission_scope JSONB DEFAULT '[]'::jsonb,
    cost_level VARCHAR(50) DEFAULT 'low',
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Persona to Skill bindings
CREATE TABLE IF NOT EXISTS persona_skill_bindings (
    id SERIAL PRIMARY KEY,
    persona_id INTEGER NOT NULL,
    skill_id INTEGER NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 0,
    policy JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (persona_id) REFERENCES personas(id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE,
    UNIQUE (persona_id, skill_id)
);

-- Persona Knowledge Base
CREATE TABLE IF NOT EXISTS persona_knowledge (
    id SERIAL PRIMARY KEY,
    persona_id INTEGER NOT NULL,
    owner_id INTEGER NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    mime_type TEXT,
    size INTEGER,
    storage_url TEXT NOT NULL,
    sha256 VARCHAR(128),
    extracted_text TEXT,
    char_count INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'ready',
    meta JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (persona_id) REFERENCES personas(id) ON DELETE CASCADE,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Upload attachments
CREATE TABLE IF NOT EXISTS attachments (
    id SERIAL PRIMARY KEY,
    owner_id INTEGER NOT NULL,
    persona_id INTEGER,
    chat_message_id INTEGER,
    session_id INTEGER,
    file_name VARCHAR(255) NOT NULL,
    mime_type TEXT,
    size INTEGER,
    kind VARCHAR(50),
    storage_url TEXT NOT NULL,
    preview_url TEXT,
    sha256 VARCHAR(128),
    meta JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (persona_id) REFERENCES personas(id) ON DELETE SET NULL,
    FOREIGN KEY (chat_message_id) REFERENCES chat_messages(id) ON DELETE SET NULL
);

-- Generated artifacts
CREATE TABLE IF NOT EXISTS artifacts (
    id SERIAL PRIMARY KEY,
    owner_id INTEGER NOT NULL,
    persona_id INTEGER,
    task_run_id INTEGER,
    artifact_type VARCHAR(100) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    mime_type TEXT,
    storage_url TEXT NOT NULL,
    preview_url TEXT,
    version INTEGER DEFAULT 1,
    status VARCHAR(50) DEFAULT 'ready',
    meta JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (persona_id) REFERENCES personas(id) ON DELETE SET NULL
);

-- Task runs for long skill execution
CREATE TABLE IF NOT EXISTS task_runs (
    id SERIAL PRIMARY KEY,
    owner_id INTEGER NOT NULL,
    persona_id INTEGER,
    skill_key VARCHAR(255),
    session_id INTEGER,
    status VARCHAR(50) DEFAULT 'queued',
    progress INTEGER DEFAULT 0,
    input_payload JSONB DEFAULT '{}'::jsonb,
    output_payload JSONB DEFAULT '{}'::jsonb,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP WITH TIME ZONE,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (persona_id) REFERENCES personas(id) ON DELETE SET NULL
);

-- Duxin Sessions table
CREATE TABLE IF NOT EXISTS duxin_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    mode VARCHAR(50) NOT NULL DEFAULT 'support',
    risk_level VARCHAR(10) NOT NULL DEFAULT 'L0',
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    summary TEXT,
    latest_message_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Duxin Messages table
CREATE TABLE IF NOT EXISTS duxin_messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    agent_name VARCHAR(255),
    content TEXT NOT NULL,
    risk_level VARCHAR(10) NOT NULL DEFAULT 'L0',
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES duxin_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Duxin Memories table
CREATE TABLE IF NOT EXISTS duxin_memories (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    memory_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    source_session_id INTEGER,
    user_editable BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (source_session_id) REFERENCES duxin_sessions(id) ON DELETE SET NULL
);

-- Duxin Risk Events table
CREATE TABLE IF NOT EXISTS duxin_risk_events (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    risk_level VARCHAR(10) NOT NULL,
    signals JSONB DEFAULT '[]'::jsonb,
    action_taken TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES duxin_sessions(id) ON DELETE CASCADE
);

-- Duxin Safety Feedback table
CREATE TABLE IF NOT EXISTS duxin_safety_feedback (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_id INTEGER,
    rating VARCHAR(50) NOT NULL,
    content TEXT,
    risk_level VARCHAR(10),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES duxin_sessions(id) ON DELETE SET NULL
);

-- Credit ledger: per-account balance changes
CREATE TABLE IF NOT EXISTS credit_transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    change_amount INTEGER NOT NULL,
    balance_after INTEGER NOT NULL DEFAULT 0,
    reason TEXT NOT NULL,
    category VARCHAR(50) DEFAULT 'text',
    tokens_input INTEGER DEFAULT 0,
    tokens_output INTEGER DEFAULT 0,
    vision_count INTEGER DEFAULT 0,
    reference_type VARCHAR(50),
    reference_id INTEGER,
    note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Dynamic system configuration persisted in DB
CREATE TABLE IF NOT EXISTS system_config (
    id SERIAL PRIMARY KEY,
    config_key VARCHAR(255) NOT NULL UNIQUE,
    config_value TEXT,
    category VARCHAR(50) DEFAULT 'system',
    label TEXT,
    description TEXT,
    updated_by INTEGER,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
);

-- Admin action audit log
CREATE TABLE IF NOT EXISTS admin_audit_logs (
    id SERIAL PRIMARY KEY,
    actor_id INTEGER,
    action TEXT NOT NULL,
    target_type VARCHAR(50),
    target_id INTEGER,
    detail TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE SET NULL
);

-- Team (multi-agent group chat): an owner-assembled group of personas
CREATE TABLE IF NOT EXISTS teams (
    id SERIAL PRIMARY KEY,
    owner_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS team_members (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL,
    persona_id INTEGER NOT NULL,
    role VARCHAR(20) DEFAULT 'member',
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (team_id, persona_id),
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
    FOREIGN KEY (persona_id) REFERENCES personas(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS team_messages (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL,
    sender_type VARCHAR(20) NOT NULL,
    user_id INTEGER,
    persona_id INTEGER,
    speaker_name VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    attachments JSONB DEFAULT '[]'::jsonb,
    mentioned_persona_ids JSONB DEFAULT '[]'::jsonb,
    message_type VARCHAR(20) DEFAULT 'text',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (persona_id) REFERENCES personas(id) ON DELETE SET NULL
);
