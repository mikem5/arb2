# arb2
Automated cryptocurrency trader

To get this up and running you will need a redis database setup to use the unix socket (/tmp/redis.sock)

Need various python packages, mainly requests, redis, websockets for the exchange scripts.

general procedure is to run each websocket/REST scraper in exchanges which feed into the redis db.
from there run the arb2.py in the main folder which collects from the redis database into an internal
orderbook. From here we plug in the trading logic (vanilla.py) to trade on this compressed orderbook.
