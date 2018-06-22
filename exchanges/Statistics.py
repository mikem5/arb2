#
# Statistics
#
# Contains functions for all "stat" type functions
# should have a stats object for each pair.
#

import decimal
import operator
import time
import math
import redis
import subprocess

from Exchange import *

r_server = redis.StrictRedis(unix_socket_path='/tmp/redis.sock', decode_responses=True)
r_pipe = r_server.pipeline()


exch = ['BTCe', 'gdax', 'kraken', 'poloniex', 'gemini','bitfinex']
exchl = ['BTCe', 'kraken', 'poloniex', 'bitfinex']


MAXVAL = 1

class Stats(object):


        def __init__(self, name):
                
                # A string containing the particular pair on the exchange
                self.name = name

                # vwap history array, a call will fill the vwap for us
                # [[D(vwap), timestamp], ...]
                self.vwap = []

                # volume
                self.volume = []
                
                # mid
                self.midwp = []

                # depth
                self.depth = []


        def setvwap(self, v):
                
                self.vwap.append([v, time.time()])


        def lastvwap(self):
                return self.vwap[-1]


        # Trade history based

        # VWAP
        # based on the entirety of our flat array
        # so we can adjust our timeframe why holding
        # onto more or some other method

        def getVWAP(self, trades):
                # sum of price * q
                # /
                # sum of q
                numer = D('0')
                denom = D('0')

                for x in trades:
                    numer += x[0] * x[1]
                    denom += x[1]
               
                if denom > 0:
                    vwap = numer / denom
                else:
                    vwap = D('0')

                return vwap







        # Orderbook based


        
        # weighted price
        # 
        # its worth pointing out that we are going to do
        # sum( bq * ap + aq * bp) / sum(aq + bq)
        # this should give a better answers than
        # having the prices in a different weight

        def getMidWP(self,asks, bids):

            numer = D('0')
            denom = D('0')
            size = min(len(asks), len(bids))

            for x in range(0,size):
                # price * quant + quant * price
                numer += (bids[x][0] * asks[x][1]) + (bids[x][1] * asks[x][0])
                denom += bids[x][1] + asks[x][1]

            if denom > 0:
                wp = numer / denom
            else:
                wp = D('0')
        
            return wp




        def getMidPrice(self, ask, bid):
            return ((ask[0] + bid[0]) / 2)


    
        # returns the depth of both sides
        def getDepth(self):
            size = self.minBookSize()

            depth_temp = []

            i = 0
            for side in [self.asks, self.bids]:
                tmp = D('0')
                for x in side:
                    tmp += x[1]

                depth_temp.append(tmp)
                i += 1

            return depth_temp



stats = {}
for x in exch:
    stats[x] = Stats(x)

    form = ":".join([x,'usd','trades'])
    timer = time.time() -1800 
    r_pipe.zrangebyscore(form, timer, "+inf",withscores=True)

    if x in exchl:
        form = ":".join([x,'ltc','trades'])
        timer = time.time() -1800 
        r_pipe.zrangebyscore(form, timer, "+inf",withscores=True)

    resp = r_pipe.execute()



    form =""
    i = 0
    for y in resp[0]:
        i +=1
        splt = y[0].split(":")
        price = D(str(splt[0]))
        amount = D(str(splt[1]))
        side = str(splt[2])
        timer = D(str(y[1])) * 1000000000
        timer = str(int(timer)) 
        form += 'market_trades,market={},coin={},forUse=True,side={} price={},amount={} {}\n'.format(x,'btcusd',side,price,amount,timer)
        if i > 50:
            i = 0
            outcall = subprocess.check_output(['curl','-i','-XPOST','http://192.168.1.60:8086/write?db=exch','--data-binary',form])
            form = ""
    print(form)
    outcall = subprocess.check_output(['curl','-i','-XPOST','http://192.168.1.60:8086/write?db=exch','--data-binary',form])

    if x in exchl:
        form =""
        i = 0
        for y in resp[1]:
            i +=1
            splt = y[0].split(":")
            price = D(str(splt[0]))
            amount = D(str(splt[1]))
            side = str(splt[2])
            timer = D(str(y[1])) * 1000000000
            timer = str(int(timer)) 
            form += 'market_trades_ltcbtc,market={},coin={},forUse=True,side={} price={},amount={} {}\n'.format(x,'ltcbtc',side,price,amount,timer)
            if i > 50:
                i = 0
                outcall = subprocess.check_output(['curl','-i','-XPOST','http://192.168.1.60:8086/write?db=exch','--data-binary',form])
                form = ""
        print(form)
        outcall = subprocess.check_output(['curl','-i','-XPOST','http://192.168.1.60:8086/write?db=exch','--data-binary',form])




