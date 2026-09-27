# Forward and Reverse Gamma Scalping 
###### Everything you need to know 
*By: Gabriel Soler, L/S Gamma Desk, QUANTT*
#

#### 1. Background
An option's delta $\left( \Delta \right)$ tells you how much the option's price moves for a \$1 move in the underlying. Gamma $\left( \Gamma \right)$ tells you how much the delta itself changes for that same \$1 move. This means that as the stock moves, the directional exposure of any options position is constantly drifting.

**=>** Gamma scalping is the process of repeatedly re-hedging that drifting delta back to zero by trading the underlying (for us, SPY shares). Once delta-hedged, the position no longer cares about **direction**, only about **how much** the stock moves.

#
There are two sides to this trade:

1. **Forward scalping** (Long Gamma): you own options, and re-hedging makes you money. You pay for this through theta (time decay).
2. **Reverse scalping** (Short Gamma): you sell options, and re-hedging costs you money. You get paid for this through theta.

#

#### 2. Profitability of a Gamma Scalp
$$\text{PnL} \approx \frac{1}{2} \Gamma S^2 \left( \frac{\Delta S^2}{S^2} - \sigma_{IV}^2 \Delta t \right)$$

**=>** Profit is the difference between realized variance over the hedging interval $\left( \frac{\Delta S^2}{S^2} \right)$ and the implied variance $\left( \sigma_{IV}^2 \Delta t \right)$ you paid/collected scaled by dollar gamma $\left( \frac{1}{2} \Gamma S^2 \right)$ .

#
Realized variance is how much the stock actually moves (somewhat analogous to volatility) during the $\Delta t$. Implied variance is just how much movement the option was priced at, meaning how much the "market" expected the underlying to move. Dollar gamma is not really relevant to your leading, however, represents the gamma size and sensitivity of the contract you own.

1. When you **Long Gamma**, you are betting that the underlying stock moves **more** than the market expects (RV>IV)
2. When you **Short Gamma**, you are betting that the underlying stock moves **less** than the market expects (IV>RV)


#### 3. Forward Scalping (Long Gamma)
**Position:** Any net long options position, delta-hedged to zero (see Section 6 for the choices).

When you are long gamma, your delta moves **with** the stock. Re-hedging forces you to trade against the move:

1. SPY goes **up** → your delta becomes positive → you **sell** shares (selling high)
2. SPY goes **down** → your delta becomes negative → you **buy** shares (buying low)

**=>** Every re-hedge locks in a small profit. You are mechanically buying low and selling high.

#
**Example:** SPY at \$500, your position has $\Gamma = 4$ (delta changes by 4 shares per \$1 move).

1. SPY rises to \$505 → delta is now $+20$ → sell 20 shares at \$505
2. SPY falls back to \$500 → delta is back to $0$ → buy 20 shares at \$500
3. Hedging profit: $20 \times \$5 = \$100$

Each \$5 leg earns $\frac{1}{2} \Gamma \Delta S^2 = \frac{1}{2}(4)(5^2) = \$50$, so two legs = \$100. This is the formula from Section 2 in action.

**The catch:** you pay theta every day whether the stock moves or not. If SPY sits still, you bleed.


#### 4. Reverse Scalping (Short Gamma)
**Position:** Any net short options position, delta-hedged to zero (see Section 6 for the choices).

When you are short gamma, your delta moves **against** the stock. Re-hedging forces you to trade with the move:

1. SPY goes **up** → your delta becomes negative → you **buy** shares (buying high)
2. SPY goes **down** → your delta becomes positive → you **sell** shares (selling low)

**=>** Every re-hedge locks in a small loss. Using the same numbers as above, the round trip would **cost** you \$100.

**The payoff:** you collect theta every day. If SPY moves less than implied, the theta you collect is larger than your hedging losses.


#### 5. Theta vs. Gamma, the Breakeven
Theta and gamma are two sides of the same coin. For a delta-hedged position:
$$\Theta \approx -\frac{1}{2} \Gamma S^2 \sigma_{IV}^2$$

**=>** The market sets the option's price so that theta exactly pays for the gamma profits **if** the stock moves exactly as much as implied. This gives a daily breakeven move:
$$\text{Breakeven Move} \approx S \times \frac{\sigma_{IV}}{\sqrt{252}}$$

#
**Example:** SPY at \$500, IV of 16%

1. Breakeven move $= 500 \times \frac{0.16}{\sqrt{252}} \approx \$5.04$ per day
2. With $\Gamma = 4$, daily theta $\approx \frac{1}{2}(4)(5.04^2) \approx \$51$

So from Section 3, if SPY moves \$5 up and back in a day, the long gamma trader makes \$100 from hedging against \$51 of theta, a **profit**. If SPY only moves \$2 up and back, hedging earns $2 \times \frac{1}{2}(4)(2^2) = \$16$ against \$51 of theta, a **loss** (and a win for the short gamma trader).


#### 6. Choosing Your Position
There is no single "correct" structure for either side. Any position with net long gamma can be forward scalped, and any position with net short gamma can be reverse scalped. The choice comes down to cost, risk, liquidity, and how much vega (IV exposure) you want alongside your gamma.

#
**Long Gamma Structures**

