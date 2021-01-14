import robin_stocks as rs
import os
from py_linq import Enumerable
import datetime as d
import time
import zulu as z
from twilio.rest import Client
import re
import json


class CreditSpread:
    # noinspection PyShadowingNames
    def __init__(self, symbol: str, expiration_date: str, quantity: int, buy_strike: float, sell_strike: float,
                 buy_price: float, sell_price: float, option_type: str, purchase_date: str, credit_id='none'):
        self.symbol = symbol
        self.expiration_date = expiration_date
        self.quantity = quantity
        self.buy_strike = buy_strike
        self.sell_strike = sell_strike
        self.buy_price = buy_price
        self.sell_price = sell_price
        self.option_type = option_type
        self.purchase_date = purchase_date
        self.spread_value = sell_price - buy_price
        self.stop_value = (sell_price - buy_price) * 2.5
        self.credit_id = credit_id


# functions
def account_login():
    # set login creds
    robin_user = os.environ.get("robinhood_username")
    robin_pass = os.environ.get("robinhood_password")

    # login
    rs.login(username=robin_user,
             password=robin_pass,
             expiresIn=86400,
             by_sms=True)
    add_event_log('function[account_login] Logging In')


def write_json(data, filename='none'):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)


def add_event_log(event: str):
    file_location = 'C:/Users/Davet/OneDrive/Desktop/Robinhood/Event Logs/'
    file_name = '{0} Event Log.txt'.format(d.datetime.now().date())
    w = open(file_location + file_name, "a")
    w.write('{0},{1}\n'.format(d.datetime.now(), event))
    w.close()


def add_price_log(symbol: str, expiration_date: str, buy_strike: float, sell_strike: float, buy_price: float,
                  sell_price: float, current_price: float, stop_price: float, profit_price: float):
    """Adds Credit Spread to config file"""
    file_location = 'C:/Users/Davet/OneDrive/Desktop/Robinhood/Price Records/Historical.csv'

    w = open(file_location, "a")
    w.write('{0},{1},{2},{3},{4},{5},{6},{7},{8},{9},{10}\n'.format(d.datetime.now(), symbol, expiration_date,
                                                                    float(rs.get_latest_price(symbol)[0]), buy_strike,
                                                                    sell_strike, buy_price, sell_price, current_price,
                                                                    stop_price, profit_price))
    w.close()


'''
def add_credit_spread_to_config(credit_spread: CreditSpread):
    """Adds Credit Spread to config file"""
    with open('Config.json') as json_file:
        section = json.load(json_file)

        temp = section['credit_spreads']
        credit_id_list: list[int] = list()
        z: int
        for num in range(len(temp)):
            credit_id_list.append(temp[num]['credit_id'])
        for num in range(len(credit_id_list) + 1):
            if num not in credit_id_list:
                z = num

        # python object to be appended
        y = {
            "symbol": credit_spread.symbol,
            "expiration_date": credit_spread.expiration_date,
            "quantity": str(credit_spread.quantity),
            "buy": {"buy_price": str(credit_spread.buy_price), "buy_strike": str(credit_spread.buy_strike)},
            "sell": {"sell_price": str(credit_spread.sell_price), "sell_strike": str(credit_spread.sell_strike)},
            "option_type": credit_spread.option_type,
            "purchase_date": credit_spread.purchase_date,
            "cancel_url": credit_spread.cancel_order_url,
            "spread_value": str(credit_spread.spread_value),
            "stop_value": str(credit_spread.stop_value),
            "credit_id": z
        }

        # appending data to emp_details
        temp.append(y)

    write_json(section)


def remove_credit_spread_from_config(credit_spread: CreditSpread):
    """Removes Credit Spread from config file"""
    with open('Config.json') as json_file:
        section = json.load(json_file)

        temp = section['credit_spreads']

        index = next((index for (index, d) in enumerate(temp) if d["credit_id"] == credit_spread.credit_id), None)
        temp.pop(index)

    write_json(section)


def get_credit_spread_config() -> list[CreditSpread]:
    """Gets the current Credit Spreads"""
    with open('Config.json') as json_file:
        section = json.load(json_file)

    return section['credit_spreads']
'''


def is_enough_funds(spread: int) -> bool:
    buying_power: float = float(rs.profiles.load_account_profile(info='buying_power'))
    add_event_log(
        'function[is_enough_funds] Buying Power: {0} '
        'Price Spread: ${1} Sufficient Funds: {2}}'.format(buying_power, spread, buying_power > (spread * 100)))
    return buying_power > (spread * 100)


