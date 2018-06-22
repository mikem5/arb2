import json
import time
import requests
import urllib.request, urllib.parse, urllib.error
from decimal import *
import asyncio
import websockets
import redis


#import logging
#logger = logging.getLogger('websockets')
#logger.setLevel(logging.DEBUG)
#logger.addHandler(logging.StreamHandler())


from Exchange import *



r_server = redis.StrictRedis(unix_socket_path='/tmp/redis.sock')
r_pipe = r_server.pipeline()


r_server.delete('gdax:usd:bid', 'gdax:usd:ask',
        'gdax:usd:bid:back', 'gdax:usd:ask:back',
        'gdax:ltc:bid', 'gdax:ltc:ask',
        'gdax:ltc:bid:back', 'gdax:ltc:ask:back',
        'gdax:lsd:bid', 'gdax:lsd:ask',
        'gdax:lsd:bid:back', 'gdax:lsd:ask:back')







url = "wss://ws-feed.gdax.com"
mname = 'gdax'
feex = D('1.0025')

orders = { 'ltc' : {'ask':{}, 'bid':{}  },
        'usd' : {'ask':{}, 'bid':{}  }, 
        'lsd' : {'ask':{}, 'bid':{}   }
        }


#url = "wss://api.gemini.com/v1/marketdata/btcusd"

async def hello():
    async with websockets.connect(url) as websocket:

        name = {"type":"subscribe","product_id":"BTC-USD"}
        await websocket.send(json.dumps((name)))

        name = {"type":"subscribe","product_id":"LTC-USD"}
        await websocket.send(json.dumps((name)))

        name = {"type":"subscribe","product_id":"LTC-BTC"}
        await websocket.send(json.dumps((name)))


        initialob()
        initialob(cur = 'ltc')
        initialob(cur = 'lsd')




        while True:
            try:
                msg = await websocket.recv()
                #p_start = time.perf_counter()
                parsed = json.loads(msg)
                obparser(parsed)
                #print(time.perf_counter() - p_start)
            except KeyboardInterrupt:
                break
            except:
                pass






# parse a gemini orderbook into redis
def obparser(item):


    # For gdax we store the orders in their own INTERNAL dict, we refer to the orders
    # by a structure as follows
    #
    # asks = { '650.51' : {
    #                           'order_id1': [ quantity, time]
    #                           'order_id2': [ etc, etc]
    #                     }
    #        }
    #
    # we must do this because gdax does not compress all the orders ontop of the "price"
    # but keeps everything seperate.
    #
    # So when we receive an 'open' order we go into our dict at the price and put
    # our order_id inside the dict price
    #
    # We then lookup that price, add the quantity's together and do our redis
    # removes/adds.
    #
    # for a remove, we look at the price, then del[orderid]
    # then we look at the price and modify the redis
    #
    # finnally for a trade we reference the price/orderid make an adjustment to the
    # orderid quantity ONLY and modify redis
    # 
    # we do not cancel the order from a 'match' message as a following done message
    # will be following which is the removal from our dict.
    #

    try:
        tcur = item['product_id']
        if tcur == 'BTC-USD':
            cur = 'usd'
            print(item)
        elif tcur == 'LTC-USD':
            cur = 'lsd'
            print(item)
        elif tcur == 'LTC-BTC':
            cur = 'ltc'
            print(item)
        else:
            return

        price = item['price']
        if item['side'] == 'sell':
            side = 'ask'
        else:
            side = 'bid'


        if cur =='usd':
            if side =='ask':
                side = 'bid'
            else:
                side = 'ask'



    except:
        print("except in start of parser")
        return



    if price in orders[cur][side]:
        pass
    else:
        orders[cur][side][price] = {}


    # a new order 
    if item['type'] == 'open':

        orders[cur][side][price][item['order_id']] = D(item['remaining_size'])

        #quantity = sum(orders[cur][side][price].values())

    # cancelled or removed
    elif item['type'] == 'done':
        q = orders[cur][side][price].pop(item['order_id'],None)
        #print('popped ', str(side), str(item['order_id']), str(q))


    # trade, so a reduction in the quantity - it could go to 0.
    elif item['type'] == 'match':
        # we want to record all trades to their own keys now as this
        # lets us check on our orders easier
        moid = item['maker_order_id']
        toid = item['taker_order_id']
        size = D(item['size'])
        price = D(item['price'])
        if item['side'] == 'sell':
            tside = 'buy'
        else:
            tside = 'sell'


        outprice = ":".join([str(price),str(size)]) + " "
        r_pipe.append(":".join([mname,'trade',moid]),outprice)
        r_pipe.append(":".join([mname,'trade',toid]),outprice)
        r_pipe.expire(":".join([mname,'trade',moid]),1800)
        r_pipe.expire(":".join([mname,'trade',toid]),1800)
        
        trade_out = ":".join([str(price),str(size),tside,mname])
        r_pipe.zadd(":".join([mname,cur,'trades']), time.time() ,trade_out)
  
        if item['maker_order_id'] in orders[cur][side][price]:
            temp = D(orders[cur][side][price][item['maker_order_id']]) - D(item['size'])
            orders[cur][side][price][item['maker_order_id']] = D(temp)

        else:
            r_pipe.execute()
            return

    # change in the quantity of an order
    elif item['type'] == 'change':
        if item['order_id'] in orders[cur][side][price]:
             orders[cur][side][price][item['order_id']] = D(item['new_size'])
             #print('change ',str(side) ," ",str(orders[cur][side][price][item['order_id']]))
        else:
            pass


            
    # likely a "received" order which we dont care about
    else:
        return



    quantity = sum(orders[cur][side][price].values())

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

    # remove old object, maybe insert new object
    r_pipe.zremrangebyscore(":".join([mname,cur,side,'back']), conv_price - df , conv_price + df)




    if quantity > 0:
        r_pipe.zadd(":".join([mname,cur,side,'back']), conv_price ,order)
        #print("adding")

    r_pipe.zunionstore(":".join([mname,cur,side]), [":".join([mname,cur,side,'back'])])
 

    if side == 'bid':
        r_pipe.zremrangebyrank(":".join([mname,cur,side]), 0 , -20)
    else:
        r_pipe.zremrangebyrank(":".join([mname,cur,side]), 20 , -1)
  

    r_pipe.execute()






