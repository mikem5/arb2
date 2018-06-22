#
#
#

import decimal
import operator
import time
import math

from config import *

class Trades(object):


        def __init__(self, marketname, name, size, thr=.02):
        
                # need this for logging its just a string
                self.market_name = marketname

                # A string containing the particular pair on the exchange
                self.name = name


                # We store the trade history data in an array from asks/bids
                # each will have [price, quantity, tid, timestamp]

                self.asks = []
                self.bids = []


                # can ignore asks/bid side as all that is really important is the
                # price and quantity of a trade. the side is a confusing subject

                # format of a trade:
                # [price, quantity, tid, timestamp, ask/buy]

                # so our flat will be [[trade], [trade], ...]

                self.flat = []


                # time that we last added a trade
                self.updated = 0

                # default to 5 times a second
                self.throttle = thr


                # This is the default holder of our
                # last seen trade on the market/ in this pair.
                # more than likely this will be based on tid 
                # will be format [[price, quantity, tid, timestamp, "ask"/"buy"],OUR TIMESTAMP]
                #
                #
                self.last_trade = [D('0'),D('0'),0,0,'ask',0]


                self.vwap = []
                self.volume = []



        # main function for adding, dedupeing, reindexing the bid/ask
        # arrays from a markets procTrades call
        # we expect incoming temp arrays of bids/asks which conform
        # to the normal format of our bids/asks array and can be
        # appended without any further formatting.

        def addTrades(self, temp_asks, temp_bids, flat):




                # append the temp lists 

                for x in flat:
                    self.flat.append(x)
                for x in temp_asks:
                    self.asks.append(x)
                for x in temp_bids:
                    self.bids.append(x)


                # remove anything over 60 seconds in our _set_ of asks

                self.asks = [x for x in self.asks if x[3] > (time.time() - TRADES_RETENTION)]
                self.bids = [x for x in self.bids if x[3] > (time.time() - TRADES_RETENTION)]
                self.flat = [x for x in self.flat if x[3] > (time.time() - TRADES_RETENTION)]