def is_market_open(market: str) -> bool:
    """Checks is the specified market is currently open
    :returns bool"""
    today = str(d.date.today())
    try:
        # times given in zulu
        market_hours = rs.markets.get_market_hours(market, today)
        open_time = d.datetime.strptime(str(market_hours['opens_at'][0:19:1]).replace('T', ' '), '%Y-%m-%d %H:%M:%S')
        # close time
        close_time = d.datetime.strptime(str(market_hours['closes_at'][0:19:1]).replace('T', ' '), '%Y-%m-%d %H:%M:%S')
        # current time
        current_time = d.datetime.strptime(str(z.now())[0:19:1].replace('T', ' '), '%Y-%m-%d %H:%M:%S')
        if open_time <= current_time < close_time:
            return True
        else:
            return False
    except Exception:
        raise Exception


def purchase_loop(symbol: str, quantity: int, expiration_date: str, sell_strike: float, buy_strike: float,
                  option_type: str):
    buy_price: float = 0
    sell_price: float = 0
    reorder: bool = True
    add_event_log('function[purchase_loop] Entering')
    while reorder:
        print('checking price')
        # update price
        # buy
        buy_price = float(rs.find_options_by_expiration_and_strike(symbol, expiration_date, str(buy_strike),
                                                                   option_type, info='adjusted_mark_price')[0])
        print('Buy Price: {0}'.format(buy_price))
        # sell
        sell_price = float(rs.find_options_by_expiration_and_strike(symbol, expiration_date, str(sell_strike),
                                                                    option_type, info='adjusted_mark_price')[0])
        print('Sell Price: {0}'.format(sell_price))
        price: float = round(sell_price - buy_price, 2)
        cancel_order = buy_credit_spread(symbol, quantity, price, expiration_date, sell_strike, buy_strike, option_type)
        print("placed the order")
        time.sleep(30)
        open_positions = Enumerable(rs.get_all_open_option_orders()).where(lambda x: x['state'] == 'queued')
        if len(open_positions) > 0:
            reorder = True
            rs.helper.request_post(cancel_order)
            add_event_log('function[purchase_loop] Order Canceled')

        else:
            reorder = False
            add_event_log('function[purchase_loop] Order Complete')

    add_event_log('function[purchase_loop] Exiting')


def sell_loop(credit_spread: CreditSpread):
    add_event_log('function[sell_loop] Entering')
    reorder: bool = True
    while reorder:
        # update price
        # buy
        bid_price: float = float(rs.find_options_by_expiration_and_strike(credit_spread.symbol,
                                                                          credit_spread.expiration_date,
                                                                          str(credit_spread.buy_strike),
                                                                          credit_spread.option_type,
                                                                          info='adjusted_mark_price'))
        # sell
        ask_price: float = float(rs.find_options_by_expiration_and_strike(credit_spread.symbol,
                                                                          credit_spread.expiration_date,
                                                                          str(credit_spread.sell_strike),
                                                                          credit_spread.option_type,
                                                                          info='adjusted_mark_price'))
        price: float = ask_price - bid_price
        cancel_order = sell_credit_spread(credit_spread.symbol, credit_spread.quantity, price,
                                          credit_spread.expiration_date, credit_spread.sell_strike,
                                          credit_spread.buy_strike, credit_spread.option_type)
        time.sleep(10)
        open_positions = Enumerable(rs.get_all_open_option_orders()).where(lambda x: x['state'] == 'queued')
        if len(open_positions) > 0:
            reorder = True
            rs.helper.request_post(cancel_order)
            add_event_log('function[sell_loop] Order Canceled')

        else:
            reorder = False
            add_event_log('function[sell_loop] Order Complete')

    add_event_log('function[sell_loop] Exiting')
    # update config