| Structure | Setup | Pros | Cons |
|---|---|---|---|
| Long Call | Buy a call, short shares to hedge | Simple, one leg, one bid/ask spread | Starts with large delta, so a large initial share hedge |
| Long Put | Buy a put, buy shares to hedge | Same gamma as a call once hedged, and put IV tends to rise in selloffs, adding vega gains | Puts are often priced at higher IV (skew), so you pay more for the same gamma |
| Long Straddle | Buy call + put, same strike (usually ATM) | Starts near delta neutral, maximum gamma per strike | Most expensive, highest theta bleed |
| Long Strangle | Buy OTM call + OTM put | Cheaper than a straddle | Much less gamma until the stock moves toward a strike |
| Reverse Calendar | Buy near-dated, sell far-dated, same strike | Long gamma but reduced or negative vega, isolates the RV bet | Two expiries to manage, loses if IV at the back rises |

#
**Short Gamma Structures**

| Structure | Setup | Pros | Cons |
|---|---|---|---|
| Short Call | Sell a call, buy shares to hedge | Simple, one leg | Unlimited loss on a sharp rally |
| Short Put | Sell a put, short shares to hedge | Collects the skew premium, puts are usually the richest options | Largest losses come in crashes, exactly when gaps make hedging hardest |
| Short Straddle | Sell call + put, same strike (usually ATM) | Maximum theta collected, starts near delta neutral | Maximum gamma, so the most painful hedging losses |
| Short Strangle | Sell OTM call + OTM put | Wider profit zone, less gamma near the money | Still unlimited tail risk, less premium collected |
| Iron Condor / Iron Fly | Short strangle/straddle + buy further OTM wings | Defined max loss, lower margin | Wings cost premium, which eats into the VRP collected |

#
**Pure Call vs. Pure Put**

Once delta-hedged, a call and a put at the same strike and expiry behave almost identically. This comes from put-call parity:
$$C - P = S - K e^{-rT}$$

**=>** A call minus a put is just the stock plus cash, so after you hedge away the delta, both give you the same gamma and theta. The real differences are practical:

1. **Skew:** OTM puts usually trade at a higher IV than OTM calls. Great if you are selling, bad if you are buying.
2. **Initial hedge:** an ITM or deep OTM single option needs a bigger share hedge than a straddle.
3. **Liquidity:** pick whichever side has the tighter bid/ask spread at your strike.
4. **Early exercise:** SPY options are American style, so short ITM calls can be exercised early around dividend dates.

#
**Strike and Expiry**

1. **Strike:** gamma is highest at the money and falls off as you move OTM. ATM gives the most gamma per contract, OTM gives cheaper exposure that only "switches on" if the stock moves toward it.
2. **Expiry:** short-dated options have more gamma and more theta. Long-dated options have more vega. If you want a pure RV vs. IV bet, shorter-dated options put more of your PnL into gamma and less into IV changes.


#### 7. Side by Side
| | Forward Scalping | Reverse Scalping |
|---|---|---|
| Gamma | Long | Short |
| Example positions | Long call/put, straddle, strangle | Short call/put, straddle, strangle, iron condor |
| Theta | Pay | Collect |
| Re-hedging | Buy low, sell high | Buy high, sell low |
| Wins when | RV > IV | IV > RV |
| Best market | Large, choppy moves | Quiet, range-bound |
| Worst market | Flat, sleepy | Gaps and crashes |
| Loss profile | Limited to premium paid | Potentially very large, unless you buy wings |


#### 8. Hedging Frequency
The formula in Section 2 assumes you re-hedge every $\Delta t$. In practice you choose when to re-hedge, and this choice matters:

1. **Time-based:** re-hedge on a fixed schedule (e.g. every hour).
2. **Band-based:** re-hedge only when delta drifts past a threshold (e.g. $\pm$ 10 shares).

**=>** Hedging more often tracks the theory more closely, but every trade costs you the bid/ask spread and commissions. Hedging less often saves costs but makes your PnL more dependent on the exact path the stock takes.

#
This affects each side differently:

1. **Long Gamma:** each re-hedge **locks in** a profit, so you want to hedge often enough to capture the moves, but not so often that costs eat the profit.
2. **Short Gamma:** each re-hedge **locks in** a loss, so wider bands are common. If the stock mean-reverts before you hedge, you avoid the loss entirely.


#### 9. Risks to Know
1. **Theta bleed (Long Gamma):** in a quiet market you lose money every single day.
2. **Gap risk (Short Gamma):** you cannot hedge overnight or through a sudden crash. A large gap can wipe out weeks of collected theta in one move.
3. **Vega risk (both):** the PnL formula ignores changes in IV itself. If IV spikes, long gamma positions gain and short gamma positions lose on a mark-to-market basis, even before any hedging.
4. **Transaction costs (both):** a strategy that is profitable on paper can lose money once spreads and commissions are included.


#### 10. How This Fits Our Desk
Implied volatility is higher than realized volatility roughly 70-80% of the time. This gap is the **Volatility Risk Premium (VRP)**.

1. When IV>RV, **reverse scalping** collects the VRP.
2. When RV>IV, **forward scalping** profits from the moves.

**=>** Our edge is not in the scalping itself, which is mechanical. It is in **forecasting realized volatility** better than the market's implied volatility, knowing which side of the trade to be on, and choosing the structure (Section 6) that best expresses that view for its cost and risk.
