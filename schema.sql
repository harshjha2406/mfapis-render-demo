-- PostgreSQL schema generated from the SQLAlchemy metadata.

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


CREATE TABLE watermarks (
	source VARCHAR(40) NOT NULL, 
	through_date DATE NOT NULL, 
	PRIMARY KEY (source)
)

;