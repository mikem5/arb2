import decimal
import time
import copy


from config import *
        


# SIDES: ASK == 0, BIDS == 1


# an orders structure is as follows:
# [orderid, market.mname, loc, side (which is 0 or 1), price, quantity, full_order (a list), time_placed, seen_on_book, amount_traded]



class OrderList(object):

    def __init__(self):

                # there wouldnt be a 'btc' key here
                # sides are [ask, bid]
                self.open = {
                        'ltc' : [0,0],
                        'ftc' : [0,0],
                        'ppc' : [0,0],
                        'doge' :[0,0],
                        'nmc' : [0,0],
                        'xpm' : [0,0],
                        'vtc' : [0,0],
                        'drk' : [0,0],
                        'usd' : [0,0],
                         }



                self.updated = 0


    # we take lower case 'key' and bid/ask
    def getOrder(self, key, side):
        if side != 0 and side != 1:
            if side == 'ask':
                side = 0
            else:
                side = 1

        return self.open[key][side]
    
    # we take key, side, contents 
    # returns TRUE if success,
    # FALSE if already have an order
    def placeOrder(self, key, side, contents):
        if side != 0 and side != 1:
            if side == 'ask':
                side = 0
            else:
                side = 1

        if self.open[key][side] != 0:
            return False
        else:
            self.open[key][side] = contents
            return True


    # removes the order from this book
    # DOES NOT CANCEL ON ACTUAL EXCHANGE!!!!!
    def removeOrder(self, key, side):
        if side != 0 and side != 1:
            if side == 'ask':
                side = 0
            else:
                side = 1

        self.open[key][side] = 0


    # sometimes we need to change the quantity of
    # an order. this call ensures the order
    # is still here, and changes it
    def changeQuantity(self, key, side, quantity):
        if side != 0 and side != 1:
            if side == 'ask':
                side = 0
            else:
                side = 1

        if self.open[key][side] != 0:
            self.open[key][side][5] = quantity
            return True
        else:
            return False

    # should take the key and return the amount that is open
    # if is BTC, sums up all the BIDS from every
    # open order
    def getOpenAmount(self, key):

        sum = D('0')

        if key == 'btc':
            for k,v in self.open.items():
                # so we have open bid in this key
                if v[1] != 0:
                    # the quantity of BTC is actually the order q
                    # plus the price
                    sum += v[1][5] * v[1][4]

        else:
            if self.open[key][0] != 0:
                sum = self.open[key][0][5]

        return sum

    # returns true or false if we have any orders on the book
    def anyOpen(self):
        for k,x in self.open.items():
            if x[0] != 0 or x[1] != 0:
                return True
        
        return False


    # this nulls out all orders - we use this for the
    # cancelAllOrder calls to null everything out from
    # the open book
    def nullOrders(self):
        for k,x in self.open.items():
            self.open[k] = [0,0]


