import json
import time
import requests
import urllib.request, urllib.parse, urllib.error
import decimal
import redis
from Exchange import *

import asyncio
from autobahn.wamp.types import SubscribeOptions
from autobahn.asyncio.wamp import ApplicationSession, ApplicationRunner

r_server = redis.StrictRedis(unix_socket_path='/tmp/redis.sock')
r_pipe = r_server.pipeline()

r_server.delete('poloniex:ltc:ask','poloniex:ltc:bid',
        'poloniex:usd:ask','poloniex:usd:bid',
        'poloniex:ltc:ask:back','poloniex:ltc:bid:back',
        'poloniex:usd:ask:back','poloniex:usd:bid:back',
        'poloniex:lsd:ask','poloniex:lsd:bid',
        'poloniex:lsd:ask:back','poloniex:lsd:bid:back')
        



mname = 'poloniex'
tempbook = { 'ltc' : {'ask':{}, 'bid':{} } , 
        'usd' : {'ask':{}, 'bid':{} },
        'lsd' : {'ask':{}, 'bid':{} }
        }
feex = D('1.0025')
reset_time = {'ltc': time.time(), 'usd': time.time(), 'lsd': time.time()}



class MyComponent(ApplicationSession):

    @asyncio.coroutine
    def onJoin(self, details):
        print("session ready" + str(details))

        def order_l(*args,**kwargs):
            for x in args:
                try:
                    obparser(x,'ltc')
                    if time.time() - reset_time['ltc'] > 60:
                        reset_time['ltc'] = time.time()
                        r_server.delete('poloniex:ltc:ask:back','poloniex:ltc:bid:back')
                        del tempbook['ltc']
                        tempbook['ltc'] = {}
                        tempbook['ltc']['ask'] = {}
                        tempbook['ltc']['bid'] = {}
                        initialob('ltc')
                except:
                    print("except in order_l")
                    pass
                
        def order_u(*args,**kwargs):
            for x in args:
                try:
                    ps = time.perf_counter()
                    obparser(x,'usd')
                    print(time.perf_counter() - ps)
                    if time.time() - reset_time['usd'] > 60:
                        reset_time['usd'] = time.time()
                        r_server.delete('poloniex:usd:ask:back','poloniex:usd:bid:back')
                        del tempbook['usd']
                        tempbook['usd'] = {}
                        tempbook['usd']['ask'] = {}
                        tempbook['usd']['bid'] = {}
                        initialob('usd')
                        print("reinit usd")
                except KeyboardInterrupt:
                    break
                except:
                    print("except in order_u")
                    pass
        def order_ls(*args,**kwargs):
            for x in args:
                try:
                    obparser(x,'lsd')
                    if time.time() - reset_time['lsd'] > 60:
                        reset_time['lsd'] = time.time()
                        r_server.delete('poloniex:lsd:ask:back','poloniex:lsd:bid:back')
                        del tempbook['lsd']
                        tempbook['lsd'] = {}
                        tempbook['lsd']['ask'] = {}
                        tempbook['lsd']['bid'] = {}
                        initialob('lsd')


                except:
                    pass
 
        try:
            yield from self.subscribe(order_l, u'BTC_LTC')
            print("subscribed to btc ltc")
            yield from self.subscribe(order_u, u'USDT_BTC')
            print("subscribed to usdt btc")
            yield from self.subscribe(order_ls, u'USDT_LTC')
            print("subscribed to usdt btc")
 
        except Exception as e:
            print("could not subscribe to topic: {0}".format(e))




def obparser(item,cur):
    x = item
    if x['type'] == 'orderBookRemove':

        side = str(x['data']['type'])
        price = str(x['data']['rate'])

        if cur == 'usd':
            if side == 'ask':
                side = 'bid'
            else:
                side = 'ask'


        if price in tempbook[cur][side]:
            quantity = tempbook[cur][side][price]
            

            if side == 'ask':
                fee_price = AskFeePrice([D(price), D(quantity), 0], feex)
                inv = invertBase( D(price), D(quantity))
                inv_fee = AskFeePrice([D(inv[0]), D(inv[1]), 0], feex)
          
            else:
                fee_price = BidFeePrice([D(price), D(quantity), 0], feex)
                inv = invertBase( D(price), D(quantity))
                inv_fee = BidFeePrice([D(inv[0]), D(inv[1]), 0], feex)
         

            if cur == 'usd':
                conv_price = priceConv(inv_fee[0],1).quantize(df)

            else:
                conv_price = priceConv(fee_price[0],1).quantize(df)



            r_pipe.set(":".join([mname,cur,'book']),time.time())

            r_pipe.zremrangebyscore(":".join([mname,cur,side,'back']), conv_price - df , conv_price + df)

     

            a = r_pipe.execute()
            #print("remove: {} {} ".format(a[0],a[1]))



        # so the order isnt in tempbook so not on the actual redsi
        else:
            pass

    elif x['type'] == 'newTrade':

        print("type: {} price: {} amount: {} total: {} -- trade".format(str(x['data']['type']),str(x['data']['rate']), str(x['data']['amount']), str(x['data']['total'])))  

        price = D(x['data']['rate'])
        size = D(x['data']['amount'])
        tside = x['data']['type']

        trade_out = ":".join([str(price),str(size),tside,mname])
        r_pipe.zadd(":".join([mname,cur,'trades']), time.time() ,trade_out)
        r_pipe.execute()

    else:
        side = str(x['data']['type'])
        price = x['data']['rate']

        # there is a good chance that this is some sort of garbage.
        # for some reason this has been getting sent across the wire
        if D(price) < D('50') and cur == 'usd':
            print(x['data'])
            return
        quantity = x['data']['amount']



        if cur == 'usd':
            if side == 'ask':
                side = 'bid'
            else:
                side = 'ask'



        if side == 'ask':
            fee_price = AskFeePrice([D(price), D(quantity), 0], feex)
            inv = invertBase( D(price), D(quantity))
            inv_fee = AskFeePrice([D(inv[0]), D(inv[1]), 0], feex)
      
        else:
            fee_price = BidFeePrice([D(price), D(quantity), 0], feex)
            inv = invertBase( D(price), D(quantity))
            inv_fee = BidFeePrice([D(inv[0]), D(inv[1]), 0], feex)
     

        if cur == 'usd':
            order = stringPack([  inv[0], inv[1], inv_fee[0], mname, time.time(),  price,  quantity, str(fee_price[0])])
            conv_price = priceConv(inv_fee[0],1).quantize(df)

        else:
            order = stringPack([price, quantity, str(fee_price[0]),  mname, time.time(), inv[0], inv[1],inv_fee[0]])
            conv_price = priceConv(fee_price[0],1).quantize(df)


        r_pipe.set(":".join([mname,'alive']),time.time())
        r_pipe.set(":".join([mname,cur,'book']),time.time())

        r_pipe.zremrangebyscore(":".join([mname,cur,side,'back']), conv_price - df , conv_price + df)

        r_pipe.zadd(":".join([mname,cur,side,'back']), conv_price ,order)
 
        tempbook[cur][side][price] = quantity


        r_pipe.zunionstore(":".join([mname,cur,side]),  [ ":".join([mname,cur,side,'back']) ] )


        if side == 'bid':
            r_pipe.zremrangebyrank(":".join([mname,cur,side]), 0 , -100)
        else:
            r_pipe.zremrangebyrank(":".join([mname,cur,side]), 100 , -1)
     



        a = r_pipe.execute()

        #print(side,order)






