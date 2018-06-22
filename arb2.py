# general default options
from config import *


# Basic objects
from Balance import *
from Pair import *
from Trades import *

# The individual markets and handling of them
from poloniex import *
from gdax import *

# Our gui
from window import *

# trading algo api
from vanilla import *

import threading
import json
import time
import curses
import copy


import logging
logger = logging.getLogger(__name__)
hdlr = logging.FileHandler('logs/logger.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s',datefmt='%s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.WARNING)



class Book(object):

        def __init__(self,m,numCur):

                # numCur is the amount of currencies we are
                # going to be tracking across all the exchanges
                # eg, ltc/btc, ftc/btc would be 2 etc.

                # keep track of running time
                self.__started = time.time()


                # an array of market objects
                self.markets = m

                # this is the default order for currency
                self.currencies = ["ltc", "usd","lsd"]

                # Use the pair object to creat an array of the
                # best currency markets
                # we may need to put the market name/index number
                # in the Pair object so that we can later match


                # The form that the pair objects in ask/bid will take
                # inside this arbitrage object is as follows, and
                # note: IS DIFFERENT FROM DEFAULT PAIR.

                # [price, quantity, index, marketbalance, marketidx]
                self.pairs = []
                self.trades = []
                for x in range(0,numCur):
                        self.pairs.append(Pair('arb',x,50,[dq,dq,dq],0))
                        self.trades.append(Trades('arb',x,50,0))

                # Variables to keep track of overall profit / trade
                # volume....This will need to be corrected for multiple
                # currency pairs as the price/volume is drasticlly different
                self.tprofit = D('0')
                self.ttrades = []

                for x in range(0,numCur):
                        self.ttrades.append(D('0'))


                # Strings for the logger
                self.last_arb = ""
                self.last_best =""
                self.last_string = ""

                # This is for our draw screen function
                self.screen_update = time.time()




                # This sets up the balance sheets for all our currencies
                # we use this to tell if we are way off the mark and need
                # to buy/sell a currency to bring us back to a flat line
                self.market_balances = Balance()

                for m in self.markets:
                        for k,v in m.balances.funds.items():
                                self.market_balances.funds[k] += v

                self.__initial_market_balances = copy.deepcopy(self.market_balances)


                # Write out our initial balances to our log file
                self.logger(self.stringFormat(0,0,0,2))

                # This lets our main loop know if we entered an arb state
                # so that we can run checkbooks/etc
                self.entered_arb = 0

                # This is a counter, to check our books a couple times
                # then stop so we don't just check all the time as
                # really, unless there is a change in 3-5 minutes
                # there shouldnt be any further change
                self.arb_counter = 0


                #
                # This is the discrepancy from the base balance we
                # are off in each market - should use to adjust order
                # trades in the future
                #
                # This is either + or - from the base
                # + means we should sell more (or buy less)
                # - means we should buy more (or sell less)
                #
                self.discrep = { 'usd': D('0'),
                                'ltc': D('0'),
                                'btc': D('0')
                                }


        ###################################


        #
        # Orderbook getting section
        #
        #



        # This is the main function which gets all the orderbook data
        # from the redis server.
        # layout is as follows:
        #   get key from redis which signals markets updated
        #   get all the data from redis ->
        #       process data into each market.pair
        #       build master order book for each pair
        #   done
        #   return true if an update, false if no update
        #
        #
        #
        #


        def buildBooks(self, loc, initial = 0):
            global perf_list
            perf_start = time.perf_counter()


            while True:
                try:
                    #perf_start = time.perf_counter()

                    pid = self.pairs[loc]
                    tempd = {}

                    r_server = redis.Redis(connection_pool=r_pool, charset="utf-9", decode_responses=True)
                    r_pipe = r_server.pipeline()

                    if initial == 1:
                        zunion_flag = 1
                    else:
                        zunion_flag = 0

                    for idx, mkt in enumerate(self.markets):
                        # due to old structure, we must make a temp dict to store
                        # data used for algos, namely the pos, mkt balance, and mkt idx

                        mktb = mkt.balances.getAvail(self.currencies[loc])

                        # and the markets current btc balance
                        mktbtc = mkt.balances.getAvail(UNDERLYING[loc])

                        tempd[mkt.mname] = {'idx' : idx, 'posa':0, 'posb':0,'mktbtc':mktbtc, 'mktb':mktb, 'min_q':MIN_COIN}





                        # this is seeing if an update passed since last time
                        # we qeue up responses no matter what and will just
                        # skip the 0's later


                        if mkt.pairs[loc] != 0:

                            r_pipe.zrange(mkt.mname + ":" + self.currencies[loc] +":ask",0,25)
                            r_pipe.zrevrange(mkt.mname + ":" + self.currencies[loc] +":bid",0,25)
                            zunion_flag = 1


                            if initial == 1:
                                tempd[mkt.mname]['min_q'] = MIN_COIN
                            else:
                                try:
                                    tempd[mkt.mname]['min_q'] = mkt.pairs[loc].min_trade_quantity()
                                except:
                                    tempd[mkt.mname]['min_q'] = MIN_COIN



                        else:
                            r_pipe.echo('0')
                            r_pipe.echo('0')




                    if zunion_flag == 1:
                        # Need a better solution for this
                        if UNDERLYING[loc] == 'usd':
                            ztempa = [x.mname + ":" + self.currencies[loc] + ":ask" for x in self.markets if tempd[x.mname]['mktbtc'] > D('1') ]
                        else: 
                            ztempa = [x.mname + ":" + self.currencies[loc] + ":ask" for x in self.markets if tempd[x.mname]['mktbtc'] > MIN_BTC ]

                        ztempb = [x.mname + ":" + self.currencies[loc] + ":bid" for x in self.markets if tempd[x.mname]['mktb'] > tempd[x.mname]['min_q'] ]

                        if ztempa:
                            r_pipe.zunionstore("ob:"+self.currencies[loc]+":ask", ztempa)
                        if ztempb:
                            r_pipe.zunionstore("ob:"+self.currencies[loc]+":bid", ztempb)
                        r_pipe.zrange("ob:"+self.currencies[loc]+":ask" ,0,100)
                        r_pipe.zrevrange("ob:"+self.currencies[loc]+":bid",0,100)
                    else:
                        r_pipe.echo('0')
                        r_pipe.echo('0')
                        r_pipe.echo('0')
                        r_pipe.echo('0')


                    #perf_start = time.perf_counter()

                    # so this will be a list as [[mkt1 ask's], [mkt1 bids], 0, 0, [mkt3 asks], ..., [zunion asks], [zunion bids]]
                    resp = r_pipe.execute()
                    #perf_end = time.perf_counter()
                    #
                    # from top to here,
                    # this section is ~~.0028s 
                    #
                    #

                    #perf_start = time.perf_counter()
                    # now parse the data
                    # first reparse each individal markets pairs
                    i = 0
                    for idx, mkt in enumerate(self.markets):
                        if resp[i] == '0':
                            i +=2
                            continue
                        else:
                            with lock:
                                mkt.getBook(loc, [resp[i], resp[i+1]],time.time())
                            i+=2

                    #
                    # time here must be roughly ~~.002s
                    #

                    # now main book
                    if resp[-1] != '0':
                        # due to other places using this we need to lock here (eg: window thread calls this and
                        # if these are deleted during update we will crash)
                        perf_start = time.perf_counter()
                        with lock:
                                            #[fee_price, quantity, pos, mkt balance, mkt idx, timer]

                            pid.asks = []
                            for x in resp[-2]:
                                order = x.split(":")
                                mktb = tempd[order[3]]['mktb']
                                idx = tempd[order[3]]['idx']
                                pos = tempd[order[3]]['posa']
                                tempd[order[3]]['posa'] += 1
                                if D(order[1]) < tempd[order[3]]['min_q']:
                                    ignore,b = mkt.NullPrice()
                                    order[1] = b[1]
                                    order[2] = b[0]
                                else:
                                    pid.asks.append([D(order[2]), D(order[1]),pos,mktb,idx,float(order[4])])







                            pid.bids = []
                            for x in resp[-1]:
                                order = x.split(":")
                                mktb = tempd[order[3]]['mktb']
                                idx = tempd[order[3]]['idx']
                                pos = tempd[order[3]]['posb']
                                tempd[order[3]]['posb'] += 1
                                if D(order[1]) < tempd[order[3]]['min_q']:
                                    ignore,b = mkt.NullPrice()
                                    order[1] = b[1]
                                    order[2] = b[0]
                                else:
                                    pid.bids.append([D(order[2]), D(order[1]),pos,mktb,idx,float(order[4])])


                        perf_end = time.perf_counter()
                        perf_list.append(perf_end - perf_start)

                        #
                        # sub block time is ~~.002s
                        #



                    #
                    # This block from after r_pipe.execute
                    # is ~~.004s
                    #
                    #


                        time.sleep(.01)
                    if initial == 1:
                        break
                except:
                    logger.exception("main arb build books")
                    time.sleep(5)





        # Stub allows us to thread this function to allow quicker
        # execution
        def skewStub(self, x):
            if x.mname == 'BTCe' or x.mname == 'gdax' or x.mname == 'kraken' or x.mname == 'gemini':
                x.skew_order = 1
                x.skew_cancel = 1

            else:
                result = x.calcSkew(0)
                if result != True:
                    if result == -2:
                        x.skew_order = x.trade_lag
                        x.skew_cancel = x.trade_lag
                    else:
                        try:
                            x.cancelAllOrder()
                        except:
                            pass



        # This is a threaded subfunction which looks at each market and
        # sees if we need to canceltrades/update orderbook.
        #
        # The rules are as follows:
        # if need_update = 0 nothing is needed
        #
        # if need_update = 1 means trade succeded and we update books
        # if hold trade, most likely something failed so we don't go until
        # everything is checked.

        def setMarketBooks(self):


                if self.entered_arb != 1:
                        if self.arb_counter > 0:
                            self.arb_counter -= 1

                        prior = threading.active_count()
                        p_timeout = time.time()
                        for m in self.markets:
                                t = threading.Thread(target = m.setBalance)
                                t.start()


                        while (threading.active_count() > prior) and (time.time() - 60  < p_timeout):
                            time.sleep(1)


                # So arb has happened, we should set the counter to 3, then
                # continue with normal getting of balances.

                else:
                        # Set to default of 4, so we check books four times,
                        # then we should be good.
                        self.arb_counter = 6
                        for m in self.markets:
                                    m.setBalance()
                        self.sumBooks()
                        self.logger(self.stringFormat(0,0,0,2))


        # This is going to process our initial book versus our current book
        # If it is way out of wack it will call fixBook which will initiate
        # a trade to correct the imbalance.
        def checkBooks(self):
                # First we ensure that all books are up to date
                # this also means that none should be held
                for m in self.markets:
                        if m.need_update >= m.hold_trade > 0:
                                return False






                cur_book = self.market_balances
                initial_b = self.__initial_market_balances


                for k,v in cur_book.funds.items():
                        # we don't want to balance btc at all
                        if k == 'btc':
                                continue

                        # create the absolute average difference
                        avg = (cur_book.funds[k] + initial_b.funds[k]) / 2
                        difference = cur_book.funds[k] - initial_b.funds[k]
                        if avg != 0:
                                abs_d = abs(difference / avg)
                        else:
                                abs_d = 0

                        # This implies that we are .06% off the starting values in
                        # the coins so either we are ahead or behind.
                        # either way we should try to come back to the
                        # initial balance and take profit or eat loss
                        if abs_d > .001:

                                # min quantity on most markets is .01, so we cant correct here
                                if k == 'usd' and abs(difference) < 6:
                                    continue 
                                # so we are going to buy or sell based on the diference
                                self.logger("market needs to be fixed....{0}, {1}".format(k, difference))
                                

                                # dont want to make use of discrep here, so null it out
                                self.getDiscrep(k)

                                self.fixBook(k, difference)

                                # Since there was actually a market change we should reprint the balance
                                # ticker tape.
                                self.sumBooks()
                                self.logger(self.stringFormat(0,0,0,2))

                # Since everything is now "fixed" we can set this to
                # 0 so we don't keep calling it
                self.entered_arb = 0
                return True



        # This method fixes our orderbook by doing a one way trade
        def fixBook(self, coin, diff):
            try:
                for indexr,k in enumerate(self.currencies):
                        if coin == k:
                                pid = self.pairs[indexr]
                                loc = indexr
                                break


                # get the discrep
                discrep = self.getDiscrep(coin)


                # This means we need to buy the currency
                if diff < 0:
                        top = pid.asks
                        bysl = "ask"
                else:
                        top = pid.bids
                        bysl = "bid"

                quant = abs(diff + discrep)


                i = 0
                counter = 0

                while quant > 0 and i+3 < len(top) and counter < 10:

                        h = top[i]
                        mkt = self.markets[h[4]]


                        # So three possible iterations, we may get caught in a loop of low values
                        if counter > 3 or i > 6:
                            if quant < .01:
                                # start lowering the amount of quant
                                quant -= D(i) * D('.001')


                        # we don't trade this pair on this exchange
                        if mkt.pairs[loc] == 0:
                            i += 1
                            continue

                        # we shouldnt be here if we have a hold
                        if mkt.hold_trade == 1:
                            i += 1
                            continue

                        with lock:
                            try:
                                if bysl == "ask":
                                        order = mkt.pairs[loc].getA(h[2])
                                else:
                                        order = mkt.pairs[loc].getB(h[2])
                            except IndexError:
                                return

                            min_quant = min(quant,order[1])

                            if not mkt.calcBalance(loc, coin,order[0],min_quant,bysl):
                                    i += 1
                                    continue

                            if mkt.pairs[loc].min_trade_quantity() > min_quant:
                                    i += 1
                                    continue


                            opts = { 'loc' : loc,
                                    'side': bysl,
                                    'price':order[0],
                                    'quantity':min_quant,
                                    'ioc': True
                                    }


                            # try not locking this section
                            temp_q = mkt.postTrade(opts)
                            if temp_q != -1:
                                    quant -= temp_q
                                    mkt.quickBalances(loc,[mkt,bysl,order,temp_q])
                                    i = 0


                            counter += 1

            except:
                logger.exception("in fixbook")


        # This adds up all the books into our one marketsheet
        def sumBooks(self):
                for k,v in self.market_balances.funds.items():
                        self.market_balances.funds[k] = 0
                        for m in self.markets:
                                self.market_balances.funds[k] += m.balances.getCurrency(k)



        # checks if a market is held, if so return True
        def checkHoldTrade(self):
            for i,m in self.markets:
                if m.hold_trade == 1:
                    return True
            return False

        # Creates custom strings for use in keeping track of arbs and
        # also for writing out to logs.
        def stringFormat(self, ask, bid, pairn, arb=0, p=D('0') , q=D('0') ):

                ds = D('.00000001')
                if arb == 1:
                        return "M:{6} [{0}:{1} a], [{2}:{3} b]ARB: Q:{4} P:{5}".format(
                                ask[0].quantize(ds),  # price
                                self.markets[ask[4]].mname, # market
                                bid[0].quantize(ds),
                                self.markets[bid[4]].mname,
                                q.quantize(ds),
                                p, pairn
                                )


                elif arb == 2:
                    return "BAL: BTC: {0}, LTC: {2}, USD : {1}".format(
                                self.market_balances.getCurrency('btc').normalize(),
                                self.market_balances.getCurrency('usd').normalize(),
                                self.market_balances.getCurrency('ltc').normalize()
                                )

                else:
                        return 'M:{4} [{0}:{1} a], [{2}:{3} b]'.format(
                                ask[0].normalize(),
                                self.markets[ask[4]].mname,
                                bid[0].normalize(),
                                self.markets[bid[4]].mname,
                                pairn
                )



        # writes logs of everything
        def logger(self,strg):
                # just to prevent spamming the arb
                if self.last_string == strg:
                    return
                else:
                    filename = "logs/" + "arb.logs"
                    f = open(filename,'a')
                    t = "T: {0} {1} \n".format(int(time.time()), strg)
                    f.write(t)
                    f.close()
                    self.last_string = strg


        # Gets the amount we are off in each coin value
        # if we are getting this, we assume that we are
        # placing a trade, so nulls the value out on the 
        # discrep value
        def getDiscrep(self, coin = 'ltc'):
            d = self.discrep[coin]
            self.discrep[coin] = D('0')
            return d



        def setDiscrep(self):

            cur_book = self.market_balances
            initial_b = self.__initial_market_balances

            for k,v in cur_book.funds.items():
                if k == 'btc':
                    continue
                else:
                    self.discrep[k] = cur_book.funds[k] - initial_b.funds[k]



        # Just returns the difference from current balance - initial
        def coinBal(self, coin = 'btc'):
            bal = self.market_balances.getCurrency(coin) - self.__initial_market_balances.getCurrency(coin)
            return bal 

        # Returns the initial balances
        def getIBal(self, coin = 'btc'):
            return self.__initial_market_balances.getCurrency(coin)



# Here is the actual running program


# Screen loop for a thread
def screenLoop(screen, arb, makr, vana, wind):
        global var, scrd

        while var == 1:
                # This will drop our CPU usage down a bit...
                time.sleep(.1)

                c = screen.getch()




                if c != -1:

                        for x in ['0','1', '2']:
                                if c == ord(x):
                                        scrd = int(x)


                if c == ord('q'):
                        var = 0
                        return


                if c == ord('b'):
                        scrd = 'b'

                if c == ord('t'):
                        scrd = 't'

                if c == ord('y'):
                        scrd = 'y'

                if c == ord('m'):
                        scrd = 'm'

                if c == ord('o'):
                        scrd = 'o'



                lock.acquire()
                try:
                    if scrd == 'b':
                        wind.drawBalances(screen,arb)
                    elif scrd == 'm':
                        wind.drawMarket(screen,1,arb,makr)
                    elif scrd == 't':
                        wind.drawTriangle(screen,arb,0)
                    elif scrd == 'y':
                        wind.drawTriangle(screen,arb,1)
                    elif scrd == 'o':
                        wind.drawOrders(screen,makr)
                    else:
                        wind.drawScreen(screen,scrd,arb,vana)
                except:
                    logger.exception("in window")
                    pass

                finally:
                    lock.release()


# GLOBAL VARIABLES
scrd = 0
var = 1

def main(screen):

        markets = [gemini(), gdax()]



        book = Book(markets,3)

        vana = vanilla()

        wind = window()

        screen.nodelay(1)


        global var

        booktime = time.time()
        skew_time = time.time() - 570
        alive_check = time.time()
        alive_reset = time.time()

#        arb.getTrades(0)
#        arb.getTrades(1)

        book.buildBooks(0,1)
        book.buildBooks(1,1)
        book.buildBooks(2,1)



        b0 = threading.Thread(target = book.buildBooks, args = (0,))
        b0.daemon = True
        b0.start()

        b1 = threading.Thread(target = book.buildBooks, args = (1,))
        b1.daemon = True
        b1.start()

        b2 = threading.Thread(target = book.buildBooks, args = (2,))
        b2.daemon = True
        b2.start()


        t = threading.Thread(target = screenLoop, args = (screen,book,makr,vana,wind,))
        t.daemon = True
        t.start()



        base_t = threading.active_count()


        for x in book.markets:
            x.cancelAllOrder()



        while var == 1:




                        # There is a chance that actually viable crossing might
                        # be taken out by delayed retirevals of orderbooks.
                        # so we wait for that to finish, then check and 
                        # see if any crossings took place.


                        if threading.active_count() == base_t:
                            try:
                                time.sleep(1)
                                vana.checkArb(1,book)
                                vana.checkArb(0,book)
                                #vana.checkArb(2,book)
                            except:
                                logger.exception('in vana.checkarb')
                                pass

                        if book.entered_arb == 1 or book.checkHoldTrade == True or(((time.time() - booktime) > 60) and (book.arb_counter > 0)) or ((time.time() - booktime) > 600):


                                                                                    # we don't want to spam if we are in a loop
                            if (time.time() - booktime) < 15:
                               pass
                            else:

                                book.setMarketBooks()

                                # We might run into a condition where our threaded setBalance
                                # doesn't complete and update the prior, "fixed" books so we
                                # double down and repeat the last correction.
                                # We will now just update the screen until the prior
                                # threads finish, and continue with checking
                                book.sumBooks()
                                book.checkBooks()
                                # just to make sure we are no longer looping here
                                book.entered_arb=0
                                booktime = time.time()


                                # set the discrep values, our book should be updated as
                                # best as possible at this point so anything extra should
                                # be added here
                                book.setDiscrep()


                                # We need to make sure we are not somehow bleeding out money while
                                # away, so this just checks if our BTC balance has lost -.02 which is
                                # the limit to an unaccetpable amount. That is literally a huge
                                # amount at thisp point in time.

                                if book.coinBal() < D('-.01'):
                                    book.logger('exit from bal < -.01 {} '.format(book.coinBal()))
                                    var = 0

                        # Check skew every 10 minutes   
                        if skew_time + 600 < time.time():
                            prior = threading.active_count()
                            p_timeout = time.time()
                            for x in book.markets:
                               t = threading.Thread(target = book.skewStub, args = (x,))
                               t.start()

                            while (threading.active_count() > prior) and (time.time() - 60  < p_timeout):
                                time.sleep(1)

                            skew_time = time.time()



                        # check exchange health every minute
                        if time.time() - alive_check > 60:
                            for x in book.markets:
                                if x.checkHealth() is False:
                                    book.logger('{} returned bad health'.format(x.mname))
                            alive_check = time.time()


                        time.sleep(.5)

                        if time.time() - alive_reset > 1800:
                            for x in book.markets:
                                x.fixHealth()
                                time.sleep(10)

                            alive_reset = time.time()


        book.logger(book.stringFormat(0,0,0,2))
        for x in book.markets:
            x.cancelAllOrder()


if __name__ == '__main__':
        curses.wrapper(main)