def stop_loss(credit_spread: list[CreditSpread], market: str):
    # stop loss continue loop while market is open and current price is below stop
    keep_watch: bool = True
    add_event_log('function[stop_loss] Starting Market Watch.')
    # make a list of objects to iterate through
    while keep_watch:
        # continue monitoring price while market is open with open positions
        if is_market_open(market) and len(credit_spread) > 0:

            for i in range(len(credit_spread)):
                # Credit Spread Long Price
                long_current = get_current_price(credit_spread[i], credit_spread[i].buy_strike)
                # Credit Spread Short Price
                short_current = get_current_price(credit_spread[i], credit_spread[i].sell_strike)
                # Current Spread Value
                price_current: float = round(short_current - long_current, 2)
                price_stop: float = round(credit_spread[i].stop_value, 2) / 100
                # stop loss
                if price_current >= price_stop:
                    add_event_log('function[stop_loss] Enacting Stop Loss')
                    # sell the spread
                    sell_loop(credit_spread[i])
                    credit_spread.pop(i)
                # TODO ADJUST TAKE PROFIT
                take_profit: float = (credit_spread[i].spread_value * .25) / 100
                if take_profit >= price_current:
                    add_event_log('function[stop_loss] Beginning Take Profit')
                    while price_current >= (credit_spread[i].spread_value * .75):
                        cancel = sell_credit_spread(credit_spread[i].symbol, credit_spread[i].quantity,
                                                    take_profit, credit_spread[i].expiration_date,
                                                    credit_spread[i].sell_strike, credit_spread[i].buy_strike,
                                                    credit_spread[i].option_type)
                        rs.logout()
                        time.sleep(60)
                        account_login()
                        open_positions = Enumerable(rs.get_all_open_option_orders()).where(
                            lambda x: x['state'] == 'queued')
                        if len(open_positions) > 0:
                            rs.helper.request_post(cancel)
                            long_current = get_current_price(credit_spread[i], credit_spread[i].buy_strike)
                            short_current = get_current_price(credit_spread[i], credit_spread[i].sell_strike)
                            price_current = round(short_current - long_current, 2)
                add_price_log(credit_spread[i].symbol, credit_spread[i].expiration_date, credit_spread[i].buy_strike,
                              credit_spread[i].sell_strike, long_current, short_current, price_current,
                              price_stop, take_profit)
            rs.logout()
            add_event_log('function[stop_loss] Account Logout')
            time.sleep(120)
            account_login()

        else:
            keep_watch = False
    add_event_log('function[stop_loss] Exiting Market Watch')


# purchase credit spread
# noinspection PyShadowingNames
def buy_credit_spread(symbol: str, quantity: int, price: float, expiration_date: str, sell_strike: float,
                      buy_strike: float, direction: str):
    """Places the order to open a Credit Spread position
    :returns Cancel url"""
    leg1 = {"expirationDate": expiration_date,
            "strike": sell_strike,
            "optionType": direction,
            "effect": "open",
            "action": "sell"}
    leg2 = {"expirationDate": expiration_date,
            "strike": buy_strike,
            "optionType": direction,
            "effect": "open",
            "action": "buy"}

    spread = [leg1, leg2]
    order = rs.order_option_spread('credit', price, symbol, quantity, spread)
    add_event_log('function[buy_credit_spread] {0}'.format(order))
    return order['cancel_url']


def sell_credit_spread(symbol: str, quantity: int, price: float, expiration_date: str, sell_strike: float,
                       buy_strike: float, direction: str):
    leg1 = {"expirationDate": expiration_date,
            "strike": sell_strike,
            "optionType": direction,
            "effect": "close",
            "action": "buy"}
    leg2 = {"expirationDate": expiration_date,
            "strike": buy_strike,
            "optionType": direction,
            "effect": "close",
            "action": "sell"}

    spread = [leg1, leg2]
    order = rs.order_option_spread('debit', price, symbol, quantity, spread, timeInForce='gtc')
    cancel = order['cancel_url']
    add_event_log('function[sell_credit_spread] {0}'.format(order))
    return cancel


def get_credit_spreads_portfolio():
    """Find the current credit spreads in the portfolio"""
    # retrieve open option positions
    add_event_log('function[get_credit_spreads_portfolio] Entering')

    open_positions = rs.options.get_open_option_positions()
    add_event_log('function[get_credit_spreads_portfolio] {0}'.format(open_positions))

    # list of CreditSpread objects
    credit_list: list = list()

    # two positions are required to make a credit spread if only one position remains there are no more spreads.
    while len(open_positions) > 1:
        # checks the update time stamp
        pairs = Enumerable(open_positions).where(
            lambda x: x['updated_at'][0:19:1] == open_positions[0]['updated_at'][0:19:1]).to_list()

        # pairs are updated at the same time. two positions updated within 1 second of each other belong together.
        if len(pairs) == 2:
            # get option specific details for the long and short positions
            long = rs.helper.request_get(
                Enumerable(pairs).where(lambda x: x['type'] == 'long').select(lambda x: x['option'])[0])
            short = rs.helper.request_get(
                Enumerable(pairs).where(lambda x: x['type'] == 'short').select(lambda x: x['option'])[0])

            # define the variables in the credit spread object
            symbol = long['chain_symbol']
            expiration_date: str = long['expiration_date']
            quantity = int(float(pairs[0]['quantity']))
            option_type: str = long['type']
            buy_strike: float = float(long['strike_price'])
            sell_strike: float = float(short['strike_price'])
            buy_price: float = abs(
                float(Enumerable(pairs).where(lambda x: x['type'] == 'long').select(lambda x: x['average_price'])[0]))
            sell_price: float = abs(
                float(Enumerable(pairs).where(lambda x: x['type'] == 'short').select(lambda x: x['average_price'])[0]))
            purchase_date = long['created_at'][0:10:1]
            # add Credit Spread object to the credit spread list
            my_spread = CreditSpread(symbol, expiration_date, quantity, buy_strike, sell_strike, buy_price, sell_price,
                                     option_type, purchase_date)

            credit_list.append(my_spread)

            # remove the current item from list to prevent duplicate Credit Spread objects
            open_positions.pop(0)
        else:
            # remove current item if the number is anything other than two
            open_positions.pop(0)

        # return the list of Credit Spread objects
    add_event_log('function[get_credit_spreads_portfolio] Exiting')
    return credit_list