def initialob(cur):
    sess = requests.Session()
    if cur == 'ltc':
        page = sess.get("https://poloniex.com/public?command=returnOrderBook&currencyPair=BTC_LTC&depth=25", verify=False)
    elif cur == 'usd':
        page = sess.get("https://poloniex.com/public?command=returnOrderBook&currencyPair=USDT_BTC&depth=25", verify=False)
    elif cur == 'lsd':
        page = sess.get("https://poloniex.com/public?command=returnOrderBook&currencyPair=USDT_LTC&depth=25", verify=False)
    else:
        return

    content = json.loads(page.text)
    sess.close()
    for x in content['asks']:


        side = 'ask'
        price = str(x[0])
        quantity = str(x[1])

        if cur == 'usd':
            if side == 'ask':
                side = 'bid'
            else:
                side = 'ask'



        tempbook[cur][side][price] = quantity   
      

        if side == 'ask':
            fee_price = AskFeePrice([D(price), D(quantity), 0], feex)
            inv = invertBase( D(price), D(quantity))
            inv_fee = AskFeePrice([D(inv[0]), D(inv[1]), 0], feex)
      
        else:
            fee_price = BidFeePrice([D(price), D(quantity), 0], feex)
            inv = invertBase( D(price), D(quantity))
            inv_fee = BidFeePrice([D(inv[0]), D(inv[1]), 0], feex)
     

    

        if cur == 'usd':
            order = stringPack([  inv[0], inv[1], inv_fee[0], mname, time.time(),  price,  quantity, str(fee_price[0])])
            conv_price = priceConv(inv_fee[0],1).quantize(df)

        else:
            order = stringPack([price, quantity, str(fee_price[0]),  mname, time.time(), inv[0], inv[1],inv_fee[0]])
            conv_price = priceConv(fee_price[0],1).quantize(df)




        r_pipe.zadd(":".join([mname,cur,side,'back']), conv_price ,order)
 
        #print(side,order)

 

    for x in content['bids']:


        side = 'bid'
        price = str(x[0])
        quantity = str(x[1])

        if cur == 'usd':
            if side == 'ask':
                side = 'bid'
            else:
                side = 'ask'




        tempbook[cur][side][price] = quantity   
      
        if side == 'ask':
            fee_price = AskFeePrice([D(price), D(quantity), 0], feex)
            inv = invertBase( D(price), D(quantity))
            inv_fee = AskFeePrice([D(inv[0]), D(inv[1]), 0], feex)
      
        else:
            fee_price = BidFeePrice([D(price), D(quantity), 0], feex)
            inv = invertBase( D(price), D(quantity))
            inv_fee = BidFeePrice([D(inv[0]), D(inv[1]), 0], feex)
    
   

        if cur == 'usd':
            order = stringPack([inv[0], inv[1], inv_fee[0], mname, time.time(),  price,  quantity, str(fee_price[0])])
            conv_price = priceConv(inv_fee[0],1)

        else:
            order = stringPack([price, quantity, str(fee_price[0]),  mname, time.time(), inv[0], inv[1],inv_fee[0]])
            conv_price = priceConv(fee_price[0],1).quantize(df)




        r_pipe.zadd(":".join([mname,cur,side,'back']), conv_price ,order)
        #print(side,order)


   
    r_pipe.set(":".join([mname,cur,'book']),str(time.time()))

    r_pipe.zunionstore(":".join([mname,cur,'ask']),  [ ":".join([mname,cur,'ask','back']) ] )
    r_pipe.zunionstore(":".join([mname,cur,'bid']),  [ ":".join([mname,cur,'bid','back']) ] )
  

    r_pipe.execute()








url = "wss://api.poloniex.com"


runner = ApplicationRunner(url = url, realm = "realm1")
print("after runner")
initialob('ltc')
initialob('usd')
initialob('lsd')



runner.run(MyComponent)

