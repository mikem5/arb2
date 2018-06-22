import decimal
import requests
import urllib.request, urllib.parse, urllib.error
import json
import hashlib
import hmac

import time
import calendar
import datetime

import logging
logger = logging.getLogger(__name__)


hdlr = logging.FileHandler('logs/logger.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s',datefmt='%s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.WARNING)



from Pair import *
from Market import *

from config import *

class poloniex(Market):

        # names of the pairs for our market we only look at
        # crypto pairs, no usd pairs    

        def __init__(self):

                self.mname = "poloniex"



                self.api_key = 
                self.api_key_secret = 
                
                self.trade_url = "https://poloniex.com/tradingApi"


                self.trade_var = "buy"


                self.trade_hist_url = "https://poloniex.com/public?command=returnTradeHistory&currencyPair="



                self.trade_lag = 1
    
                self.xnames = ["BTC_LTC", "USDT_BTC","USDT_LTC"]

                self.xurl = ["http://poloniex.com/public?command=returnOrderBook&depth=25&currencyPair=", ""]
                
                self.xrange = 20

                self.xfee = 1.0025# This is actually a maker/taker market....

                
                self.xthrp = .5 # 1 or less seconds throttle per pair



                self.maker_fee = D('1.0015')
                
                # again, fairly sure this is .0001 btc value as min
                self.min_trade_quantity = D('.1')
                # to 8 places
                self.price_increment = dq
                self.quantity_increment = dq

                usd = [D('.0000001'),D('.0000001'), D('.0000001')]
                lsd = [D('.0000001'), D('.0000001'), D('.0000001')]
 
                ltc = [D('.1'), dq, dq]

                super(poloniex,self).__init__(self.xnames, self.xurl, self.xrange, self.xfee, self.xthrp, mtq = [ltc, usd,lsd])


        









        # the params come from individual functions which parse the 
        # params into a dict which then sends to the postPage method
        # which calls this to get the actual encoded headers
        def formatPost(self, type, params):
                params['command'] = type
                
                # This gives a very fine nonce value
                params['nonce'] = str(self.getNonce())

                encode_param = urllib.parse.urlencode(params)

                h = hmac.new(self.api_key_secret.encode('utf-8'), digestmod=hashlib.sha512)
                h.update(encode_param.encode('utf-8'))
                sign = h.hexdigest()
                head = {
                                "Sign": sign, "Key": self.api_key}



                return self.trade_url, params, head


        # Trade api filler
        # can be modified later to fit Pair.asks and all that
        # can be gleaned from using our objects

        # poloniex has two seperate orders for either ask or buy

        def formatTrade(self, options):


                if options['side'] == "ask":
                        self.trade_var = "sell"
                else:
                        self.trade_var = "buy"



                # if our pair is inverted we need to get the actual values
                if self.pairs[options['loc']].inverted == 1:
                    inv  = self.revertBase(options['price'], options['quantity'])
                    price = inv[0].quantize(df)
                    quantity = inv[1] / D('1.001') # fee adjust to fix not enough usd problem
                    if options['side'] == "ask":
                            self.trade_var = "buy"
                    else:
                            self.trade_var = "sell"
                else:
                    price = options['price'].quantize(dq)
                    quantity = options['quantity']







                params = { 
                        "currencyPair": self.pairs[options['loc']].name,  # eg, ltc_btc
                        "rate": str(price),        #  numerical. the actual price
                        "amount": str(quantity.quantize(dq)) # numerical quantity
                }

                if 'post_only' in options:
                    params['postOnly'] = 1

                if 'ioc' in options:
                    params['immediateOrCancel'] = 1

                if 'fok' in options:
                    params['fillOrKill'] = 1



                return params


        def parseTradeResponse(self,loc, response):
                self.last_quantity_traded = D('-1')


                # There is a "spinning wheel" problem with the api
                # so, we should try to check for our orders if we got
                # a "timeout" error, see if something was up, or
                # something was traded.
                if response == 0:
                    data = []
                    
                
                else:
                    try:
                        pair = self.pairs[loc].name
                        data = json.loads(response)
                    except (KeyError, TypeError, ValueError):
                        logger.exception("in parseTrade, loading json")
                        return -1, 0
        
                # So the trade didn't go through more than likely
                if "error" in data:
                        return -1, 0

                # We get the order id then cancel the order in case
                # anything remains.
                # This happens to be failing with a certain amount
                # of consistency. It is probable that the api is
                # not giving us back an orderNumber?
                try:
                        orderid = D(str(data['orderNumber']))
                
                except:
                        # It could be the case that we DO have an
                        # order and it needs to be canceled, or that
                        # the order went through and we should return
                        # a quantity.
                        logger.exception("no ordernumber?")
                        self.cancelAllOrder()                   
                        return -1, 0

                 


                q = D('0')
                # This is confusing and may need to be looked at
                # specifically is amount what traded or is total
                # what traded?
                for x in data['resultingTrades']:
                        if self.pairs[loc].inverted == 1:
                            tmp = self.invertBase(D(str(x['rate'])), D(str(x['amount'])))
                            q += D(tmp[1])
                        else:
                            q += D(str(x['amount']))

                self.last_quantity_traded = D(q)
                return q, orderid



        def cancelOrder(self, orderid, loc):
                pair = self.xnames[loc]
                params = {
                        'currencyPair' : pair,
                        'orderNumber': orderid
                        }
                return self.postPage('cancelOrder', params)


        def cancelAllOrder(self):
                self.open_order_mm.nullOrders() 
                try:
                        page = self.postPage('returnOpenOrders',params = {'currencyPair':'all'})
                        data = json.loads(page)
                        for k,v in data.items():
                            for loc,name in enumerate(self.xnames):
                                if k == name: 
                                        for x in v:
                                                if x:
                                                        orderid = x['orderNumber']
                                                        self.cancelOrder(orderid,loc)
                except (ValueError, TypeError,requests.ConnectionError, requests.Timeout, requests.HTTPError, requests.RequestException):
                        logger.exception("in poloniex in cancelAllorder")
                        return False

                return True



        def tradeHist(self, timestamp = 0, cPair = 'all'):
                try:
                        if timestamp == 0:
                            param = {'currencyPair' :cPair}
                        else:
                            param = {'currencyPair' :cPair, 'start': str(int(timestamp))}
                       
                        page = self.postPage('returnTradeHistory',params = param)
                        data = json.loads(page)
                        return data
                except (ValueError, TypeError,requests.ConnectionError, requests.Timeout, requests.HTTPError, requests.RequestException):
                        logger.exception("in poloniex in tradeHistory()")
                        return False


   
        def tradesOrder(self, orderid):
                try:
                        page = self.postPage('returnOrderTrades',params = {'orderNumber':orderid})
                        data = json.loads(page)
                        return data
                except (ValueError, TypeError,requests.ConnectionError, requests.Timeout, requests.HTTPError, requests.RequestException):
                        logger.exception("in poloniex in openOrders()")
                        return False





        def openOrders(self, orderid, cPair = 'all'):
                try:
                        page = self.postPage('returnOpenOrders',params = {'currencyPair':cPair})
                        data = json.loads(page)
                        return data
                except (ValueError, TypeError,requests.ConnectionError, requests.Timeout, requests.HTTPError, requests.RequestException):
                        logger.exception("in poloniex in openOrders()")
                        return False



        def getPendAmount(self, orderid, loc = 0):
            try:
                pending = D('-1')

                resp = self.openOrders(orderid)
                if resp != False:
                    for k,v in resp.items():
                                if k in self.xnames:
                                        for x in v:
                                                if x['orderNumber'] == orderid:
                                                    if self.pairs[loc].inverted == 1:
                                                        tmp = self.invertBase(D(str(x['rate'])), D(str(x['amount'])))
                                                        pending = tmp[1]
                                                    else: 
                                                        pending = D(str(x['amount']))

                return pending
                                
            except (AttributeError, ValueError, TypeError,requests.ConnectionError, requests.Timeout, requests.HTTPError, requests.RequestException):
                        logger.exception("in poloniex in getpendorder")
                        return D('-1')




        def getTradeAmount(self, orderid, loc = 0):
            try:
                traded = D('0')

                resp = self.tradesOrder(orderid)

                if resp != False:
                    if resp:
                        try:
                            if resp['error']:
                                return traded
                        except (KeyError, TypeError):
                            pass

                        for x in resp:
                            if self.pairs[loc].inverted == 1:
                                tmp = self.invertBase(D(str(x['rate'])), D(str(x['amount'])))
                                traded += tmp[1]
                            else: 

                                traded = traded + D(str(x['amount']))


                return traded
                                
            except (AttributeError, ValueError, TypeError,requests.ConnectionError, requests.Timeout, requests.HTTPError, requests.RequestException):
                        logger.exception("in poloniex in gettradeamount")
                        return D('-1')





        # info on account
        def postInfo(self):
                page = self.postPage("returnCompleteBalances")
                data = json.loads(page)
                bal = {}
                for k,v in data.items():
                    sum = D(str(v['available'])) + D(str(v['onOrders']))
                    if k == 'USDT':
                        bal['USD'] = sum
                    else:
                        bal[k] = sum
                return bal



        def getOrderId(self, data):
            try:
                return data['orderNumber']
            except:
                return False

        # takes a pair name, returns a balances formatted key
        # eg takes ltcbtc and returns 'ltc'
        def pairKey(self, p):
            val = p.split('_')
            if val[0] == 'USDT':
                key = 'usd'
            else:
                key = val[1].lower()
            return key
