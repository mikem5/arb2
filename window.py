import decimal
import time
import datetime
import curses
import copy
import statistics
import curses
from config import *

class window(object):


        def __init__(self):

            self.screen_update = 0
            self.__started = time.time()


        # This draws the default curses screen
        # we need the "screen" object, and the arb object,
        # as well as the loc that we are using.


        def drawScreen(self,screen,loc, arb, vanilla):

                global perf_list                
#                perf_start = time.perf_counter()

                pid = arb.pairs[loc]

                ds = D('.000001')

                if time.time() - self.screen_update > .016:

                        screen.erase()
                        # Always print the last arb event at top
                        screen.addstr(0,0, arb.last_arb)


                        # Columsn and formatting begind at line 5

                        # Ask column
                        screen.addstr(2,1,"Asks")
                        screen.addstr(2,13,"Quantity")
                        screen.addstr(2,25,"Market")
                        screen.addstr(2,34,"active")
                        screen.addstr(3,1,"---")
                        screen.addstr(3,13,"---")
                        screen.addstr(3,25,"---")
                        screen.addstr(3,34,"---")
                        for i,v in enumerate(pid.asks[:8]):

                                screen.addstr(4+i,1,str(v[0].quantize(ds)))
                                screen.addstr(4+i,13,str(v[1].quantize(ds)))
                                screen.addstr(4+i,25,arb.markets[v[4]].mname)

                                upd = D(time.time() - v[5]).quantize(D('.1'))
                                if upd > D(100):
                                     screen.addstr(4+i,34,"100+")
                                else:   
                                    screen.addstr(4+i,34,str(upd))
                                
                        off = 44
                        screen.addstr(2,1+off,"Bids")
                        screen.addstr(2,13+off,"Quantity")
                        screen.addstr(2,25+off,"Market")
                        screen.addstr(2,34+off,"active")
                        screen.addstr(3,1+off,"---")
                        screen.addstr(3,13+off,"---")
                        screen.addstr(3,25+off,"---")
                        screen.addstr(3,34+off,"---")
                        for i,v in enumerate(pid.bids[:8]):

                                screen.addstr(4+i,1+off,str(v[0].quantize(ds)))
                                screen.addstr(4+i,13+off,str(v[1].quantize(ds)))
                                screen.addstr(4+i,25+off,arb.markets[v[4]].mname)
                                
                                upd = D(time.time() - v[5]).quantize(D('.1'))
                                if upd > D(100):
                                     screen.addstr(4+i,34+off,"100+")
                                else:
                                    screen.addstr(4+i,34+off,str(upd))
                
                        # Draw the balances of this market
                        screen.addstr(13,1,"btc")
                        screen.addstr(13,13,arb.currencies[loc])
                        screen.addstr(13,25,"market")
                        screen.addstr(13,34,"trades")
                        screen.addstr(13,44,"skew_o")
                        screen.addstr(13,53,"skew_c")
                        screen.addstr(13,62,"update")
                        screen.addstr(13,71,"hold")

                        for i,v in enumerate(arb.markets):
                                btc = arb.markets[i].balances.getCurrency('btc')
                                if arb.currencies[loc] == 'lsd':
                                    coin = arb.markets[i].balances.getCurrency('usd')
                                else:
                                    coin = arb.markets[i].balances.getCurrency(arb.currencies[loc])
                                m = arb.markets[i]
                                screen.addstr(14+i,1,str(btc.quantize(ds)))
                                screen.addstr(14+i,13,str(coin.quantize(ds)))
                                screen.addstr(14+i,25,m.mname)
                                screen.addstr(14+i,34,str(m.totaltrades))
                                screen.addstr(14+i,44,str(D(m.skew_order).quantize(D('.001'))))
                                screen.addstr(14+i,53,str(D(m.skew_cancel).quantize(D('.001'))))
               
                                if m.pairs[loc] == 0:
                                        upd = 0
                                else:
                                        upd = time.time() - m.pairs[loc].updated
                                        upd = D(upd)
                                        upd = upd.quantize(D('.01'))

                                screen.addstr(14+i,62,str(upd))

                                if m.hold_trade == 1:
                                    screen.addstr(14+i,71,"*")





                        # We now generate the spread difference
                        spread = pid.bids[0][0] - pid.asks[0][0]
                        pspread,  psq= vanilla.calcProfit(pid.asks[0], pid.bids[0], loc,arb)

                        x = 3
                        screen.addstr(19+x,1,"Thread count : " + str(threading.active_count()))
                        screen.addstr(20+x,1,"Current spread : " + str(spread.normalize()))
                        screen.addstr(21+x,1,"Profit Spread  : " + str(pspread.normalize()))
                        screen.addstr(22+x,1,"Thr. Profit : " + str(arb.tprofit.normalize()))
                        screen.addstr(23+x,1,"Act. Profit : " + str(arb.coinBal().normalize()))

                        # this will let us see how much is really there if we flattened our
                        # positions out
                        if arb.currencies[loc] == 'lsd':
                            ltc_size = arb.coinBal('usd')
                        else:
                            ltc_size = arb.coinBal(arb.currencies[loc])
                        if ltc_size < D('0'):
                                # sell ltc to get btc
                                pflat = arb.coinBal() + (ltc_size * pid.bids[0][0])
                        else:
                                pflat = arb.coinBal() - (ltc_size * pid.bids[0][0])

                        screen.addstr(24+x,1,"Flat Profit : " + str(pflat.quantize(D('.00000001'))))

                        screen.addstr(25+x,1,"Trade Volume : " + str(arb.ttrades[loc].normalize()))
                        running = time.time() - self.__started
                        running = int(running)
                        screen.addstr(26+x,1,"Running : " + str(datetime.timedelta(seconds=running)))

                        #perf_end = time.perf_counter()

                        # section takes around .00067

                        #perf_list.append(perf_end - perf_start)



                        # tracks performance

                        if len(perf_list) > 501:
                            del perf_list[:-500]

                        screen.addstr(28+x,1,"perfsize: " + str(len(perf_list)))
                        screen.addstr(29+x,1,"perf max: " + str(max(perf_list)   ))
                        screen.addstr(30+x,1,"perf min: " + str(min(perf_list)   ))
                        screen.addstr(31+x,1,"perf med: " + str(statistics.median(perf_list)   ))







                        screen.refresh()

                        self.screen_update = time.time()






        # Draw the balances of this market
        def drawBalances(self,screen, arb):

                ds = D('.00001')

                if time.time() - self.screen_update > .016:

                        screen.erase()

                        off = 0

                        screen.addstr(1,1,"btc")
                        for l in arb.currencies:
                                screen.addstr(1,12+off,l)
                                off +=12
                        screen.addstr(1,12+off,"market")
                        screen.addstr(1,24+off,"trades")


                        off = 0
                        end = 0
                        for i,v in enumerate(arb.markets):
                                end = i
                                btc = arb.markets[i].balances.getCurrency('btc')
                                screen.addstr(2+i,1,str(btc.quantize(ds)))
                                for l in arb.currencies:
                                    if l == 'lsd':
                                        pass
                                    else:
                                        coin = arb.markets[i].balances.getCurrency(l)
                                        m = arb.markets[i]
                                        screen.addstr(2+i,12+off,str(coin.quantize(ds)))
                                        off += 12
                                screen.addstr(2+i,12+off,m.mname)
                                screen.addstr(2+i,24+off,str(m.totaltrades))
                                off = 0

                        off = 0

                        # have to fix this part
                        screen.addstr(4+end,1,str(arb.getIBal().quantize(ds)))
                        for l in arb.currencies:
                            if l =='lsd':
                                pass
                            else:
                                coin = arb.getIBal(coin = l)
                                screen.addstr(4+end,12+off,str(coin.quantize(ds)))
                                off += 12
                        screen.addstr(4+end,12+off,"initial balance")

                        cur_bal = arb.market_balances

                        off = 0
                        screen.addstr(5+end,1,str(cur_bal.getCurrency('btc').quantize(ds)))
                        for l in arb.currencies:
                            if l =='lsd':
                                pass
                            else:
                                coin = cur_bal.getCurrency(l)
                                screen.addstr(5+end,12+off,str(coin.quantize(ds)))
                                off += 12
                        screen.addstr(5+end,12+off,"current balance")


                        off = 0
                        btcbal = arb.coinBal()
                        screen.addstr(7+end,1,str(btcbal.quantize(ds)))
                        for l in arb.currencies:
                            if l == 'lsd':
                                pass
                            else:

                                bals = arb.coinBal(coin = l)
                                screen.addstr(7+end,12+off,str(bals.quantize(ds)))
                                off += 12
                        screen.addstr(7+end, 12+off,"difference")







                        screen.refresh()

                        self.screen_update = time.time()




        # This draws a screen which shows the spread, profit spread, and highest
        # order from all markets in a given currency. This is useful to keep
        # track of which markets can be "made" by placing orders.

        def drawMarket(self, screen, loc, arb, makr):
                
                pid = arb.pairs[loc]
        
                ds = D('.000001')

                if time.time() - self.screen_update < .16:
                        return


                screen.clear()


                # We go through the pairs best order book and pick out and display
                # the best orders, then follow suit on the rest of the markets

                # market id is pid[0][4]

                bestAsk = pid.asks[0]
                bestBid = pid.bids[0]

                tab = 30
                screen.addstr(1,1,"Asks")
                screen.addstr(1,1+tab,"Bids")
                screen.addstr(2,1,"-----")
                screen.addstr(2,1+tab,"-----")

                # This is slightly confusing, but what is happening is we are
                # comparing if we sell at the top price on a market, then we
                # actually 'hit' the best price on another market.
                # so we DID place an ask offer, 'curA' and then need to
                # execute agasint the 'bestA' order.


                # For the ask side
                screen.addstr(4,1,"Best Market: " + arb.markets[bestAsk[4]].mname)
                screen.addstr(5,1,"Price: " + str(bestAsk[0].quantize(ds)))

                # Bid side
                screen.addstr(4,1+tab,"Best Market: " + arb.markets[bestBid[4]].mname)
                screen.addstr(5,1+tab,"Price: " + str(bestBid[0].quantize(ds)))


                off = 0

                for idx,m in enumerate(arb.markets):
                    
                    # get best from market
                    curA, curB = m.bestPrice(loc)
                    curA = [curA[0], curA[1], curA[2], 0, idx, time.time()]
                    curB = [curB[0], curB[1], curB[2], 0, idx, time.time()]


                    # SIDES: ASK == 0, BIDS == 1
                    for side in [[bestAsk,curA,0],[bestBid,curB,1]]:
                        
                        p = 0                
                        q = 0

                        # ie if our market is the same as the BEST, skip
                        if idx == side[0][4]:
                            continue

                        elif m.pairs[loc] == 0:
                            continue

                        else:

                            # we want to make a deepcopy of this order so
                            # that we can increment the price and not
                            # impact our orderbook.
                            cur = copy.deepcopy(side[1])

                            # just look at the top order in this market



                            if side[2] == 0:
                                base = copy.deepcopy(m.pairs[loc].qBask())
                                
                                # in an inverted pair we simply look at the base[3]
                                # which is the non inverted value
                                if m.pairs[loc].inverted == 1:
                                    base[4] += (df)
                                    base[4] = base[4].quantize(df)
                                    inv = m.invertBase(base[4], base[5])
                                    base[0] = inv[0]
                                    


                                # now increment our price by the lowest allowed value,
                                # OR decrease depending on what we need to do
                                else: 
                                    base[0] -= (m.pairs[loc].price_increment() + m.compete_price[loc])

                                base[0] = base[0].quantize(dq)

                                # NOTE: Fee's are switched! Ask/Bid are different when placing the order
                                # this must be taken into account
                                withFee = [(base[0] / m.maker_fee), base[1], base[2]]
                                #withFee = m.BidFeePrice(base)
                            else:
                                base = copy.deepcopy(m.pairs[loc].qBbid())

                                # in an inverted pair we simply look at the base[3]
                                # which is the non inverted value
                                if m.pairs[loc].inverted == 1:
                                    base[4] -= (df)
                                    base[4] = base[4].quantize(df)
                                    inv = m.invertBase(base[4], base[5])
                                    base[0] = inv[0]
     

                                else:
                                    base[0] += (m.pairs[loc].price_increment() + m.compete_price[loc])
                                base[0] = base[0].quantize(dq)
                                withFee = [(base[0] / m.maker_fee), base[1], base[2]]
 
                                #withFee = m.AskFeePrice(base)



                            # copy the fee price, and quantity into our "cur"
                            cur = [withFee[0], withFee[1], withFee[2], cur[3], cur[4], cur[5]]

                            # calculate profit to see if there is any
                            # side[0] is bestAsk, cur is best pid.ask order , eg the full order
                            p, q = makr.calcProfit(arb, loc, side[0], cur, ab = side[2])


                            if side[2] == 0:
                                
                                screen.addstr(8+idx+off,1,"Market: " + arb.markets[idx].mname)
                                screen.addstr(9+idx+off,1,"Price: " + str(cur[0].quantize(ds)))
                                screen.addstr(10+idx+off,1,"Spread: " + str(abs(bestAsk[0] - cur[0]).quantize(ds)))
                                screen.addstr(11+idx+off,1,"Profit: " + str(p.quantize(dq)))
                            
                            else:

                                screen.addstr(8+idx+off,1+tab,"Market: " + arb.markets[idx].mname)
                                screen.addstr(9+idx+off,1+tab,"Price: " + str(cur[0].quantize(ds)))
                                screen.addstr(10+idx+off,1+tab,"Spread: " + str(abs(bestBid[0] - cur[0]).quantize(ds)))
                                screen.addstr(11+idx+off,1+tab,"Profit: " + str(p.quantize(dq)))

                    off += 4





                screen.refresh()

                self.screen_update = time.time()


        # This will display all active orders we have out there (at least in our maker object)
        # mostly for debugging
        def drawOrders(self, screen, maker):
       
                ds = D('.000001')

                if time.time() - self.screen_update < .16:
                        return


                screen.clear()

                # if it is empty
                if maker.order_list == []:
                    t = "order list empty"
                    screen.addstr(1,1,t)

                else:
                    for i,x in enumerate(maker.order_list):
                        t = "orderid: {0} \tmarket: {1}\tloc: {2}\tside: {3}\tprice: {4}\tquantity: {5}".format(x[0], x[1], x[2], x[3], x[4], x[5]) 
                        screen.addstr(1+i,1,t)

                screen.refresh()
                self.screen_update = time.time()                
               



        def drawTradeHistory(self, screen, loc, arb):
                
        
                ds = D('.00001')

                if time.time() - self.screen_update < 1:
                        return


                screen.clear()



                x = 0
                start_y = 0
                for idx,val in enumerate(arb.markets):
                            y = start_y

                            screen.addstr(y, x, arb.markets[idx].mname)

                            tmpv = val.trades[loc].getVWAP()
                            try:
                                vwap = "vwap: " + str(tmpv[0].quantize(ds))
                                screen.addstr(y, x+10, vwap)
                            except:
                                pass
                            y+=1

                            screen.addstr(y, x+0 , "price")
                            screen.addstr(y, x+10 , "amount")
                            screen.addstr(y, x+20, "time ago")
                            screen.addstr(y, x+30, "type")

                            # slice the last 5 trades of the flat array
                            trades = val.trades[loc].flat[:5]

                            y+=1
                            if trades != []:
                                for i in range(len(trades)):

                                    screen.addstr(y, x+0 , str(trades[i][0].quantize(ds))) # price
                                    screen.addstr(y, x+10 , str(trades[i][1].quantize(ds))) # quantity
                                    
                                    timestamp = time.time() - trades[i][3]
                                    
                                    screen.addstr(y, x+20, str(int(timestamp))) # time diff
                                    
                                    screen.addstr(y, x+30, str(trades[i][4])) # buy/ask
                                    y+=1
                            
                            x+=36


                            if x > 100:
                                x = 0
                                start_y += 9

                screen.refresh()

                self.screen_update = time.time()




        def drawTriangle(self, screen, arb, side):
            if time.time() - self.screen_update < 1:
                    return

            screen.clear()


            scrx = 0
            scry = 0

            # do btc -> usd, usd -> ltc, ltc -> btc
            # direction
            #
            btcusd = []
            ltcusd = []
            ltcbtc = []
            for idx,mkt in enumerate(arb.markets):
               
                if side == 0:

                    # get best this market
                    btcusd.append(mkt.pairs[1].asks[0])
                    if mkt.pairs[0] == 0:
                        ltcusd.append(0)
                        ltcbtc.append(0)
                    else:
                        ltcusd.append(mkt.pairs[2].asks[0])
                        ltcbtc.append(mkt.pairs[0].bids[0])

                else:
                    btcusd.append(mkt.pairs[1].bids[0])
                    if mkt.pairs[0] == 0:
                        ltcusd.append(0)
                        ltcbtc.append(0)
                    else:
                        ltcusd.append(mkt.pairs[2].bids[0])
                        ltcbtc.append(mkt.pairs[0].asks[0])


            outtri =[]
            for i,x in enumerate(btcusd):
                
                screen.addstr(scry,scrx,arb.markets[i].mname)
                ly = 0
                for j,y in enumerate(ltcusd):
                
                    if y != 0:
                        screen.addstr(scry+ly, scrx+ 10, arb.markets[j].mname)
                        hint = 0 
                        for h,z in enumerate(ltcbtc):
                            if z != 0:
                                screen.addstr(scry + ly+ hint, scrx+20, arb.markets[h].mname)

                                if side == 0:

                                    minusd = min(x[1], y[1] * y[2])
                                    minltc = min(minusd / y[2], z[1])
                                    q = minltc * y[2]
                                         
                                    btc = (x[2] * q) 
                                    ltc = q / y[2]
                                    btco = ltc * z[2]
                                    result = btco - btc

                                else:
                                    minbtc = min(x[1] * x[2], z[1] * z[2])
                                    minltc = min(minbtc / z[2], y[1])
                                    q = minltc * z[2]
                                        
                                    usd = q / x[2]  
                                    ltc = q / z[2]
                                    btco = ltc * y[2]
                                    result = btco - usd
                                    if result > 0:
                                        # this is not accurate and the trade quantity
                                        # should be adjusted at initially to account
                                        # for extra fee's being incurred
                                        result = result * x[0]
                                if result > 0:
                                    screen.addstr(scry+ly+hint, scrx+30, str(result.quantize(D('.000001'))),curses.A_BOLD)
                                else:
                                    screen.addstr(scry+ly+hint, scrx+30, str(result.quantize(D('.000001'))),curses.A_DIM)
                         
                                hint+=1

                        ly+=6

                scry += 25
                if scry > 25:
                    scrx +=50
                    scry = 0











            screen.refresh()

            self.screen_update = time.time()

      
