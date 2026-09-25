CREATE TABLE evaluation_runs (
	id SERIAL NOT NULL, 
	run_name VARCHAR(80) NOT NULL, 
	dataset_version VARCHAR(40) NOT NULL, 
	dataset_item_id VARCHAR(20) NOT NULL, 
	category VARCHAR(32) NOT NULL, 
	variant VARCHAR(60) NOT NULL, 
	target_llm VARCHAR(40) NOT NULL, 
	input_tokens INTEGER NOT NULL, 
	output_tokens INTEGER, 
	latency_ms INTEGER, 
	quality_score FLOAT, 
	task_success BOOLEAN, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_evaluation_runs_item UNIQUE (run_name, dataset_item_id, variant, target_llm), 
	CONSTRAINT ck_evaluation_runs_category CHECK (category IN ('closed_qa', 'information_extraction', 'classification', 'summarization', 'coding', 'other')), 
	CONSTRAINT ck_evaluation_runs_quality_range CHECK (quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 10))
);

CREATE INDEX ix_evaluation_runs_run_name ON evaluation_runs (run_name);

CREATE TABLE lora_models (
	id SERIAL NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	base_model VARCHAR(120) NOT NULL, 
	lora_rank INTEGER NOT NULL, 
	adapter_path VARCHAR(255), 
	dataset_version VARCHAR(40), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

CREATE TABLE rules (
	id SERIAL NOT NULL, 
	code VARCHAR(40) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	stage VARCHAR(1) NOT NULL, 
	description TEXT NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_rules_stage CHECK (stage IN ('A', 'B')), 
	UNIQUE (code)
);

CREATE TABLE users (
	id SERIAL NOT NULL, 
	display_name VARCHAR(80), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE prompts (
	id SERIAL NOT NULL, 
	user_id INTEGER, 
	original_text TEXT NOT NULL, 
	pii_redactions INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_prompts_expiry_after_creation CHECK (expires_at > created_at), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_prompts_expires_at ON prompts (expires_at);

CREATE TABLE optimization_results (
	id SERIAL NOT NULL, 
	prompt_id INTEGER NOT NULL, 
	ir JSONB NOT NULL, 
	optimized_text TEXT NOT NULL, 
	confidence FLOAT NOT NULL, 
	used_lora BOOLEAN NOT NULL, 
	lora_model_id INTEGER, 
	pipeline_version VARCHAR(20) NOT NULL, 
	latency_ms INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_results_confidence_range CHECK (confidence >= 0 AND confidence <= 1), 
	FOREIGN KEY(prompt_id) REFERENCES prompts (id) ON DELETE CASCADE, 
	FOREIGN KEY(lora_model_id) REFERENCES lora_models (id) ON DELETE SET NULL
);

CREATE INDEX ix_optimization_results_prompt_id ON optimization_results (prompt_id);

CREATE TABLE prompt_features (
	id SERIAL NOT NULL, 
	prompt_id INTEGER NOT NULL, 
	task_type VARCHAR(32) NOT NULL, 
	has_format_spec BOOLEAN NOT NULL, 
	has_context BOOLEAN NOT NULL, 
	missing_constraints JSONB NOT NULL, 
	redundant_phrases JSONB NOT NULL, 
	ambiguous_refs JSONB NOT NULL, 
	confidence FLOAT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_features_task_type CHECK (task_type IN ('closed_qa', 'information_extraction', 'classification', 'summarization', 'coding', 'other')), 
	CONSTRAINT ck_features_confidence_range CHECK (confidence >= 0 AND confidence <= 1), 
	UNIQUE (prompt_id), 
	FOREIGN KEY(prompt_id) REFERENCES prompts (id) ON DELETE CASCADE
);

CREATE TABLE renderings (
	id SERIAL NOT NULL, 
	result_id INTEGER NOT NULL, 
	target_llm VARCHAR(40) NOT NULL, 
	rendered_text TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_renderings_target UNIQUE (result_id, target_llm), 
	FOREIGN KEY(result_id) REFERENCES optimization_results (id) ON DELETE CASCADE
);

CREATE TABLE token_usage (
	id SERIAL NOT NULL, 
	result_id INTEGER NOT NULL, 
	target_llm VARCHAR(40) NOT NULL, 
	tokenizer VARCHAR(60) NOT NULL, 
	original_input_tokens INTEGER NOT NULL, 
	optimized_input_tokens INTEGER NOT NULL, 
	original_output_tokens INTEGER, 
	optimized_output_tokens INTEGER, 
	est_cost_original_usd NUMERIC(12, 6), 
	est_cost_optimized_usd NUMERIC(12, 6), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_token_usage_nonnegative CHECK (original_input_tokens >= 0 AND optimized_input_tokens >= 0), 
	FOREIGN KEY(result_id) REFERENCES optimization_results (id) ON DELETE CASCADE
);

CREATE TABLE transformations (
	id SERIAL NOT NULL, 
	result_id INTEGER NOT NULL, 
	step_no INTEGER NOT NULL, 
	stage VARCHAR(1) NOT NULL, 
	rule_id INTEGER, 
	before_text TEXT NOT NULL, 
	after_text TEXT NOT NULL, 
	note VARCHAR(255), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_transformations_step UNIQUE (result_id, step_no), 
	CONSTRAINT ck_transformations_stage CHECK (stage IN ('B', 'C')), 
	CONSTRAINT ck_transformations_rule_required_for_b CHECK (stage = 'C' OR rule_id IS NOT NULL), 
	FOREIGN KEY(result_id) REFERENCES optimization_results (id) ON DELETE CASCADE, 
	FOREIGN KEY(rule_id) REFERENCES rules (id) ON DELETE SET NULL
);

