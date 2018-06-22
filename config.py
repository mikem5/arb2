import threading
import decimal
import redis


global r_pool
r_pool = redis.ConnectionPool(connection_class=redis.UnixDomainSocketConnection, path="/tmp/redis.sock",decode_responses=True)






global perf_list
perf_list = []

CURRENCIES = ["ltc", "usd", "lsd"]
UNDERLYING = ["btc", "btc", "usd"]


# flags
global ENTERED_ARB 
global ARB_COUNTER 
ENTERED_ARB = 0
ARB_COUNTER = 0

lock = threading.RLock()

D = decimal.Decimal

decimal.getcontext().prec = 16
dq = D(".00000001")
df = D(".01")

# This should be considered since we are
# culling out btc balances
MIN_COIN = D('1')
MIN_BTC = D('.01')

# more defaults
MIN_TRADE_PROFIT = D('-0.00001')


MAX_QUANTITY = D('20')

# A default error term
ERR_RET = D('-1')


# amount of seconds to keep trades in the trade history pairs
TRADES_RETENTION = 1800
