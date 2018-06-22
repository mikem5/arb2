import decimal

D = decimal.Decimal

decimal.getcontext().prec = 16
dq = D(".00000001")
df = D(".1")
du = D(".001")
currencies = ['ltc', 'usd', 'lsd']









def priceConv(price, typ):
    if typ == 1:
        return D(str(price)) * D('100000000')
    
    else:
        return D(str(price)) / D('100000000')



#
#
# Current string format:
#    price : quantity : price_w_fee : market_name : time : ( for usd) inverted price : inverted quantity
#
#

# takes an array of strings and packs them into the
# format "sargs1:sargs2:sargs3:..."
def stringPack(sargs):
    return ":".join(map(str,sargs))
    





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
def BuyFee(array, fee):
        price = array[0]
        quantity = array[1]

        btc_flat = price * quantity
        btc_fee = btc_flat * fee
        return btc_fee

# The loss that goes from selling for example LTC -> BTC
# how much btc we actually get
def SellFee(array, fee):
        price = array[0]
        quantity = array[1]

        btc_flat = price * quantity
        btc_fee = btc_flat / fee
        return btc_fee




# The Bid/Ask-FeePrice is the actual price that it would cost
# us to fill. This is just looking at cost. Different markets
# actually subtract the fee's differently from the quantity and
# do not actually effect the price at all.
# This should return the price after fee
def BidFeePrice(array, fee):
        price = array[0]
        quantity = array[1]
        idx = array[2]

        newq = price / fee
        return [newq , quantity, idx]

# for ask
def AskFeePrice(array, fee):
        price = array[0]
        quantity = array[1]
        idx = array[2]

        return [(price * fee), quantity, idx]



# in case we do not use the particular pair, or we error
def NullPrice():
        return [D('999999'),D('0'), 0], [D('0'),D('0'), 0]





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

def invertBase(price, quantity):
    
    # first we calculate usd, our new quantity
    usd = price * quantity 
    
    # now we get the new price
    p2 = 1 / price
    
    return [p2, usd]


# reverses the above transform
# this is to go back for actually placing orders and interacting
# with exchanges API's

def revertBase(price, quantity):

    # this is the original price
    p1 = 1 / price

    # this is the original quantity
    btc = quantity / p1

    return [p1, btc]




