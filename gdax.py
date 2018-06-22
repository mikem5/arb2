import decimal
import requests
import urllib.request, urllib.parse, urllib.error
import json
import hashlib
import hmac
import base64


import time
import calendar
import datetime

import logging
logger = logging.getLogger(__name__)


hdlr = logging.FileHandler('logs/logger.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s',datefmt = '%s')

hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.WARNING)



from Pair import *
from Market import *

from config import *

class gdax(Market):

        # names of the pairs for our market we only look at
        # crypto pairs, no usd pairs    

        def __init__(self):

                self.mname = "gdax"


                self.api_key = 
                self.api_passphrase = 
                self.api_key_secret = 

                self.trade_url = "https://api.gdax.com/"


                self.trade_var = "orders"

                # not live api
                self.trade_hist_url = "https://api-public.sandbox.gdax.com/products/",



                self.trade_lag = 1

                # for gdax pagination
                self.trade_page = 0
                self.last_page = 0




                # normally is BTC-LTC, just using for testing 
                self.xnames = ["LTC-BTC", "BTC-USD","LTC-USD" ]

                self.xurl = ["https://api.gdax.com/products/", "/book?level=2"]
                
                self.xrange = 50

                self.xfee = 1.0025 # This is actually a maker/taker market....

                self.xthrp = 5 # 5 or less seconds throttle per pair



                self.maker_fee = D('1.0000')



                # again, fairly sure this is .0001 btc value as min
                # because this is inverted, the amount of USD is 1/btc which is
                # actually .01 btc. assuming btc doesnt go higher than 1000 anytime
                # soon 10 usd quanttiy is fair
                self.min_trade_quantity = D('7.5')
                # to 8 places
                self.price_increment = D('.01')
                self.quantity_increment = D('1')

                musd = [D('.01'), D('.01'), D('.01')]
                ltc = [D('.01'), D('.00001'), D('.00001')]
                lsd = [D('.01'), D('.01'), D('.01')]


                super(gdax,self).__init__(self.xnames, self.xurl, self.xrange, self.xfee, self.xthrp, mtq = [ltc, musd,lsd])





        
        def getPage(self, pairid, url = 0, typ = 0, params = 0):

                session = requests.Session()
                if url == 0:
                    page = session.get(self.defURL[0] + pairid.name + self.defURL[1],timeout=5, verify=False)
                else:
                    # if type != 0 we have an authenticated GET
                    if typ ==0:
                        page = session.get(url, timeout = 5, verify = False)
                    else:
                        url, para, head = self.formatPost(url, params, method = 'GET')
                        page = session.get(url, headers = head, data = para,timeout =10, verify = False)
                        self.postlog(url, typ, para, page)
                session.close()


                return page.text




        def deletePage(self, typ, params ={}):
                resp = 0
                url = 0
                para = 0
                try:
                        session = requests.Session()
                        url, para, head = self.formatPost(typ, params,method='DELETE')
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














        # the params come from individual functions which parse the 
        # params into a dict which then sends to the postPage method
        # which calls this to get the actual encoded headers
        def formatPost(self, typ, params = 0, method = 'POST'):

                

                # GET/POST/DELETE
                # are method types 

                timestamp = str(time.time())

                if params != 0:
                    encode_param = json.dumps(params)
                else:
                    encode_param = ''
                    params = {}

                # params needs to be the 

                message = timestamp + method + '/'+ typ + encode_param
                hmac_key = base64.b64decode(self.api_key_secret)
                signature = hmac.new(hmac_key, message.encode('utf8'), hashlib.sha256)
                signature_b64 = base64.b64encode(signature.digest())
                head = {
                                "CB-ACCESS-SIGN": signature_b64, 
                                "CB-ACCESS-KEY": self.api_key,
                                "CB-ACCESS-TIMESTAMP": timestamp,
                                "CB-ACCESS-PASSPHRASE": self.api_passphrase,
                                'Content-Type': 'application/json',
                                'Accept': 'application/json'
                        }


                url = self.trade_url + typ

                return url, encode_param, head


        # Trade api filler
        # can be modified later to fit Pair.asks and all that
        # can be gleaned from using our objects


        def formatTrade(self, options):


                if options['side'] == "ask":
                        bysl = "sell"
                else:
                        bysl = "buy"



                if self.pairs[options['loc']].inverted == 1:
                    invs = self.revertBase(options['price'], options['quantity'])
                    price = invs[0].quantize(df)
                    quantity = invs[1]

                    if bysl == "buy":
                            bysl = "sell"
                    else:
                            bysl = "buy"

                else:
                    price = options['price'].quantize(dq)
                    quantity = options['quantity']

                params = { 
                        "product_id": self.pairs[options['loc']].name,    # eg, ltc_btc
                        "type": "limit",
                        "side": bysl,
                        "price": str(price),       #  numerical. the actual price
                        "size": str(quantity.quantize(self.pairs[options['loc']].quantity_increment())) # numerical quantity
                        }

                if 'post_only' in options:
                    params['post_only'] = True

                if 'ioc' in options:
                    params['time_in_force'] = 'IOC'

                if 'fok' in options:
                    params['time_in_force'] = 'FOK'


                return params


        def parseTradeResponse(self,loc, response):
                self.last_quantity_traded = D('-1')
                orderid = 0

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
                        orderid = str(data['id'])
                        end_cond = 0
                
                except:
                        # It could be the case that we DO have an
                        # order and it needs to be canceled, or that
                        # the order went through and we should return
                        # a quantity.
                        logger.exception("no ordernumber?")
                        self.cancelAllOrder()                   
                        end_cond = 1    


                # We now get the quantity traded to return it
                if orderid != 0:
                    time.sleep(.5)
                    traded = self.getTradeAmount(orderid,loc)
                else:
                    traded = D("-1")
                
                
                # In this case we had an exception so we need to find our order number,
                # It is more than likely the first order as we should be locked
                # in place here.
                if end_cond == 1:
                        self.hold_trade = 1
                        return -1, 0



                # This is confusing and may need to be looked at
                # specifically is amount what traded or is total
                # what traded?
                if traded != D("-1"):
                    q = traded
                else:
                    self.cancelAllOrder()

                self.last_quantity_traded = traded
                return q, orderid





        # delete order section
        #
        # works with deletePage call
        #
        def cancelOrder(self, orderid,loc):
                params = {}
                return self.deletePage('orders/'+str(orderid), params)


        def cancelAllOrder(self):
                self.open_order_mm.nullOrders() 

                try:
                    self.deletePage('orders',params = {})
                except (ValueError, TypeError,requests.ConnectionError, requests.Timeout, requests.HTTPError, requests.RequestException):
                        logger.exception("in gdax in cancelAllorder")
                        return False

                return True



    
        #
        # Order status section
        #
        #

        def openOrders(self, orderid):
                try:
                        
                        page = self.getPage(0, 'orders/'+str(orderid), typ = 1)
                        data = json.loads(page)
                        return data
                except (ValueError, TypeError,requests.ConnectionError, requests.Timeout, requests.HTTPError, requests.RequestException):
                        logger.exception("in gdax in openOrders()")
                        return False



        def getPendAmount(self, orderid, loc = 0):
            try:
                pending = D('-1')

                resp = self.openOrders(orderid)
                if resp != False:
                    if resp['status'] != 'done':
                        if self.pairs[loc].inverted == 1:

                            p_t = D(str(resp['size'])) - D(str(resp['filled_size']))


                            tmp = self.invertBase(D(str(resp['price'])), p_t)
                            pending = tmp[1]

                        else:

                            pending = D(str(resp['size'])) - D(str(resp['filled_size']))

                return pending
                                
            except (KeyError, AttributeError, ValueError, TypeError,requests.ConnectionError, requests.Timeout, requests.HTTPError, requests.RequestException):
                        logger.exception("in gdax in getpendorder")
                        return D('-1')



        def getFills(self, orderid, loc = 0):
                try:
                        
                        page = self.getPage(0, 'fills?order_id='+str(orderid), typ = 1)
                        data = json.loads(page)
                        return data
                except (ValueError, TypeError,requests.ConnectionError, requests.Timeout, requests.HTTPError, requests.RequestException):
                        logger.exception("in gdax in openOrders()")
                        return False



        # Get websocket api trades.
        # these are stored as "mname:trade:orderid  -> 'size size size' "
        def getTradeAmount(self, orderid, loc = 0):
            r_server = redis.Redis(connection_pool=r_pool, charset="utf-9", decode_responses=True)
            r_pipe = r_server.pipeline()

            traded = D('0')


            try:    

                resp = r_server.get(":".join([self.mname,'trade',str(orderid)]))
                
                # They key will be None if not there
                if resp != None:
                    size = resp.split()
                    for x in size:
                        y = x.split(":")
                        price = y[0]
                        size = y[1]
                        if self.pairs[loc].inverted == 1:
                            tmp = self.invertBase(D(price), D(size))
                            traded += tmp[1]
                 
                        else:

                            traded += D(size)

                return traded
            except (KeyError, AttributeError, ValueError, TypeError,requests.ConnectionError, requests.Timeout, requests.HTTPError, requests.RequestException):
                logger.exception("in gdax in gettradeamount")
                return D('-1')



        def getTradeAmountolld(self, orderid, loc = 0):
            try:
                traded = D('-1')


                rsp = self.openOrders(orderid)
                x = rsp

                if rsp != False:
                        try:
                            # we assume this means cancelled order with no trade
                            if rsp['message'] == 'NotFound':
                                return D('0')

                            # so this is a trade, we need to get fills here
                            if rsp['message'] == 'Order already done':
                                fills = self.getFills(orderid,loc)
                                x = {}
                                x['side'] = 'sell'
                                x['price'] = D('0')
                                x['size'] = D('0')
                                x['fill_fees'] = D('0')
                                x['status'] = 'done'
                                for y in fills:
                                    x['side'] = y['side']
                                    x['price'] = D(str(y['price']))
                                    x['size'] += D(str(y['size']))
                                    x['fill_fees'] += D(str(y['fee']))

                        except KeyError:
                            pass



                        if x['status'] == 'done':
                            if self.pairs[loc].inverted == 1:
                                # Add in the fee
                                if x['side'] == 'sell': # this will be a usd reduction
                                    tmp = self.invertBase(D(str(x['price'])), D(str(x['size'])))
                                    traded += tmp[1] - D(x['fill_fees'])
                                else: # this is in terms of btc
                                    tmp = self.invertBase(D(str(x['price'])) - D(str(x['fill_fees'])), D(str(x['size'])))
                                    traded += tmp[1] 
                               

                            else:
                                traded += D(str(x['size']))

                return traded
            except (KeyError, AttributeError, ValueError, TypeError,requests.ConnectionError, requests.Timeout, requests.HTTPError, requests.RequestException):
                        logger.exception("in gdax in gettradeamount")
                        return D('-1')





        # info on account
        def postInfo(self):
                bal = {}
                try: 
                    page = self.getPage(0, "accounts", typ = 1)
                    data = json.loads(page)
                    for k in data:
                            bal[k['currency'].lower()] = D(str(k['balance']))

                except:
                    logger.exception("in gdax post info")
                    bal = {'none':0}

                return bal



        def getOrderId(self, data):
            try:
                return data['id']
            except:
                return False

        # takes a pair name, returns a balances formatted key
        # eg takes ltcbtc and returns 'ltc'
        def pairKey(self, p):
            if p == 'LTC-USD':
                key = 'lsd'
            elif p == 'LTC-BTC':
                key = 'ltc'
            else:

                val = p.split('-')
                key = val[1].lower()
            return key
