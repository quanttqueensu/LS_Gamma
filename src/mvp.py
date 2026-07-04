#POC/MVP

from datetime import datetime
import random
import numpy as np 
import pandas as pd

"""
This document represents the minimum viable product (MVP) of long/short gamma strategy
VRP = Implied  - realised volatility

Improving RV forecasts -> improves performance

OVERPRICE IV 
    Short Gamma/Long Theta - forecast confirms V is higher than RV (this occurs 70-80% of the time)
       Trade: Sell an OTM strangle -> one OTM call and one OTM put at different strike prices but same expiry date.
        MAX LOSS: unlimited (if the underlying moves significantly in either direction)
        MAX GAIN: premium received for the strangle (exposes us to VRP upfront)
            Strategy makes money when the underlying asset does not move much so when delta is rehedged.

            important thing to note: for short gamma we are betting that the underlying asset will not move much, so we are effectively selling volatility.

UNDERPRICE IV
    Long Gamma/Short Theta - forecast confirms AV is lower than RV (this occurs 20-30% of the time)
            Trade: Buy an ATM straddle -> one ATM call and one ATM put at the same strike price and expiry date. 
            MAX LOSS: premium paid for the straddle (exposes us to VRP upfront)
            MAX GAIN: unlimited (if the underlying moves significantly in either direction)
                Strategy makes money when the underlying asset moves so when delta is rehedged, small realised profits are made.
                
             this side bets that market moves more than expected

"""

###Initial setup 

INITIAL_CAPITAL = 100_000




#forecasts will be maintained seperately in subfolder and various models will be tested and compared
def rv_forecast():

    return random.uniform(0.3, 0.5) 

def iv():

    return random.uniform(0.3, 0.5) 

realized_volatility_forecast = rv_forecast()
implied_volatility = iv()


# arbitrary thresholds for the sake of the MVP - need to develop tool/system to systematically determine dynamic thresholds
LG_THRESHOLD_HIGH  = 0.02
LG_THRESHOLD_LOW = -0.02
SG_THRESHOLD_LOW = -0.05
SG_THRESHOLD_HIGH = 0.05

import time
def vrp(realized_volatility_forecast, implied_volatility):

    volatility_risk_premium = realized_volatility_forecast - implied_volatility
    return volatility_risk_premium

# for i in range(10): # loop to simulate multiple time periods
#     if vrp(realized_volatility_forecast, implied_volatility) > THRESHOLD_HIGH:
#         print("IV OVER = Short Gamma = BUY ATM straddle.")
#     elif vrp(realized_volatility_forecast, implied_volatility) < THRESHOLD_LOW:
#         print("IV UNDER = Long Gamma = SELL OTM strangle.")
#     else:
#         print("IV FAIR = No action.")

for i in range(20): # loop to simulate multiple time periods
    realized_volatility_forecast = rv_forecast()
    implied_volatility = iv()
    timestamp = datetime.now().strftime("%H:%M:%S")

    
    if vrp(realized_volatility_forecast, implied_volatility) > LG_THRESHOLD_HIGH:
        print(f"{timestamp} | IV UNDER | Long Gamma  | BUY ATM straddle.")
        print("------------------------------------------")
        # execute_long_gamma_strategy()

    elif vrp(realized_volatility_forecast, implied_volatility) < SG_THRESHOLD_LOW:
        print(f"{timestamp} | IV OVER  | Short Gamma | SELL OTM strangle.")
        print("------------------------------------------")
        # execute_short_gamma_strategy()

    else:
        print(f"{timestamp} | IV FAIR  | No action.")
        print("------------------------------------------")

    time.sleep(0.1)


def execute_short_gamma_strategy():
    # Logic for executing short gamma strategy
    # BUY ATM straddle -> one ATM call and one ATM put at the same strike price and expiry date.
    return

def execute_long_gamma_strategy():
    # Logic for executing long gamma strategy
    # SELL OTM strangle -> one OTM call and one OTM put at different strike prices but same expiry date.
    return