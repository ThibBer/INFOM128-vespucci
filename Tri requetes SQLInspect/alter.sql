ALTER TABLE photos ADD direction int DEFAULT NULL
ALTER TABLE photos ADD source VARCHAR DEFAULT NULL
ALTER TABLE directories ADD tag VARCHAR DEFAULT NULL
ALTER TABLE apis ADD COLUMN showicon INTEGER DEFAULT 0
ALTER TABLE apis ADD COLUMN oauth INTEGER DEFAULT 0
ALTER TABLE apis ADD COLUMN accesstoken TEXT DEFAULT NULL
ALTER TABLE apis ADD COLUMN accesstokensecret TEXT DEFAULT NULL
ALTER TABLE presets ADD COLUMN active INTEGER DEFAULT 0
ALTER TABLE apis ADD COLUMN readonlyurl TEXT DEFAULT NULL
ALTER TABLE apis ADD COLUMN notesurl TEXT DEFAULT NULL
ALTER TABLE presets ADD COLUMN position INTEGER DEFAULT 0
ALTER TABLE presets ADD COLUMN usetranslations INTEGER DEFAULT 1
ALTER TABLE presets ADD COLUMN version TEXT DEFAULT NULL
ALTER TABLE presets ADD COLUMN shortdescription TEXT DEFAULT NULL
ALTER TABLE presets ADD COLUMN description TEXT DEFAULT NULL
ALTER TABLE layers ADD COLUMN no_tile_header TEXT DEFAULT NULL
ALTER TABLE layers ADD COLUMN no_tile_value TEXT DEFAULT NULL
ALTER TABLE layers ADD COLUMN description TEXT DEFAULT NULL
ALTER TABLE layers ADD COLUMN privacy_policy_url TEXT DEFAULT NULL
ALTER TABLE layers ADD COLUMN category TEXT DEFAULT NULL
ALTER TABLE layers ADD COLUMN attribution_url TEXT DEFAULT NULL
ALTER TABLE layers ADD COLUMN no_tile_tile BLOB DEFAULT NULL
ALTER TABLE layers ADD COLUMN tile_type TEXT DEFAULT NULL
ALTER TABLE resurveytags ADD COLUMN is_regexp INTEGER DEFAULT 0