while True:
    try:
        for cur in ['usd', 'ltc']:
            for x,v in stats.items():
                if cur == 'ltc':
                    if x in exchl:
                        pass
                    else:
                        continue

                    

                # get trades
                print(x, end=' ')
                form = ":".join([x,cur,'trades'])
                r_pipe.zrevrange(form, 0, 50,withscores=True)

                form = ":".join([x,cur,'bid'])
                r_pipe.zrevrange(form, 0, 100)

                form = ":".join([x,cur,'ask'])
                r_pipe.zrange(form, 0, 100)


                form = ":".join([x,cur,'trades'])
                timer = time.time() - 3
                r_pipe.zrangebyscore(form, timer, "+inf",withscores=True)


                resp = r_pipe.execute()





                trades = []
                for y in resp[0]:
                    splt = y[0].split(":")
                    price = D(str(splt[0]))
                    amount = D(str(splt[1]))
                    timer = y[1]
                    trades.append([price,amount,timer]) 
                vwap = v.getVWAP(trades)

                if cur == 'usd':
                    if vwap > 0:
                        vwap = 1/vwap
                    else:
                        continue
                        vwap = 0


                bids = []
                for y in resp[1]:
                    splt = y.split(":")
                    price = D(splt[2])
                    quantity = D(splt[1])
                    bids.append([price,quantity])

                asks = []
                for y in resp[2]:
                    splt = y.split(":")
                    price = D(splt[2])
                    quantity = D(splt[1])
                    asks.append([price,quantity])
                
                if x == 'poloniex':
                    print(asks[0], bids[0])

                midp = v.getMidPrice(asks[0], bids[0])
                midwp = v.getMidWP(asks, bids)
                if midp > MAXVAL or midwp > MAXVAL:
                    continue
                timer = time.time()
                if cur == 'usd':

                    form = 'market_data_btcusd,market={},coin={},forUse=True vwap={},midp={},midwp={}'.format(x,'btcusd',vwap,midp,midwp)
                    if x == 'poloniex':
                        print(form)
                else:
                    form = 'market_data_ltcbtc,market={},coin={},forUse=True vwap={},midp={},midwp={}'.format(x,'ltcbtc',vwap,midp,midwp)
                    if x == 'kraken':
                        print(form)
                
                outcall = subprocess.check_output(['curl','-i','-XPOST','http://192.168.1.60:8086/write?db=exch','--data-binary',form])


                i = 0
                time_end = 0
                form = ""
                print("trades", resp[3])
                for y in resp[3]:
                    i +=1
                    splt = y[0].split(":")
                    price = D(str(splt[0]))
                    amount = D(str(splt[1]))
                    side = str(splt[2])
                    timer = D(str(y[1])) * D('1000000000')
                    if timer == time_end:
                        timer += D('1')
                    else:
                        time_end = timer

                    timer = str(int(timer))
 
                    if cur == 'usd':

                        form = 'market_trades,market={},coin={},forUse=True,side={} price={},amount={} {}\n'.format(x,'btcusd',side,price,amount,timer)
                    else:
                        form = 'market_trades_ltcbtc,market={},coin={},forUse=True,side={} price={},amount={} {}\n'.format(x,'ltcbtc',side,price,amount,timer)
                   
                    outcall = subprocess.check_output(['curl','-i','-XPOST','http://192.168.1.60:8086/write?db=exch','--data-binary',form])


    except:
        pass
    time.sleep(1)   




#curl -i -XPOST 'http://192.168.1.60:8086/write?db=exch' --data-binary 'market_data,market=test,coin=btcusd vwap=.00156,midp=.00455,midap=.00565'
