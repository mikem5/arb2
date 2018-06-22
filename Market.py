#
#       General Market object
# This contains most interactions with the pair, general retreival of the
# orderbook and other associated functioas
#
#
#
import decimal
import json
import time
import hmac
import hashlib
import requests
import urllib.request, urllib.parse, urllib.error
import random
import copy
import math
import subprocess
import redis

import logging
logger = logging.getLogger(__name__)

hdlr = logging.FileHandler('logs/logger.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s',datefmt='%s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.WARNING)




from Pair import *
from Trades import *
from Balance import *
from OrderList import *

from config import *


class Market(object):

        def __init__(self,cur, url, rang=50, f=1.002, thrp=.02, thrm=0, mtq = [0,0]):

                # An array of currency names
                self.curPairs = cur

                # The url is an ARRAY [] where 0 is the first bit
                # then we stop and continue after the curPair would be
                # added so that we have [0] + curPair + [1] for the
                # complete url. but our defURL will only have [0] and [1]
                self.defURL = url

                # The range or orderbook depth default 50
                self.range = rang


                # Default fee is .2%
                # we write as 1.002
                # This is a decimal from this point on
                self.fee = D(str(f))



                # throttles should be deleted

                # Default throttle is 0
                # this is time between calls
                self.throttle = thrm

                # we set this so that we can keep track
                self.throttle_updated = time.time()

                # Main orderbook pairs initialization process
                self.pairs=[]
                for i,x in enumerate(self.curPairs):
                        if x != 0:
                            # set the inverted bit
                            if self.pairKey(x) == 'usd':
                                self.pairs.append(Pair(self.mname,x,self.range,mtq[i],thrp,inv = 1)) # we make the currency pairs, thrp is the default pair throttle
                            # non inverted, "normal"
                            else:
                                self.pairs.append(Pair(self.mname,x,self.range,mtq[i],thrp, inv = 0)) # we make the currency pairs, thrp is the default pair throttle
                        else:
                                self.pairs.append(x)


                # same process for trades history
                self.trades=[]
                for x in self.curPairs:
                        if x != 0:
                                self.trades.append(Trades(self.mname,x,self.range,thrp)) # we make the currency pairs, thrp is the default pair throttle
                            
                                # now we open the trade file and get the last trade
                                try:
                                    line = subprocess.check_output(['tail','-1','logs/trades/' + self.mname + '/' + x])
                                    # now parse the trade
                                    y = line.split(',')
                                    self.trades[-1].last_trade = [D(str(y[0])), D(str(y[1])), int(str(y[2])), int(str(y[3])), 'bid',str(time.time())]
                                except:
                                    pass

                        else:
                                self.trades.append(x)



                # This is the balance sheet object
                self.balances = Balance()


                # this is the order array for an open "market maker" order
                self.open_order_mm = OrderList()


                # This indicates if the market is in some type of error
                # so we halt trading on it
                self.hold_trade = 0


                # This variable indicates that we interacted in a trade
                # so we should call the cancelorders/setBalance
                # to update our book.
                self.need_update = 0

                # Market was last alive at this point
                self.last_alive = time.time()


                # A way to count number of trades executed on this market
                self.totaltrades = 0


                # Last quantity is a way for threading execution to get
                # the last traded amount since python threads cant
                # return the value that well.
                self.last_quantity_traded = D('-1')
    
                
                # The initial nonce is loaded from a saved file. This SHOULD
                # be quite close to the last one, but just in case we
                # will increment by 100 at the start to make sure we are not off
                # this could change later.
                # nonces are stored in nonce/


                filename = "nonce/" + self.mname
                f = open(filename,'r')

                self.initial_nonce = int(f.readline()) + 100
                self.current_nonce = 0

                f.close()


                self.writeNonce()

                # Function which gets initial balances for this market
                self.setBalance(initial = 1)


                # skew for order placement, and order cancel
                self.skew_order = 10
                self.skew_cancel = 10

                # for competing on market making orders
                self.compete_price = []
                for x in self.curPairs:
                    self.compete_price.append(D('0'))



        # This should only be called while we are locked
        # so there really should be no cases where it is overwritten.
        def getNonce(self):
                self.current_nonce += 1
                nonce = self.initial_nonce + self.current_nonce

                # This writes the nonce down if we are around 20
                # in increments
                if (self.current_nonce % 20) == 0:
                        self.writeNonce()       
                return nonce


        # In some cases (exiting, etc) we may want to just write the nonce
        # no matter what
        def writeNonce(self):
                filename = "nonce/" + self.mname
                f = open(filename,'w')
                f.write(str(self.current_nonce + self.initial_nonce))
                f.close()
        

        # to make an API request that is other than the simple
        # get, eg post. This is usually trade, balance, etc calls
        # this is a broad general function which calls a formmating
        # function, formatPost which should be specific to each market
        # that function should return the url, header, and parameters.
        #
        # call will go as follows for a trade call:
        #  market specific: postTrade -(calls)-> postPage
        #       -(calls)-> formatPost -> return response.text
        #
        #
        def postPage(self, typ, params ={}):
                resp = 0
                url = 0
                para = 0
                resp = 0
                try:
                        session = requests.Session()
                        url, para, head = self.formatPost(typ, params)
                        response = session.post(url, headers=head, data=para, timeout = 7, verify = False) # Setting verify False...
                        session.close()
                        resp = response.text
                except (ValueError, TypeError, requests.ConnectionError, requests.Timeout,
                        requests.HTTPError, requests.RequestException):
                        logger.exception("in postPage")
                        resp = 0
                        # raise
                finally:
                        self.postlog(url, typ, para,resp)
                        return resp



        # The full trade call. This takes in params, then
        # formats, sends the trade, and if filled OK. if not
        # filled it cancels order and returns the quantity
        # traded.
        # Error status is a return of -1


        # options is a dict structured as such:
        # { 'loc' :  0 , 1 (eg the pid loc
        #   'side' : bid, ask (req)
        #   'price': D('1')
        #   'quantity' : D('1') req
        #
        #   'post_only': if possible only put a post order (optional)
        #   
        # }
        #



        def postTrade(self, options):
                # Always set quantity traded to -1 just incase
                # some error happens.
                self.last_quantity_traded = D('-1')

                # First we check to see if a trade is possible or
                # are we holding
                if self.hold_trade == 1:
                        return D('-1')

                # Now we set our touched variable
                self.need_update = 1
        

                # Due to some confusion earlier, I need to change the
                # bysl type around as what is happening is I am
                # FILLING a bysl with the opposite type
                # so if the incoming bysl is a bid, I must output
                # an ask order.

                if options['side'] == 'ask':
                        options['side'] = 'bid'
                else:
                        options['side'] = 'ask'


                try:
                        params = self.formatTrade(options)
                        response = self.postPage(self.trade_var,params)
                except (ValueError, TypeError, requests.ConnectionError, requests.Timeout,
                        requests.HTTPError, requests.RequestException):
                        logger.exception("in postTrade, after postPage()")
                        
                        self.hold_trade = 1
                        return D('-1')

                # This would mean that the data returned is not a normal
                # array. not very bad, but should require evaluation
                # likely to be caused by a wrong quantity/available
                try:
                        q, id = self.parseTradeResponse(options['loc'], response)
                        self.last_quantity_traded = D(q)
                except (ValueError, TypeError, KeyError):
                        logger.exception("in postTrade, after parseTrade()")
                        self.hold_trade = 1
                        return D('-1')


                # This means an error occured. if it is 0 we
                # absolutely need to cancel instead.
                # not success though is much better than something else
                # as it means the order was not placed/etc. so simply exit
                if q == D('-1'):
                        self.hold_trade = 1
                        return D('-1')


                self.last_quantity_traded = D(q)
                return D(q)





        #
        # Delete page stub (more RESTful implementations)
        #


        # Quick stub for apis which implement the DELETE
        # command


        def deletePage(self, typ, params ={}):
                resp = 0
                url = 0
                para = 0
                try:
                        session = requests.Session()
                        url, para, head = self.formatPost(typ, params)
                        response = session.delete(url, headers=head, data=para, timeout = 15)
                        session.close()
                        resp = response.text
                except (ValueError, TypeError, requests.ConnectionError, requests.Timeout,
                        requests.HTTPError, requests.RequestException):
                        logger.exception("in deletePage")
                        resp = 0
                        # raise
                finally:
                        self.postlog(url, typ, para,resp)
                        return resp









        #
        # Get process sections
        #



        # This returns the page text we do processing later in procBook, and procTrades
        # our entry variable is the currnecy OBJECT
        # this is so we can later factor in a throttle event
        def getPage(self, pairid, url = 0):

                session = requests.Session()
                if url == 0:
                    page = session.get(self.defURL[0] + pairid.name + self.defURL[1],timeout=5, verify=False)
                else:
                    page = session.get(url, timeout = 5, verify = False)
                
                session.close()
                return page.text




        # Orderbook section

        # This is the general form which is going to be using the
        # get page call, as well as will use the formatting
        # that is desired by the market. all the calls
        # are standard
        # This returns True if updated.
        # False will be for exception, throttle, error etc.
        def getBook(self, loc,content, timer):
            try:
                i = self.pairs[loc]


                # Now is [price, amount, fee price, invp, invq, invfp]
                # if is inverted the invp and price sections are swapped
                # the inversion is done at the exchange level, we always will
                # just place these in the correct position

                i.asks = [[D(b[0]), D(b[1]),D(b[2]), D(b[5]) ,D(b[6]) ,D(b[7]) ] for b in (x.split(":") for x in content[0]) ]
                i.bids = [[D(b[0]), D(b[1]),D(b[2]), D(b[5]) ,D(b[6]) ,D(b[7]) ] for b in (x.split(":") for x in content[1]) ]




                i.updated = float(timer)
                self.throttle_updated = time.time()


                return True

            except:
                logger.exception("in get book" + str(content))
                i.updated = time.time()
                return False










        ###################################################################
        ###################################################################
        # fee structurce:
        # we take in the decimal price, decimal quantity
        # we check our fee variable from the market,
        # then we compute the total after fee's and return that amount
        # in the btc-e case as an example it takes .2% of the transaction
        # so we will instead return a quantity?
        # eg buying ltc from btc, btc-e takes an amount off the ltc you buy.

        # These give the changed QUANTITY back and is actually what markets
        # will do. The common way we will look at these is expecting
        # the exchange to take a cut in the primary currency only
        # so for ltc/btc it will only take cut out of the BTC side
        # so going btc -> ltc we pay higher btc price but get full ltc amount
        # going ltc -> btc again we lose out on BTC quantity not ltc.
        # some exchanges do this differently though so they need their
        # own functions to convert to this standard.
        #

        # This is what it costs to FILL a bid quote for us.
        def BuyFee(self, array):
                price = array[0]
                quantity = array[1]

                btc_flat = price * quantity
                btc_fee = btc_flat * self.fee
                return btc_fee

        # The loss that goes from selling for example LTC -> BTC
        # how much btc we actually get
        def SellFee(self,array):
                price = array[0]
                quantity = array[1]

                btc_flat = price * quantity
                btc_fee = btc_flat / self.fee
                return btc_fee




        # The Bid/Ask-FeePrice is the actual price that it would cost
        # us to fill. This is just looking at cost. Different markets
        # actually subtract the fee's differently from the quantity and
        # do not actually effect the price at all.
        # This should return the price after fee
        def BidFeePrice(self, array):
                price = array[0]
                quantity = array[1]
                idx = array[2]

                return [(price / self.fee) , quantity, idx]

        # for ask
        def AskFeePrice(self, array):
                price = array[0]
                quantity = array[1]
                idx = array[2]

                return [(price * self.fee), quantity, idx]

        # general best viable orderbook price
        # i is the index location
        def bestPrice(self, loc, idx = 0):

                pair = self.pairs[loc]

                if pair == 0:
                        return self.NullPrice()
                else:
                        
                        newa = pair.quantask(idx)
                        newa = [newa[3], newa[1], idx]
                        newb = pair.quantbid(idx)
                        newb = [newb[3], newb[1], idx]
                        return newa, newb




        # in case we do not use the particular pair, or we error
        def NullPrice(self):
                return [D('999999'),D('0'), 0], [D('0'),D('0'), 0]




        ###########################################################
        ###########################################################
        ######### HELPER FUNCTION AREA                            #
        # COMPS AND SETTING ORDERS                                #
        ###########################################################

        # Helper function which checks in "general" if two decimals
        # are close to each other for us.
        def comp_decimal(self, x, y, sens = D('.0075')):
            avg = (x + y) / 2
            diff = x - y
            if avg != 0:
                abs_d = abs(diff/avg)
            else:
                abs_d = 0

            if abs_d > sens:
                return False
            else:
                return True




        # this abstracts the sub call to
        # the creation on our orderbook,
        # also handles updating the balance sheet
        # with the "available"

            
        def placeOrder(self, loc, side, contents):
            status = self.open_order_mm.placeOrder(self.pairKey(self.pairs[loc].name),side,contents)

            self.setAvailBook()

            return status

        def removeOrder(self, loc, side):
            status = self.open_order_mm.removeOrder(self.pairKey(self.pairs[loc].name),side)

            self.setAvailBook()
            
            return status


        def changeOrder(self, loc, side, quantity):
            status = self.open_order_mm.changeQuantity(self.pairKey(self.pairs[loc].name),side,quantity)

            self.setAvailBook()
            
            return status


        
        #        
        # Inverting section
        #
        # for example, the btc/usd is not the format that we normally
        # use as we have written this in a 'base' btc format, eg: ltc/btc
        # using btc/usd with usd as the base confuses our algos. so
        # in the case where btc is not the base we must adjust.

        # changes from btc/usd to usd/btc assuming this:
        # price * btc = usd  
        # --> btc = usd / price
        # will return the new 'quantity' which is
        # the amount which is the 'usd' portion
        # while the price is now 1/price

        def invertBase(self, price, quantity):
            
            # first we calculate usd, our new quantity
            usd = price * quantity 
            
            # now we get the new price
            if price != D('0'):
                p2 = 1 / price
            else:
                p2 = D('0')
            
            return [p2, usd]


        # reverses the above transform
        # this is to go back for actually placing orders and interacting
        # with exchanges API's

        def revertBase(self, price, quantity):

            # this is the original price
            p1 = 1 / price

            # this is the original quantity
            btc = quantity / p1

            return [p1, btc]






        # Health of exchange monitor

        # Checks on redis what last update was
        # if this is older than our expire time
        # we do the following:
        # 1) stop trading on exchange
        # 2) end the exchanges screen
        # 3) restart the screen
        # 4) get fresh book time
        # 5) check again in 1 minute to make sure the book is fresh
        # 6) lift trading ban
        def checkHealth(self):
            r_server = redis.Redis(connection_pool=r_pool, charset="utf-9", decode_responses=True)
            r_pipe = r_server.pipeline()

            alive = r_server.get(":".join([self.mname,'alive']))
            self.last_alive = float(alive)


            # has not updated in 60 seconds
            if time.time() - self.last_alive> 60: 
                self.fixHealth()
                return False
            else:
                return True
    

        def fixHealth(self):

            self.hold_trade = 1

            # Kill the old exchange process
            cmd = ['screen', '-X', '-S', self.mname, 'kill']
            subprocess.run(cmd)
            
            time.sleep(1)

            # Restart exchange process
            cmd = ['screen', '-dm','-S', self.mname, 'python3','exchanges/'+self.mname+'.py']
            subprocess.run(cmd)

            time.sleep(1)
            

















        ##################### Balance Section ########################


        # We will need to check our balances when we are making trades
        # to ensure that we have the funds available.
        # This function will take the type (eg, bid or ask) that IT
        # will be executing against. iow if we get a buy we are matching
        # an ask order, so we look to btc->coin and vice versa

        # This will then check our balances, calc the fees, and return
        # true is we have funds, false if not.


        def calcBalance(self, loc, coin, price, quantity, bysl):
                if bysl == "ask":
                        btc_needed = self.BuyFee([price,quantity])
                        if btc_needed <= self.balances.getAvail(UNDERLYING[loc]):
                                return True
                        else:
                                return False
                else:
                        if quantity <= self.balances.getAvail(coin):
                                return True
                        else:
                                return False


        # this sums up the orders on our open_order book
        # and subtracts the funds values from our balance
        # sheet to create an "available" balance which we
        # use for all checks
        def setAvailBook(self):
            oomm = {}
            for k,v in self.open_order_mm.open.items():
                oomm[k] = self.open_order_mm.getOpenAmount(k) 
            
            # this is special one off as btc is not kept
            # in the order list
            oomm['btc'] = self.open_order_mm.getOpenAmount('btc')
            
            self.balances.computeAvailable(oomm)











        # Main balance setting function
        #
        # We expect a dictionary of keys/values
        def setBalance(self,content = 0, initial = 0):
                t = time.time() - self.balances.updated
                if self.need_update > 0 or t > 1:
                        try:
                                if self.hold_trade == 1:
                                        # Lets cancel all the orders, pause, then we
                                        # we can try to get the new book
                                        ret = self.cancelAllOrder()
                                        time.sleep(1)

                                        if ret == False:
                                                return False
                                if content == 0:
                                        content = self.postInfo()
                        except (NameError, KeyError, ValueError, TypeError, requests.ConnectionError, requests.Timeout, requests.HTTPError, requests.RequestException):
                                logger.exception("in setBalance after postInfo()")
                                return False

                        # This means we error out
                        if content == {'none': 0}:
                                logger.exception("in setBalance content is none")
                                return False

                        lock.acquire()

                        # If it is initial setup, we just do this
                        try:
                                if initial == 1:
                                    for key,val in content.items():
                                                if key.lower() in self.balances.funds:
                                                    self.balances.setCurrency(key, D(str(val)))

                                    self.balances.funds_new = copy.deepcopy(self.balances.funds)
                                    self.balances.setComp()

                            # Now we must assume it is not initial so we
                            # need to take into account the old balance sheet

                            # So what we are going to do is this,
                            # 1) we set the new incoming data into funds_new
                            # 2) compare the two funds sheets, if they match set
                            #       the "master" funds sheet.
                            # 3) if they don't match, we check our third sheet,
                            #       funds_comp
                            # 4) if funds_new and comp match, it means two data issues
                            #       from the server produced identical results, so
                            #       move that data into funds.
                            # 5) they conflict, so move the funds_new into comp and
                            #       do not touch funds.

                                else:
                                    for key,val in content.items():
                                        if key.lower() in self.balances.funds:
                                            self.balances.setCurrencyNew(key, D(str(val)))

                                    if self.balances.checkNew() == True:
                                        self.balances.setComp()
                                        self.balances.setFunds()
                                        self.hold_trade = 0

                                    elif self.balances.checkComp() == True:
                                        self.balances.setFunds()
                                        self.hold_trade = 0

                                    else:
                                        self.balances.setComp()



                                self.setAvailBook()
                                self.balances.updated = time.time()
                                self.need_update = 0
                                
        
                        except (ValueError, TypeError, requests.ConnectionError, requests.Timeout, requests.HTTPError, requests.RequestException):
                                logger.exception("in setbalance after locked loop")
                                self.need_update = 1
                                self.hold_trade = 1
                                return False
        
                        finally:
                                lock.release()
        
                        return True






        # This adjusts balances that were changed
        # This is only a partial adjustment and is overridden
        # by the loop getting the ACTUAL balance sheets.
        def quickBalances(self, loc, order):

                btc = UNDERLYING[loc]
                coin = CURRENCIES[loc]
                mkt = order[0]
                bysl = order[1]
                price = order[2][0]
                quant = order[3]


                if bysl == "ask":
                        xbtc = self.BuyFee([price,quant,0])
                else:
                        xbtc = self.SellFee([price,quant,0])

        
                btcc = self.balances.getCurrency(btc)
                curc = self.balances.getCurrency(coin)

                if bysl == "ask":
                        self.balances.setCurrency(btc, btcc - xbtc)
                        self.balances.setCurrency(coin,quant + curc)
                elif bysl == "bid":
                        self.balances.setCurrency(coin, curc - quant)
                        self.balances.setCurrency(btc, xbtc + btcc)



                self.setAvailBook()

                if quant > 0:
                    self.totaltrades += 1





        # stub for orderbook conversion used in findOrder
        def orderbookConversion(self, price, quantity):
            return price, quantity


        # this checks the orderbook to find if we can see
        # a matching order
        def findOrder(self, loc, price, quantity, side):
            
            pid = self.pairs[loc]

            if side == 'ask':
                book_side = pid.asks
            else:
                book_side = pid.bids


            # we need to perform a conversion here
            # in case the orderbook performs some
            # weird thing which is unexpected, like applying
            # or not applying the fee
            # eg: a bter conversion

            price,quantity = self.orderbookConversion(price,quantity)



            lock.acquire()
            try:
                if pid.inverted == 1:
                    # 1 cent difference will show up as a +- 4 in the 8th place
                    op = price.quantize(dq)
                else:
                    op = price.quantize(self.pairs[loc].price_increment())
                oq = quantity.quantize(self.pairs[loc].quantity_increment())    

                for x in book_side:
                    if pid.inverted == 1:
                        ap = x[0].quantize(dq)
                    else:
                        ap = x[0].quantize(self.pairs[loc].price_increment())

                    aq = x[1].quantize(self.pairs[loc].quantity_increment())
                    # only the price truly matters, the quantity is just
                    # extra verification
                    if op == ap:
                        if oq == aq:
                            # so both match, we found our order
                            return [True,True]
                        elif aq > oq:
                            # only price matched BUT quantity is same
                            # or higher, implies an existing order perhaps
                            return [True,False]
                        

                # we didnt find our order 
                return [False,False]

            finally:
                lock.release()
            

        # Calculate Skew, which we mean to be the lag between when we place an order,
        # or action, and the orderbook of the market actually reports it.
        # We measure this by placing a small order, then seeing when it
        # shows up on the orderbook, timing that, then timing the cancellation
        # of that order

        def calcSkew(self, loc = 0):
                

            # we don't actually use 'loc' at present, and just go by
            # checks on either drk or ltc as they are our most popular
            # currencies, and most likely to have some balance 

            # Check to make sure we have a balance in the pair to trade on.
            if self.balances.getAvail('ltc') > 2 * self.pairs[loc].min_trade_quantity() :
                pid = self.pairs[0]
            else:
                return -2

            mid = pid.midAsk()

            if mid[1] == 0:
                return False

            # These are higher than the mid price, and the quantity is small
            # times a random value which we can determine in our search
            random_end = random.random() * float(self.pairs[loc].min_trade_quantity())
            our_quantity = self.pairs[loc].min_trade_quantity() + D(random_end).quantize(self.pairs[loc].quantity_increment())
            our_price = mid[0] + self.pairs[loc].price_increment()

            # we want to find a price/quantity not on the book to make computation easier
            # THIS WILL NOT WORK ON FULL ORDER BOOKS
            v = 0
            i = 0
            while (v == 0 and i < 5):
                our_price += self.pairs[loc].price_increment()
                resp = self.findOrder(loc,our_price,our_quantity,'ask')
                if resp == [False,False]:
                    v = 1
                else:
                    i += 1



            # this is true start of making the post, so is more accurate to us actuallyp lacing an order
            # since we are looking to see how long it takes to place an order and it show up on the
            # order book vs how long it takes from us posting to seeing if its on the book

            timer_order = time.perf_counter()

        
            opts = { 'loc': loc,
                    'side': 'ask',
                    'price': our_price,
                    'quantity': our_quantity
                    }

            param = self.formatTrade(opts)


            
            try:
                resp = self.postPage(self.trade_var, param)
            except (KeyError, ValueError, TypeError, requests.ConnectionError, requests.Timeout,
                                requests.HTTPError, requests.RequestException):
                    logger.exception("in skewcalc after postpage")
                    return False

            try:
                data = json.loads(resp)
                order_id = self.getOrderId(data)
            except (ValueError, KeyError, TypeError):
                logger.exception("in skewcalc after datalad")
                return False


            # Now we need to enter a loop and check for the order to show up
            end = 0
            timer_end = 0 
            while (end == 0) and (timer_order + 30 > time.perf_counter()):
                resp = self.findOrder(loc,our_price,our_quantity,'ask')
                if resp == [True, True]:
                    timer_end = time.perf_counter()
                    end = 1
                    break
                elif resp == [True,False] and self.mname == 'BTCe':
                    timer_end = time.perf_counter()
                    end = 1
                    break
                else:
                    time.sleep(.00001)

            self.skew_order = timer_end - timer_order



            # Now we need to determine the time to cancel
            cancel_order = time.perf_counter()

            resp = self.cancelOrder(order_id,loc)

            cancel_end = 0
            end = 0
            while (end == 0) and (cancel_order + 30 > time.perf_counter()):
                resp = self.findOrder(loc, our_price, our_quantity, 'ask')
                if (resp == [False,False]) or (resp == [True,False]):
                    cancel_end = time.perf_counter()
                    end = 1
                    break
                else:
                    time.sleep(.00001)
               

            self.skew_cancel = cancel_end - cancel_order



            # This means it failed somehow
            if self.skew_order < 0 or self.skew_cancel < 0:
                self.skew_order = 31
                self.skew_cancel = 31

                # no reason to cancel if we cancelled above
                try:
                    self.cancelAllOrder()
                except:
                    pass

            return True













        # This writes out to the trade log file, which should be a container
        # for every markets actual interactions with the exchange.
        def postlog(self, url= 0, typ = 0, params = 0,response= 0):
                filename = "logs/trade.logs"
                f = open(filename, 'a')
                a = "##################\n"
                b = "T:{0} ------>> {1} {2} {3}\n".format(int(time.time()), str(url), str(typ), str(a))
                try:
                    c = "<<------" + str(response) + "\n"
                except:
                    c = "error encoding" + "\n"
                
                f.write(a + b + c + a)
                f.close()





        # This logger is for the order book. it dumps the freshly received book into
        # a file under the path of logs/orderbook/exchange/pair.name
        # the way it is written is by  "timestamp --> 'exact html contents'"
        # this way of storing it will enable us to possibly rework or reformat
        # the servers replies without having stripped off or cleaned data in the
        # past.

        def orderbooklog(self, pair, resp = 0):
            filename = "logs/orderbook/" + self.mname + "/" + pair.name
            f = open(filename, 'a')
            timestamp = str(time.time())
            b = "--> "
            content = str(resp) + "\n"
            f.write(timestamp + b + content)
            f.close()




        def fakeTrade(self, loc, side, price, quant):
            self.last_quantity_traded = quant
            return True