def initialob(cur = 'usd'):
    sess = requests.Session()
    if cur == 'usd':
        page = sess.get("https://api.gdax.com/products/BTC-USD/book?level=3", verify=False)
    elif cur == 'ltc':
        page = sess.get("https://api.gdax.com/products/LTC-BTC/book?level=3", verify=False)
    elif cur == 'lsd':
        page = sess.get("https://api.gdax.com/products/LTC-USD/book?level=3", verify=False)
 
    else:

        return

    content = json.loads(page.text)
    sess.close()
    #print(len(content['asks']), len(content['bids']))
    for x in content['asks']:


        side = 'ask'
        price = str(x[0])
        quantity = str(x[1])
   

        if cur == 'usd':
            if side == 'ask':
                side = 'bid'
            else:
                side = 'ask'




        if price in orders[cur][side]:
            pass
        else:
            orders[cur][side][price] = {}

       
        orders[cur][side][price][x[2]] = D(quantity)

    for p,v in orders[cur][side].items():
        price = p
        quantity = sum(v.values())

 
        if side == 'bid':
 
     
            fee_price = BidFeePrice([D(price), D(quantity), 0], feex)
            inv = invertBase( D(price), D(quantity))
            inv_fee = BidFeePrice([D(inv[0]), D(inv[1]), 0], feex)
        
  

            order = stringPack([  inv[0], inv[1], inv_fee[0], mname, time.time(),  price,  quantity, str(fee_price[0])])
            conv_price = priceConv(inv_fee[0],1).quantize(df)

        else:
            fee_price = AskFeePrice([D(price), D(quantity), 0], feex)
            inv = invertBase( D(price), D(quantity))
            inv_fee = AskFeePrice([D(inv[0]), D(inv[1]), 0], feex)
     
            order = stringPack([price, quantity, str(fee_price[0]),  mname, time.time(), inv[0], inv[1],inv_fee[0]])
            print(side,order)


            conv_price = priceConv(fee_price[0],1).quantize(df)




        r_pipe.zadd(":".join([mname,cur,side,'back']), conv_price ,order)
 
        print(side,order)



    for x in content['bids']:


        side = 'bid'
        price = str(x[0])
        quantity = str(x[1])


        if cur == 'usd':
            if side == 'ask':
                side = 'bid'
            else:
                side = 'ask'


        if price in orders[cur][side]:
            pass
        else:
            orders[cur][side][price] = {}

        orders[cur][side][price][x[2]] = D(quantity)


    for p,v in orders[cur][side].items():
        price = p
        quantity = sum(v.values())


        if side == 'ask':
 
            fee_price = AskFeePrice([D(price), D(quantity), 0], feex)
            inv = invertBase( D(price), D(quantity))
            inv_fee = AskFeePrice([D(inv[0]), D(inv[1]), 0], feex)
    

            order = stringPack([inv[0], inv[1], inv_fee[0], mname, time.time(),  price,  quantity, str(fee_price[0])])
            conv_price = priceConv(inv_fee[0],1)

        else:
            fee_price = BidFeePrice([D(price), D(quantity), 0], feex)
            inv = invertBase( D(price), D(quantity))
            inv_fee = BidFeePrice([D(inv[0]), D(inv[1]), 0], feex)
     
            order = stringPack([price, quantity, str(fee_price[0]),  mname, time.time(), inv[0], inv[1],inv_fee[0]])
            print(side,order)


            conv_price = priceConv(fee_price[0],1).quantize(df)




        r_pipe.zadd(":".join([mname,cur,side,'back']), conv_price ,order)
        #print(side,order)


   
    r_pipe.set(":".join([mname,cur,'book']),str(time.time()))


    r_pipe.execute()




    # remove all but top 50
    r_pipe.zunionstore(":".join([mname,cur,'bid']), [":".join([mname,cur,'bid','back'])])
    r_pipe.zunionstore(":".join([mname,cur,'ask']), [":".join([mname,cur,'ask','back'])])
    r_pipe.zremrangebyrank(":".join([mname,cur,'bid']), 0 , -20)
    r_pipe.zremrangebyrank(":".join([mname,cur,'ask']), 20 , -1)
    r_pipe.execute()

























asyncio.get_event_loop().run_until_complete(hello())












