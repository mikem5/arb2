import decimal
import time
import copy


from config import *
        


class Balance(object):

        def __init__(self):

                self.funds = {
                        'btc' : D('0'),
                        'ltc' : D('0'),
                        'ftc' : D('0'),
                        'ppc' : D('0'),
                        'doge' : D('0'),
                        'nmc' : D('0'),
                        'xpm' : D('0'),
                        'vtc' : D('0'),
                        'drk' : D('0'),
                        'usd' : D('0')
                         }


                # We use this to compare against
                # new fund balancements
                self.funds_comp = {
                        'btc' : D('0'),
                        'ltc' : D('0'),
                        'ftc' : D('0'),
                        'ppc' : D('0'),
                        'doge' : D('0'),
                        'nmc' : D('0'),
                        'xpm' : D('0'),
                        'vtc' : D('0'),
                        'drk' : D('0'),
                        'usd' : D('0')
                         }


                self.funds_new = {
                        'btc' : D('0'),
                        'ltc' : D('0'),
                        'ftc' : D('0'),
                        'ppc' : D('0'),
                        'doge' : D('0'),
                        'nmc' : D('0'),
                        'xpm' : D('0'),
                        'vtc' : D('0'),
                        'drk' : D('0'),
                        'usd' : D('0')
                         }

                # this is a rough amount that we can trade on
                self.available = {
                        'btc' : D('0'),
                        'ltc' : D('0'),
                        'ftc' : D('0'),
                        'ppc' : D('0'),
                        'doge' : D('0'),
                        'nmc' : D('0'),
                        'xpm' : D('0'),
                        'vtc' : D('0'),
                        'drk' : D('0'),
                        'usd' : D('0')
                         }






                self.updated = 0

        def getBalance(self):
                return self.funds
        
        def getCurrency(self, xcur):
                x = xcur.lower()
                # handling for ltc/usd market
                if x == 'lsd':
                    x = 'ltc'
                try:
                        return self.funds[x]
                except ValueError:
                    return False

        # returns the amount that can be traded with
        def getAvail(self, xcur):
                x = xcur.lower()

                # handling for ltc/usd market
                if x == 'lsd':
                    x = 'ltc'
                try:
                        return self.available[x]
                except ValueError:
                        return False


        def setCurrency(self, xcur, amount):
                x = xcur.lower()
                 # handling for ltc/usd market
                if x == 'lsd':
                    x = 'ltc'
                try:
                        self.funds[x] = amount
                        # We need this to mirror the changed funds
                        # in the case the we compare against laggy
                        # data returned from servers.
                        self.funds_comp[x] = amount
                except ValueError:
                        return False


        def setCurrencyNew(self, xcur, amount):
                x = xcur.lower()
                 # handling for ltc/usd market
                if x == 'lsd':
                    x = 'ltc'
                try:
                        self.funds_new[x] = amount
                except ValueError:
                        return False


        def setFunds(self):
            self.funds = copy.deepcopy(self.funds_new)
            return True

        def setComp(self):
            self.funds_comp = copy.deepcopy(self.funds_new)
            return True


        # this method takes a dict of values and
        # subtracts the on order amount from our balance
        # to compute the "available" dict here
        def computeAvailable(self, dic):
        
            self.available = copy.deepcopy(self.funds)
                
            for k,v in dic.items():
                self.available[k] -= v


        # This is a better check as sometimes the actual
        # values we get back might be slightly off...if this
        # is the case we don't want to cause issues.
        def checkNew(self):
            for k,v in self.funds_new.items():
                
                avg = (self.funds_new[k] + self.funds[k]) / 2
                diff = self.funds_new[k] - self.funds[k]
                if avg != 0:
                    abs_d = abs(diff/avg)
                else:
                    abs_d = 0

                if abs_d > D('.01'):
                    return False

            return True

        def checkComp(self):
            for k,v in self.funds_new.items():
                if v != self.funds_comp[k]:
                    return False
            return True
