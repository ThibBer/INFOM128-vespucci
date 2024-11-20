CREATE TABLE filters (name TEXT)
CREATE TABLE filterentries (filter TEXT, include INTEGER DEFAULT 0, type TEXT DEFAULT '*', key TEXT DEFAULT '*', value TEXT DEFAULT '*', active INTEGER DEFAULT 0, FOREIGN KEY(filter) REFERENCES filters(name))
CREATE TABLE offsets (imagery_id TEXT NOT NULL, lon NUMBER NOT NULL, lat NUMBER NOT NULL,  min_zoom INTEGER NOT NULL, max_zoom INTEGER NOT NULL, imagery_lon NUMBER NOT NULL, imagery_lat NUMBER NOT NULL)
CREATE INDEX imagery_idx ON offsets(imagery_id)
CREATE TABLE IF NOT EXISTS photos (lat int, lon int, direction int DEFAULT NULL, dir VARCHAR, name VARCHAR, source VARCHAR DEFAULT NULL);
CREATE INDEX latidx ON photos (lat)
CREATE INDEX lonidx ON photos (lon)
CREATE TABLE IF NOT EXISTS directories (dir VARCHAR, last_scan int8, tag VARCHAR DEFAULT NULL);
CREATE TABLE apis (id TEXT, name TEXT, url TEXT, readonlyurl TEXT, notesurl TEXT, user TEXT, pass TEXT, preset TEXT, showicon INTEGER DEFAULT 1, oauth INTEGER DEFAULT 0, accesstoken TEXT, accesstokensecret TEXT)
CREATE TABLE presets (id TEXT, name TEXT, url TEXT, version TEXT DEFAULT NULL, shortdescription TEXT DEFAULT NULL, description TEXT DEFAULT NULL, lastupdate TEXT, data TEXT, position INTEGER DEFAULT 0, active INTEGER DEFAULT 0, usetranslations INTEGER DEFAULT 1)
CREATE TABLE geocoders (id TEXT, type TEXT, version INTEGER DEFAULT 0, name TEXT, url TEXT, active INTEGER DEFAULT 0)
CREATE TABLE layers (type TEXT, position INTEGER DEFAULT -1, visible INTEGER DEFAULT 1, content_id TEXT)
CREATE TABLE geocoders (id TEXT, type TEXT, version INTEGER DEFAULT 0, name TEXT, url TEXT, active INTEGER DEFAULT 0)
CREATE TABLE layers (type TEXT, position INTEGER DEFAULT -1, visible INTEGER DEFAULT 1, content_id TEXT)
CREATE TABLE keys (name TEXT, type TEXT, key TEXT DEFAULT NULL, add1 TEXT DEFAULT NULL, add2 TEXT DEFAULT NULL, custom INTEGER DEFAULT 0)
CREATE UNIQUE INDEX idx_keys ON keys (name, type)
CREATE UNIQUE INDEX idx_keys ON keys (name, type)
CREATE TABLE sources (name TEXT NOT NULL PRIMARY KEY, updated INTEGER)
CREATE TABLE layers (id TEXT NOT NULL PRIMARY KEY, name TEXT NOT NULL, server_type TEXT NOT NULL, category TEXT DEFAULT NULL, tile_type TEXT DEFAULT NULL, source TEXT NOT NULL, url TEXT NOT NULL, tou_url TEXT, attribution TEXT, overlay INTEGER NOT NULL DEFAULT 0, default_layer INTEGER NOT NULL DEFAULT 0, zoom_min INTEGER NOT NULL DEFAULT 0, zoom_max INTEGER NOT NULL DEFAULT 18, over_zoom_max INTEGER NOT NULL DEFAULT 4, tile_width INTEGER NOT NULL DEFAULT 256, tile_height INTEGER NOT NULL DEFAULT 256, proj TEXT DEFAULT NULL, preference INTEGER NOT NULL DEFAULT 0, start_date INTEGER DEFAULT NULL, end_date INTEGER DEFAULT NULL, no_tile_header TEXT DEFAULT NULL, no_tile_value TEXT DEFAULT NULL, no_tile_tile BLOB DEFAULT NULL, logo_url TEXT DEFAULT NULL, logo BLOB DEFAULT NULL, description TEXT DEFAULT NULL, privacy_policy_url TEXT DEFAULT NULL, attribution_url TEXT DEFAULT NULL, FOREIGN KEY(source) REFERENCES sources(name) ON DELETE CASCADE)
CREATE INDEX layers_overlay_idx ON layers(overlay)
CREATE INDEX layers_source_idx ON layers(source)
CREATE TABLE coverages (id TEXT NOT NULL, zoom_min INTEGER NOT NULL DEFAULT 0, zoom_max INTEGER NOT NULL DEFAULT 18, left INTEGER DEFAULT NULL, bottom INTEGER DEFAULT NULL, right INTEGER DEFAULT NULL, top INTEGER DEFAULT NULL, FOREIGN KEY(id) REFERENCES layers(id) ON DELETE CASCADE)
CREATE INDEX coverages_idx ON coverages(id)
CREATE TABLE headers (id TEXT NOT NULL, name TEXT NOT NULL, value TEXT NOT NULL, FOREIGN KEY(id) REFERENCES layers(id) ON DELETE CASCADE)
CREATE INDEX headers_idx ON headers(id)
CREATE TABLE IF NOT EXISTS t_renderer (id VARCHAR(255) PRIMARY KEY,name VARCHAR(255),base_url VARCHAR(255),zoom_min INTEGER NOT NULL,zoom_max INTEGER NOT NULL,tile_size_log INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS tiles (rendererID VARCHAR(255) NOT NULL,zoom_level INTEGER NOT NULL,tile_column INTEGER NOT NULL,tile_row INTEGER NOT NULL,timestamp INTEGER NOT NULL,countused INTEGER NOT NULL DEFAULT 1,filesize INTEGER NOT NULL,tile_data BLOB, PRIMARY KEY(rendererID,zoom_level,tile_column,tile_row));
CREATE TABLE rulesets (id INTEGER, name TEXT)
CREATE TABLE resurveytags (ruleset INTEGER, key TEXT, value TEXT DEFAULT NULL, is_regexp INTEGER DEFAULT 0, days INTEGER DEFAULT 365, FOREIGN KEY(ruleset) REFERENCES rulesets(id))
CREATE TABLE checktags (ruleset INTEGER, key TEXT, optional INTEGER DEFAULT 0, FOREIGN KEY(ruleset) REFERENCES rulesets(id))
