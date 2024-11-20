SELECT rowid as _id, active, include, type, key, value FROM filterentries WHERE filter = '{{na}}'
SELECT rowid as _id, active, include, type, key, value FROM filterentries WHERE filter = '{{na}}'
SELECT rowid as _id, active, include, type, key, value FROM filterentries WHERE filter = '{{na}}'
SELECT rowid as _id, active, include, type, key, value FROM filterentries WHERE filter = '{{na}}'
SELECT coverages.id as id,left,bottom,right,top,coverages.zoom_min as zoom_min,coverages.zoom_max as zoom_max FROM layers,coverages WHERE layers.rowid={{question}} AND layers.id=coverages.id
SELECT * FROM layers WHERE rowid={{question}}
SELECT layers.rowid as _id, name FROM layers
SELECT layers.rowid as _id, name FROM layers WHERE source={{question}} OR source={{question}}
SELECT layers.rowid as _id, name FROM layers WHERE server_type='wms_endpoint' ORDER BY name
SELECT headers.id as id,headers.name as name,value FROM layers,headers WHERE headers.id=layers.id AND overlay={{question}}
SELECT coverages.id as id,left,bottom,right,top,coverages.zoom_min as zoom_min,coverages.zoom_max as zoom_max FROM layers,coverages WHERE coverages.id=layers.id AND overlay={{question}}
SELECT rendererID,zoom_level,tile_column,tile_row,filesize FROM tiles WHERE filesize > 0 ORDER BY timestamp ASC
SELECT zoom_level,tile_column,tile_row,filesize FROM tiles WHERE rendererID='{{na}}' ORDER BY timestamp ASC
SELECT SUM(filesize) AS tmp FROM tiles
SELECT DISTINCT zoom_level FROM tiles ORDER BY zoom_level
SELECT key, value, is_regexp, days FROM resurveytags WHERE rowid={{question}}
SELECT key, optional FROM checktags WHERE rowid={{question}}
SELECT resurveytags.rowid as _id, key, value, is_regexp, days FROM resurveytags WHERE ruleset = 0 ORDER BY key, value
SELECT resurveytags.rowid as _id, key, value, is_regexp, days FROM resurveytags, rulesets WHERE ruleset = rulesets.id and rulesets.name = {{question}} ORDER BY key, value
SELECT checktags.rowid as _id, key, optional FROM checktags WHERE ruleset = 0 ORDER BY key
SELECT checktags.rowid as _id, key, optional FROM checktags, rulesets WHERE ruleset = rulesets.id and rulesets.name = {{question}} ORDER BY key
