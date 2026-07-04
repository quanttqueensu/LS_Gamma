"""
IBKR Paper Trading — Test Order Script
----------------------------------------
Connects to IB Gateway (paper mode), pulls account info, places a small
test market order, and confirms the fill. Use this to sanity-check your
API connection before wiring in real strategy logic.

Requires: pip install ib_async --break-system-packages
"""

from ib_async import IB, Stock, MarketOrder

# --- Connection settings ---
HOST = '127.0.0.1'
PORT = 4002          # 4002 = IB Gateway paper trading | 7497 = TWS paper trading
CLIENT_ID = 1        # must be unique if you run multiple scripts/sessions at once

# --- Order settings ---
SYMBOL = 'AAPL'
EXCHANGE = 'SMART'
CURRENCY = 'USD'
ACTION = 'BUY'       # 'BUY' or 'SELL'
QUANTITY = 1         # keep this small for a test order


def main():
    ib = IB()

    print(f"Connecting to {HOST}:{PORT} (clientId={CLIENT_ID})...")
    ib.connect(HOST, PORT, clientId=CLIENT_ID)
    print("Connected:", ib.isConnected())

    # --- Account sanity check ---
    print("\n--- Account Summary ---")
    for row in ib.accountSummary():
        if row.tag in ('NetLiquidation', 'BuyingPower', 'TotalCashValue'):
            print(f"{row.tag}: {row.value} {row.currency}")

    # --- Define and qualify the contract ---
    contract = Stock(SYMBOL, EXCHANGE, CURRENCY)
    ib.qualifyContracts(contract)
    print(f"\nQualified contract: {contract}")

    # --- Get a quick quote before trading ---
    ticker = ib.reqMktData(contract)
    ib.sleep(2)
    print(f"Last: {ticker.last} | Bid: {ticker.bid} | Ask: {ticker.ask}")

    # --- Place the test order ---
    order = MarketOrder(ACTION, QUANTITY)
    trade = ib.placeOrder(contract, order)
    print(f"\nOrder submitted: {ACTION} {QUANTITY} {SYMBOL} (Market)")

    # --- Wait for status updates ---
    ib.sleep(3)
    print(f"Order status: {trade.orderStatus.status}")

    # Wait a bit longer if not yet filled (paper fills are usually instant during market hours)
    timeout = 10
    while trade.orderStatus.status not in ('Filled', 'Cancelled', 'ApiCancelled') and timeout > 0:
        ib.sleep(1)
        timeout -= 1

    print(f"Final status: {trade.orderStatus.status}")
    if trade.orderStatus.status == 'Filled':
        fill = trade.fills[-1]
        print(f"Filled {fill.execution.shares} @ {fill.execution.price}")
    elif trade.orderStatus.status != 'Filled':
        print("Order not filled yet — check that market is open, "
              "and that Read-Only API is unchecked in Gateway settings.")

    # --- Show current positions ---
    print("\n--- Current Positions ---")
    for pos in ib.positions():
        print(pos)

    ib.disconnect()
    print("\nDisconnected.")


if __name__ == '__main__':
    main()