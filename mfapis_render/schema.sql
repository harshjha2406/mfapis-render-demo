
CREATE TABLE fx_provider_budget (
	id VARCHAR(30) NOT NULL, 
	window_start BIGINT NOT NULL, 
	used INTEGER NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE fx_provider_cooldown (
	symbol VARCHAR(20) NOT NULL, 
	retry_at BIGINT NOT NULL, 
	status INTEGER NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	message TEXT NOT NULL, 
	PRIMARY KEY (symbol)
)

;


CREATE TABLE ingestion_status (
	source VARCHAR(40) NOT NULL, 
	last_attempt_at BIGINT, 
	last_success_at BIGINT, 
	status VARCHAR(20) NOT NULL, 
	message TEXT, 
	next_attempt_at BIGINT NOT NULL, 
	PRIMARY KEY (source)
)

;


CREATE TABLE latest_fx_quotes (
	symbol VARCHAR(7) NOT NULL, 
	rate TEXT NOT NULL, 
	provider_timestamp BIGINT NOT NULL, 
	fetched_at BIGINT NOT NULL, 
	raw_response BYTEA NOT NULL, 
	raw_sha256 VARCHAR(64) NOT NULL, 
	PRIMARY KEY (symbol)
)

;


CREATE TABLE observation_revisions (
	revision_id VARCHAR(64) NOT NULL, 
	source VARCHAR(40) NOT NULL, 
	first_seen_at VARCHAR(40) NOT NULL, 
	record_json TEXT NOT NULL, 
	PRIMARY KEY (revision_id)
)

;


CREATE TABLE observations (
	source VARCHAR(40) NOT NULL, 
	entity VARCHAR(80) NOT NULL, 
	metric VARCHAR(100) NOT NULL, 
	observation_date DATE NOT NULL, 
	unit VARCHAR(40) NOT NULL, 
	value NUMERIC(30, 12), 
	frequency VARCHAR(20) NOT NULL, 
	quality VARCHAR(20) NOT NULL, 
	source_url TEXT NOT NULL, 
	raw_sha256 VARCHAR(64) NOT NULL, 
	retrieved_at VARCHAR(40) NOT NULL, 
	attribution TEXT NOT NULL, 
	PRIMARY KEY (source, entity, metric, observation_date, unit)
)

;


CREATE TABLE raw_source_responses (
	sha256 VARCHAR(64) NOT NULL, 
	source VARCHAR(40) NOT NULL, 
	body BYTEA NOT NULL, 
	metadata_json TEXT NOT NULL, 
	PRIMARY KEY (sha256)
)

;


CREATE TABLE watermarks (
	source VARCHAR(40) NOT NULL, 
	through_date DATE NOT NULL, 
	PRIMARY KEY (source)
)

;