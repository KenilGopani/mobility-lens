-- Runs once on first container start. Local development only.
CREATE DATABASE mobility_lens_test OWNER mobility;
\connect mobility_lens
CREATE EXTENSION IF NOT EXISTS postgis;
\connect mobility_lens_test
CREATE EXTENSION IF NOT EXISTS postgis;
