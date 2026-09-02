-- Create databases for Airflow
CREATE DATABASE airflow;

-- Main warehouse
\c public_health_warehouse;

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS warehouse;
CREATE SCHEMA IF NOT EXISTS reporting;

-- Staging: long-format health indicators from OWID
CREATE TABLE IF NOT EXISTS staging.stg_health_indicators (
    region_key          VARCHAR(50),
    region_name         VARCHAR(200),
    iso_code            VARCHAR(20),
    region_type         VARCHAR(20),
    year                INTEGER,
    indicator_code      VARCHAR(50),
    indicator_name      VARCHAR(200),
    indicator_category  VARCHAR(50),
    indicator_unit      VARCHAR(20),
    value               NUMERIC(8, 2),
    is_missing          BOOLEAN DEFAULT FALSE,
    is_revised          BOOLEAN DEFAULT FALSE,
    is_estimated        BOOLEAN DEFAULT FALSE,
    loaded_at           TIMESTAMP,
    PRIMARY KEY (region_key, year, indicator_code)
);

CREATE TABLE IF NOT EXISTS staging.stg_regions (
    region_key          VARCHAR(50) PRIMARY KEY,
    region_name         VARCHAR(200),
    iso_code            VARCHAR(20),
    region_type         VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS staging.stg_rejected_rows (
    id                  SERIAL PRIMARY KEY,
    source_row          INTEGER,
    region_name         VARCHAR(200),
    iso_code            VARCHAR(20),
    year                INTEGER,
    indicator_code      VARCHAR(50),
    value               NUMERIC(8, 2),
    reject_reason       VARCHAR(200),
    loaded_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging.stg_data_revisions (
    id                  SERIAL PRIMARY KEY,
    region_key          VARCHAR(50),
    year                INTEGER,
    indicator_code      VARCHAR(50),
    old_value           NUMERIC(8, 2),
    new_value           NUMERIC(8, 2),
    prior_snapshot      VARCHAR(20),
    detected_at         TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging.data_quality_log (
    id                  SERIAL PRIMARY KEY,
    table_name          VARCHAR(100),
    check_name          VARCHAR(100),
    check_result        VARCHAR(20),
    details             TEXT,
    checked_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
