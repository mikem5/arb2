#
#
# The pair object. Stores an order book in asks and bids variables.
# The list of ask/bids is composed in the following way. 
# [price, quantity] and is generally only filled by the specific orderbook
# filling market operation.
#
# Every function out of this returns this list object form
# [price, quantity, index]
# the inclusion of index referring to the index location in the ask/bid
# arrays.
# 
# All prices,quantities are stored in the decimal format. index is not
#

import decimal
import operator
import time
import math
import statistics

from config import *

class Pair(object):


        def __init__(self, marketname, name, size, minq, thr=.02, inv = 0):
        
                # name of exchange
                self.market_name = marketname

                # A string containing the particular pair on the exchange
                self.name = name

                # index = range(0,size-1) # we use 50 slots

                # cols = ["actual exchange price", "quantity", "price with fee applied"] this is what is expected
                # if we are inverted, then we have
                #
                #   [inverted price, inv quant, inv fee price, exchg price, exchg quant, exchang fee price]
                #


                self.asks = [[D(999999),D(0),D(99999),D(99999) ,D(0) ,D(99999)]]
                self.bids = [[D(0),D(0),D(0),D(0) ,D(0) ,D(0)]]

                self.updated = 0

                # default to 5 times a second
                self.throttle = thr

                # this signals that we have inverted the API's
                # responses and will need to adjust when
                # interacting with the exchange.
                # 0 = no, 1 = yes
                self.inverted = inv


                # Given default values
                self.mtq =  minq[0]
                self.pi = minq[1]
                self.qi = minq[2]


                # This is the default holder of our
                # last seen trade on the market/ in this pair.
                # We should actually check the saved file
                # upon startup to see what the last added value
                # was so that we can go based off that.
                
                
                self.last_trade = ""



                # statistic records

                # mid weighted price
                # [[price, timestamp], ...]
                self.midwp = []

                # depth
                # [[ask,bid,timestamp], ...]
                self.depth = []




        # this will give us the pair name, eg btc/usd etc
        def pair(self):
                return self.name

        # These are the default returns in case of some sort of error 
        def zerob(self):
                return [D(0), D(0), 0, D(0), D(0), D(0), D(0)]

        def zeroa(self):
                return [D(999999), D(0), 0, D(99999),D(99999), D(0), D(99999)]

        # These helper functions return in values at the specific index
        # location then format the result into the correct [p,q,i,f] way
        def getA(self, idx):
                return [self.asks[idx][0], self.asks[idx][1], idx, self.asks[idx][2], self.asks[idx][3], self.asks[idx][4], self.asks[idx][5]]

        def getB(self, idx):
                return [self.bids[idx][0], self.bids[idx][1], idx, self.bids[idx][2], self.bids[idx][3], self.bids[idx][4], self.bids[idx][5]]


                

        # we should assume for NOW, that the first in array
        # is the best price
        def qBask(self):
                if not self.asks:
                        return self.zeroa()  
                else:
                        return self.getA(0)

        # we should assume for NOW, that the first in array
        # is the best price
        def qBbid(self):
                if not self.bids:
                        return self.zerob() 
                else:
                        return self.getB(0)




        # A better bid return as this will not get troubled
        # by super low quantity bids designed to fool people
        def quantask(self, idx = 0):

                max = len(self.asks)
                
                if max <= 1:
                        return self.zeroa()

                elif idx >= max-1:
                        return self.getA(-1)

                else:
                        #while self.asks[idx][1] < MIN_COIN and idx < max-1:
                        #       idx += 1                
                        


                        return self.getA(idx)



        # A better bid return as this will not get troubled
        # by super low quantity bids designed to fool people
        def quantbid(self, idx = 0):
                max = len(self.bids)
                #max -= 1
                if max <= 1 :
                        return self.zerob()

                elif idx >= max-1:
                        return self.getB(-1)

                else:
                        #while self.bids[idx][1] < MIN_COIN and idx < max-1:
                        #       idx += 1                
                        
                        return self.getB(idx)


        # Return the middle ask
        def midAsk(self):
                max = len(self.asks)

                return self.quantask(int(math.ceil(max / 2)))

        # Return the middle bid
        def midBid(self):
                max = len(self.bids)

                return self.quantask(int(math.ceil(max / 2)))




        # Super quick simple sort functions
        # These only look at price for sorting
        # i is optional sub sorting method eg, sort by price then sort by
        # quantity, (1), or in higher level Pair sort by mkt balance
        def askSort(self, i = 0):
                if len(self.asks) > 3:
                        if i != 0:
                                self.asks.sort(key=operator.itemgetter(i), reverse=True)
                                self.asks.sort(key=operator.itemgetter(0), reverse=False)
                
                        else:
                                self.asks.sort(key=operator.itemgetter(0), reverse=False)


        
        def bidSort(self, i = 0):
                if len(self.bids) > 3:
                        if i != 0:
                                self.bids.sort(key=operator.itemgetter(0,i), reverse=True)      
                        else:
                                self.bids.sort(key=operator.itemgetter(0), reverse=True)        



        # Quick overview to sort both arrays.
        # Defaults to only sorting by price.
        def pSort(self, i = 0):
                self.askSort(i)
                self.bidSort(i)

        
        # This gives a size of the MINIMUM of either bids or asks
        # so that we can fill the best book sort.
        def minBookSize(self):
                return min(len(self.asks), len(self.bids))





        # basic deduping function. checks against the price
        def dedupe(self, side):
            if side == 'ask':
                side = self.asks
            else:
                side = self.bids

            for i in range (0,len(side)):
                i = 1






        # Exchange min, price, and quantity values
        # If the exchange is inverted we need to adjust on the fly for
        # some of the values, otherwise we just use the given defaults.

        def min_trade_quantity(self):
            if self.inverted == 1:
                # Normally we would be 'buying' BTC with this exchagne rather than
                # 'buying' usd. So a common quantity of .01 is .01 BTC, not usd. 
                # A min quantity of .01 btc then depends on the price of that btc
                # when we size it in USD. eg, .01 btc would require us to sell
                # 10 usd if it is $1000 per btc. So the min quantity for our
                # inverted is then actually 10 usd rather than .01 which is way
                # off the mark
                #
                
                # To start we get the mid point of the exchange
                try:
                    midp = statistics.mean([self.asks[0][0], self.bids[0][0]])
                    midp = 1 / midp
                    qi = midp * (self.mtq + D('.001')) 
                except:
                    qi = D('99999')
                return qi.quantize(df)
            else:
                return self.mtq




        def price_increment(self):
            return self.pi

        def quantity_increment(self):
            return self.qi















        #
        # statistics
        #

        
        # weighted price
        # 
        # its worth pointing out that we are going to do
        # sum( bq * ap + aq * bp) / sum(aq + bq)
        # this should give a better answers than
        # having the prices in a different weight

        def calcMidWP(self):
            size = self.minBookSize()

            numer = D('0')
            denom = D('0')

            for x in range(0,size):
                # price * quant + quant * price
                numer += (self.bids[x][0] * self.bids[x][1]) + (self.asks[x][1] * self.asks[x][0])
                denom += self.bids[x][1] + self.asks[x][1]

            if denom > 0:
                wp = numer / denom
            else:
                wp = D('0')


            # put calculated wp in our array
            self.midwp.append([wp, time.time()])

            if len(self.midwp) > 50:
                del self.midwp[0]

#            self.writeStats(self.midwp[-1], "midwp")
        


        def getMidWP(self):
                if self.midwp != []:
                    return self.midwp[-1]
                else:
                    return [0,0]






    
        # returns the depth of both sides
        def calcDepth(self):
            size = self.minBookSize()

            depth_temp = []

            i = 0
            for side in [self.asks, self.bids]:
                tmp = D('0')
                for x in side:
                    tmp += x[1]

                depth_temp.append(tmp)
                i += 1

            # put depth calcs in array
            self.depth.append([depth_temp[0], depth_temp[1], time.time()])

            if len(self.depth) > 50:
                del self.depth[0]

#           self.writeStats(self.depth[-1], "depth")


        def getDepth(self):
                if self.depth != []:
                    return self.depth[-1]
                else:
                    return [0,0]





        def writeStats(self, data,type):

            filename = "logs/stats/" + self.market_name + "/" + type
            f = open(filename, 'a')
            st = ""
            for x in data[:-1]:
                st += str(x) + ", "

            st += str(data[-1]) + "\n"

            f.write(st)
            f.close()