#


                # dedupe this might be really slow, idk
                self.asks = self.dedupe(self.asks)
                self.bids = self.dedupe(self.bids)
                self.flat = self.dedupe(self.flat)








        def dedupe(self, k):
                new = []
                for elem in k:
                    if elem not in new:
                        new.append(elem)
                return new






        # this will give us the pair name, eg btc/usd etc
        def pair(self):
                return self.name


        # returns the last 5 trades in a list
        # this is regardless of buy/ask and is only based on tid
        def lastTrades(self, amount = 5):

                trades = []
                # start by putting all asks and bids into one array
                for x in self.asks:
                    a = []
                    a = [x[0], x[1], x[2], x[3], 'ask',x[3]]
                    trades.append(a)
                for x in self.bids:
                    b = []
                    b = [x[0], x[1], x[2], x[3], 'bid',x[3]]
                    trades.append(b)

                length = len(trades)

                # as long as it isn't short then proceed
                if length > 3:
                    trades.sort(key=operator.itemgetter(2), reverse=True)                    
                
                if length < amount:
                    amount = length

                temp = []
                for x in range(amount):
                    temp.append(trades[x])

                return temp



        # sort based on the tid
        def askSort(self, i = 0):
                if len(self.asks) > 1:
                        if i != 0:
                                self.asks.sort(key=operator.itemgetter(i), reverse=True)
                                self.asks.sort(key=operator.itemgetter(0), reverse=False)
                
                        else:
                                self.asks.sort(key=operator.itemgetter(2), reverse=True)


        
        def bidSort(self, i = 0):
                if len(self.bids) > 1:
                        if i != 0:
                                self.bids.sort(key=operator.itemgetter(0,i), reverse=True)      
                        else:
                                self.bids.sort(key=operator.itemgetter(2), reverse=True)        


        
        def flatSort(self, i = 0):
                if len(self.flat) > 1:
                        if i != 0:
                                self.flat.sort(key=operator.itemgetter(0,i), reverse=True)      
                        else:
                                self.flat.sort(key=operator.itemgetter(2), reverse=True)        




        # Quick overview to sort both arrays.
        # Defaults to only sorting by tid
        # puts the last tid in last_trade
        def tSort(self, i = 0):
                self.askSort(i)
                self.bidSort(i)
                self.flatSort(i)
                self.tradelog()
                self.get_last_trade()


        # find a trade based on price, returns
        # the quantity traded and time since "now" it was done
        def find_price_trade(self, price):
            for x in self.bids:
                if x[0] == price:
                    return [x[1], x[3]]
            for x in self.asks:
                if x[0] == price:
                    return [x[1], x[3]]



        def get_last_trade(self):
                if self.flat != []:
                    if self.flat[0][3] > self.last_trade[3]:
                        self.last_trade = self.flat[0]
                else:
                    return


        # high tid gives the highest tid in our bid/ask
        # then places that "trade" in the last_trade
        def get_last_trade_old(self):

                # get most last trade tid
                tempt = self.last_trade[2]
                
                # we only look at the TOP value which is the last
                # tid, so we should only call this
                # after a sort
                if self.asks != []:
                    if self.asks[0][2] > tempt:
                            x = self.asks[0]
                            tempt = [x[0], x[1], x[2], x[3], "ask"]
                if self.bids != []:            
                    if self.bids[0][2] > tempt:
                            x = self.bids[0]
                            tempt = [x[0], x[1], x[2], x[3], "bid"]

                self.last_trade = tempt
        
        # This gives a size of the MINIMUM of either bids or asks
        # so that we can fill the best book sort.
        def minBookSize(self):
                return min(len(self.asks), len(self.bids))



        #######################
        # Statistics portion  #
        #######################



        # VWAP
        # based on the entirety of our flat array
        # so we can adjust our timeframe why holding
        # onto more or some other method

        def calcVWAP(self):
                # sum of price * q
                # /
                # sum of q
                numer = D('0')
                denom = D('0')
                vwap = D('0')

                for x in self.flat:
                    numer += x[0] * x[1]
                    denom += x[1]
               
                if denom > 0:
                    vwap = numer / denom
                else:
                    vwap = D('0')


                # add to our array
                self.vwap.append([vwap,time.time()])


                if len(self.vwap) > 50:
                    del self.vwap[0]

                # write out
#                self.writeStats(self.vwap[-1], "vwap")




        def getVWAP(self):
                if self.vwap != []:
                    return self.vwap[-1]
                else:
                    return [0,0]

     
        # returns the volume of all sides as an array
        # [asks, bids, flat]
        def calcVolume(self):
                size = self.minBookSize()

                depth_temp = []

                i = 0
                for side in [self.asks, self.bids, self.flat]:
                    tmp = D('0')
                    for x in side:
                        tmp += x[1]

                    depth_temp.append(tmp)
                    i += 1


                # record in array
                self.volume.append([depth_temp[0], depth_temp[1], depth_temp[2], time.time()])


                if len(self.volume) > 50:
                    del self.volume[0]


                # write out
#                self.writeStats(self.volume[-1], "volume")


        def getVolume(self):
                if self.volume != []:
                    return self.volume[-1]
                else:
                    return [0,0]


        #
        # Logging section
        #

        def writeStats(self, data,type):

            filename = "logs/stats/" + self.market_name + "/" + type
            f = open(filename, 'a')
            st = ""
            for x in data[:-1]:
                st += str(x) + ", " 

            st += str(data[-1]) + "\n"

            f.write(st)
            f.close()

   
      
        def tradelog(self):

            filename = "logs/trades/" + self.market_name + "/" + self.name
            f = open(filename, 'a')
            for trade in reversed(self.flat):
                if trade[2] > self.last_trade[2]:
                    st = ""
                    for x in trade[:-1]:
                        st += str(x) + ", "
                    st += str(trade[-1]) + "\n"

                    f.write(st)
            if st == '-1':
                st = "---->"
                for x in self.last_trade[:-1]:
                    st += str(x) + ", "
                st += str(trade[-1]) + "\n"
                f.write(st)

            f.close()

