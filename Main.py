# imports
import AutoTrader_Functions as f
import robin_stocks as rs
import datetime as d
import json
from AutoTrader_Functions import CreditSpread


# noinspection PyShadowingNames
def purchase(symbol: str):
    f.add_event_log('function[purchase] Begin purchase evaluation')

    expiration_date = f.get_next_expiration(symbol)
    strikes = f.find_credit_spread_strikes(symbol, expiration_date)
    buy_strike = strikes[0]
    sell_strike = strikes[1]
    vix = rs.helper.request_get('https://www.cboe.com/indices/data/?symbol=VIX&timeline=1M')['data'][-1][-1]
    if f.is_enough_funds(abs(buy_strike - sell_strike)) and 30 > vix:
        f.add_event_log('function[purchase] Purchase conditions are met. Sufficient Funds and '
                        'Vix: {0} is under 30'.format(vix))
        f.purchase_loop(symbol, 1, expiration_date, sell_strike, buy_strike, 'put')
    f.add_event_log('function[purchase] Exiting')


def find_variable(key: str):
    with open('C:/Users/Davet/OneDrive/Desktop/Robinhood/Config.json') as json_file:
        section = json.load(json_file)
        return section[key]


def run():
    f.add_event_log('function[run] Robinhood Auto_trader Start')

    market: str = find_variable('market')
    symbol: str = find_variable('symbol')
    # check if market is currently open
    f.add_event_log('function[run] Market Open: {0}'.format(f.is_market_open(market)))

    if f.is_market_open(market):
        f.add_event_log('function[run] Market Open')

        # login
        f.account_login()
        # check spread positions
        if 1 > len(rs.get_open_option_positions()):
            purchase(symbol)

        portfolio_credit_spreads: list[CreditSpread] = f.get_credit_spreads_portfolio()

        # if list is empty place an order && sufficient balance

        # check age of the spreads
        for credit_spread in portfolio_credit_spreads:
            f.add_event_log('function[run] Check purchase date')
            purchase_date = d.datetime.strptime(credit_spread.purchase_date, '%Y-%m-%d')
            if (d.datetime.today() - purchase_date).days >= 30:
                f.add_event_log('function[run] purchase_date: {0} is older than 30 day. Sell position.')
                f.sell_loop(credit_spread)

        # check update config file
        if len(portfolio_credit_spreads) > 0:
            # stop_loss
            f.stop_loss(portfolio_credit_spreads, market)
        # log out
        rs.logout()
        f.add_event_log('function[run] Account Logout')
    f.add_event_log('function[run] Robinhood Auto_trader Shutdown.')


# run the program
run()

