UPDATE apis SET url='https://api.openstreetmap.org/api/0.6/' WHERE id='default'
UPDATE presets SET active=1 WHERE id='default'
UPDATE geocoders SET url='https://photon.komoot.io/' WHERE url='https://photon.komoot.de/'
UPDATE checktags SET key='name|ref' WHERE key='name'
