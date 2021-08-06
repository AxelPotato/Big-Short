from user_agent import generate_user_agent
import requests
import json
from datetime import date
from bs4 import BeautifulSoup

from config.config import Helper

requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

config = Helper()


def fv_get_news(ticker, article_num=2):
    entrie_num = 0
    news = []

    today = date.today()
    today = today.strftime("%b-%d-%y")

    payload = requests.get(url=config.FV_URL, params={'t': ticker}, verify=False, headers={'User-Agent': generate_user_agent()})

    soup = BeautifulSoup(payload.content, 'html.parser')
    news_block = soup.find('table', class_='fullview-news-outer')

    for entry in news_block.contents:

        if entry != '\n' and entrie_num < article_num:

            time = entry.contents[0].contents[0]
            title = entry.find('a', class_="tab-link-news").contents[0]
            link = entry.find('a', class_="tab-link-news")['href']
            entrie_num += 1
            news.append((time, title, link))

    return news


def fv_get_last_news(ticker):
    entrie_num = 0

    today = date.today()
    today = today.strftime("%b-%d-%y")

    try:
        payload = requests.get(url=config.FV_URL, params={'t': ticker}, verify=False, headers={'User-Agent': generate_user_agent()})
    except ConnectionResetError or TimeoutError:
        print('Failed connection')
        return (False, False, False, 'Request Fail')

    if payload.status_code != 200:
        return (False, False, False, 'Request Fail')

    soup = BeautifulSoup(payload.content, 'html.parser')
    news_block = soup.find('table', class_='fullview-news-outer')

    if news_block != None:

        for entry in news_block.contents:

            if entry != '\n':

                time = entry.contents[0].contents[0]
                title = entry.find('a', class_="tab-link-news").contents[0]
                link = entry.find('a', class_="tab-link-news")['href']
                entrie_num += 1
                return (time, title, link, 'Success')

    return (False, False, False, 'No News')


def tv_scanner(tv_payload, tv_cookie):
    tv_dict = {}

    tv_headers_dict = {
        'Accept': 'text/plain, */*; q=0.01',
        'Accept-Encoding': 'gzip, deflate, br',
        'Cookie': tv_cookie,
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Origin': 'https://www.tradingview.com'
    }

    r = requests.post(config.TV_SCANNER_URL, headers=tv_headers_dict, data=tv_payload)

    for stock in r.json()['data']:
        tv_dict[stock['s']] = {
            'stock': stock['d'][1],
            'Last': stock['d'][2],
            'Change from Open %': round(stock['d'][3], 2),
            'Post-Market CHG%': round(stock['d'][4], 2) if stock['d'][4] != None else 'None',
            # '1-Month Low': round(stock['d'][5], 2),
            # '1-Month High': round(stock['d'][6], 2),
            'CHG%': round(stock['d'][7], 2),
            'Pre-market CHG%': round(stock['d'][8], 2) if stock['d'][8] != None else 'None',
        }

    return tv_dict


def tv_add_to_list(full_stock_name, tv_cookie, color):

    tv_payload = [full_stock_name]

    tv_headers_dict = {
        'Accept': 'text/plain, */*; q=0.01',
        'Accept-Encoding': 'gzip, deflate, br',
        'Cookie': tv_cookie,
        'Content-Type': 'application/json; charset=utf-8',
        'Origin': 'https://www.tradingview.com'
    }

    color_list = config.TV_LIST_URL + color + '/append/'

    requests.post(color_list, headers=tv_headers_dict, json=tv_payload)


def notify_via_telegram(message, chat_target):
    if chat_target == 'gainers':
        telegram_chat_id = config.TELEGRAM_CHAT_ID_GAINERS
    elif chat_target == 'losers':
        telegram_chat_id = config.TELEGRAM_CHAT_ID_LOSERS
    elif chat_target == 'news':
        telegram_chat_id = config.TELEGRAM_CHAT_ID_NEWS

    params = {"chat_id": telegram_chat_id, "text": message, "disable_web_page_preview": "True", "parse_mode": "markdown"}
    resp = requests.post(config.TELEGRAM_TARGET_URL, params)
    resp.raise_for_status()


def tv_payload_maker(tv_arg_array):
    '''
    Reieves tuples of (data_type, operation, value) \n
    data_types: everything in TV essentially \n
    operation types : eless ,egreater, in_range, not_in_range for the most part \n
    values: positive / negative integer or 'high' / 'low' string \n

    standard ones: \n
    {"left":"change","operation":"less","right":555}, \n
    {"left":"open","operation":"egreater","right":{open}, \n
    {"left":"close","operation":"less","right":888}, \n
    {"left":"change_from_open","operation":"less","right":666}, \n
    {"left":"High.1M","operation":"eless","right":"high"}, \n
    {"left":"Low.1M","operation":"egreater","right":"low"}, \n
    {"left":"premarket_change","operation":"less","right":444}, \n
    {"left":"postmarket_change","operation":"less","right":777}], \n

    in_range/not_in_range operation recieves a list in the right column \n
    {"left":"change_from_open","operation":"in_range","right":[5,10]} \n
    '''
    tv_payload_list = []

    tv_payload_list.append('{"filter":[{"left":"change","operation":"nempty"},')
    tv_payload_list.append('{"left":"type","operation":"in_range","right":["stock","dr","fund"]},')
    tv_payload_list.append('{"left":"subtype","operation":"in_range","right":["common","","etf","unit","mutual","money","reit","trust"]},')
    tv_payload_list.append('{"left":"exchange","operation":"in_range","right":["AMEX","NASDAQ","NYSE"]}')

    for tuple_args in tv_arg_array:
        if isinstance(tuple_args[2], int) or isinstance(tuple_args[2], list):
            tv_payload_list.append(',{"left":"%s","operation":"%s","right":%s}' % tuple_args)
        else:
            tv_payload_list.append(',{"left":"%s","operation":"%s","right":"%s"}' % tuple_args)

    tv_payload_list.append('],"options":{"active_symbols_only":true,"lang":"en"},')
    tv_payload_list.append('"symbols":{"query":{"types":[]},"tickers":[]},"columns":')
    tv_payload_list.append('["logoid","name","close","change_from_open","postmarket_change","Low.1M","High.1M","change","premarket_change","description","name","type","subtype","update_mode","pricescale","minmov","fractional","minmove2"],')
    tv_payload_list.append('"sort":{"sortBy":"change","sortOrder":"asc"},"range":[0,150]}')

    return ''.join(tv_payload_list)