def find_credit_spread_strikes(symbol_param: str, target_expiration_date: str):
    """Find the strike prices that corresponds with 30 & 16 Delta
    :returns [buy strike, sell strike]"""
    add_event_log('function[find_credit_spread_strikes] Looking for {0} '
                  'strike prices for {1}'.format(symbol_param, target_expiration_date))

    current_price: int = int(round(float(rs.stocks.get_latest_price(symbol_param)[0]), 0))
    buy_strike = get_strike_target(symbol_param, .16, target_expiration_date, current_price)
    sell_strike = get_strike_target(symbol_param, .31, target_expiration_date, current_price)
    strike_list: list[int] = list()
    strike_list.append(buy_strike)
    strike_list.append(sell_strike)
    add_event_log('function[find_credit_spread_strikes] Found buy_strike: {0} '
                  'sell_strike: {1}'.format(buy_strike, sell_strike))

    return strike_list


# noinspection PyShadowingNames
def get_strike_target(symbol: str, delta_target: float, expiration_date: str, current_price: int):
    """Finds the strike price that corresponds to the given Delta"""
    add_event_log('function[get_strike_target] Entering')

    delta = 1.0
    while delta > delta_target:
        current_price -= 1
        current_option = rs.find_options_by_expiration_and_strike(symbol, expiration_date, str(current_price),
                                                                  optionType='put')
        if len(current_option) > 0:
            delta = abs(float(current_option[0]['delta']))
        elif current_price > 0:
            continue
        else:
            raise Exception
    add_event_log('function[get_strike_target] Exiting')
    return int(current_price)


# noinspection PyShadowingNames
def get_next_expiration(symbol: str):
    """Finds the next expiration date for a credit spread"""
    add_event_log('function[get_next_expiration_date] Entering')
    ex_date_list: list = list()
    expiration_dates = rs.options.get_chains(symbol, info='expiration_dates')
    for index in range(len(expiration_dates)):
        my_date = d.datetime.strptime(expiration_dates[index], '%Y-%m-%d')
        ex_date_list.append(my_date.date())

    target_date = (d.datetime.now() + d.timedelta(45)).date()

    first_expiration_date = Enumerable(ex_date_list).where(lambda x: x >= target_date).first()
    while target_date != first_expiration_date:
        target_date += d.timedelta(1)
    add_event_log('function[get_next_expiration_date] Next viable expiration date: {0}'.format(target_date))
    return str(target_date)


def get_current_price(credit_spread: CreditSpread, strike: float) -> float:
    return float(rs.find_options_by_expiration_and_strike(credit_spread.symbol, credit_spread.expiration_date,
                                                          str(strike),
                                                          optionType=credit_spread.option_type,
                                                          info='adjusted_mark_price')[0])


def find_variable(key: str):
    with open('Config.json') as json_file:
        section = json.load(json_file)
        return section[key]


def get_challenge_sms():
    add_event_log('function[get_challenge_sms] Robinhood requested authentication')
    account_sid = find_variable('account_sid')
    auth_token = find_variable('auth_token')
    client = Client(account_sid, auth_token)

    message_receive = client.messages.list()
    number: str
    try:
        latest = message_receive[0].body
        number = re.findall(r'(\d{6})', latest)[0]
    except IndexError:
        latest = message_receive[1].body
        number = re.findall(r'(\d{6})', latest)[0]
    time.sleep(10)
    add_event_log('function[get_challenge_sms] Checked Twilio log. Submitted security code {0}'.format(number))

    return number
