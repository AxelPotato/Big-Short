import requests
from datetime import datetime, time
from pytz import timezone
from urllib.parse import urlencode
from time import sleep
from threading import Thread

from trading_viz.helper import tv_scanner, tv_payload_maker, fv_get_last_news, notify_via_telegram, tv_add_to_list
from config.config import Helper

config = Helper()

class Loop:

    def __init__(self):
        self.est = timezone('US/Eastern')
        self.premarket_start = time(4, 0)
        self.day_start = time(9, 30)
        self.day_end = time(16, 0)
        self.post_end = time(20, 0)

        self.alerted_stocks = set()
        self.alerted_stocks_clean = set()
        self.news_updates = set()

    def start(self):

        self.threadify(self.tv_thread_loop)
        self.threadify(self.news_thread_loop)

    def threadify(self, target_fucntion, function_args=None):
        if function_args:
            Thread(target=target_fucntion, args=function_args).start()
        else:
            Thread(target=target_fucntion).start()

    def message_maker(self, stock, data, banner, chat_target, add_to_list='blue'):
        stock_alert = data['stock'] + str(banner)

        if stock_alert not in self.alerted_stocks:

            self.alerted_stocks_clean.add((stock, data['stock'], chat_target))
            self.alerted_stocks.add(stock_alert)

            time, title, link, error = fv_get_last_news(data['stock'])
            stock_news = data['stock'] + str(time)

            if add_to_list != 'none':
                self.threadify(tv_add_to_list, (stock, config.TV_COOKIE, add_to_list))
                # tv_add_to_list(stock, TV_COOKIE, add_to_list)

            message = ''

            message += f'[{stock}]({config.TV_CHART_URL}{stock})\n'
            message += banner
            message += f'\n#####################\n'

            for entry, value in data.items():
                if entry == 'stock' or entry == 'Last':
                    continue

                message += f'{entry}: {value}\n'

            message += f'\n[FinViz]({config.FV_URL}?t={data["stock"]})  '

            if error == 'Success':
                message += f'[{time}]({link})\n{title}'
                self.news_updates.add(stock_news)

            elif error == 'No News':
                message += '\nNo News'
                self.news_updates.add(stock_news)

            else:
                message += '\nFailed Finviz Connection'

            # message += '[TradingView](' + TV_CHART_URL + stock + ')\n'
            # message += '[FinViz](' + FV_URL + '?t=' + data['stock'] + ')\n'
            # message += f'{datetime.now().date()}'

            notify_via_telegram(message, chat_target)

    def tv_fv_combo(self, add_to_list, banner, chat_target, tv_arg_array):

        tv_payload = tv_payload_maker(tv_arg_array)
        tv_dict = tv_scanner(tv_payload, config.TV_COOKIE)

        for stock, data in tv_dict.items():
            self.message_maker(stock, data, banner, chat_target, add_to_list)

    def thread_news_checker(self, full_stock, stock, chat_target):

        time, title, link, error = fv_get_last_news(stock)
        stock_news = stock + str(time)

        if stock_news not in self.news_updates:

            message = ''
            message += f'[{full_stock}]({config.TV_CHART_URL}{stock})\n'
            message += f'[News Update]({config.FV_URL}?t={full_stock})\n\n'

            if error == 'Success':
                message += f'[{time}]({link})\n{title}'
                self.news_updates.add(stock_news)
            elif error == 'No News':
                message += 'No News'
                self.news_updates.add(stock_news)
            else:
                print('Failed Finviz Connection')
                self.news_updates.add(stock_news)
                return

            # message += '[TradingView](' + TV_CHART_URL + full_stock + ')\n'
            # message += '[FinViz](' + FV_URL + '?t=' + stock + ')\n'
            # message += f'{datetime.now().date()}'

            chat_target = 'news'

            self.threadify(notify_via_telegram, (message, chat_target))

    def tv_fv_gainers_wrapper(self, time, the_banner, chat_target, tv_arg_array):
        tv_payload = tv_payload_maker(tv_arg_array)
        tv_dict = tv_scanner(tv_payload, config.TV_COOKIE)

        if time == 'premarket':
            stock_value = 'Pre-market CHG%'
        elif time == 'daytime':
            stock_value = 'Change from Open %'
        elif time == 'postmarket':
            stock_value = 'Post-Market CHG%'

        for stock, data in tv_dict.items():
            change = data[stock_value]

            if change > 100.0:
                banner = '100% ' + the_banner
                add_to_list = 'green'
            elif change > 50.0:
                banner = '50% ' + the_banner
                add_to_list = 'blue'
            elif change > 25.0:
                banner = '25% ' + the_banner
                add_to_list = 'blue'
            else:
                banner = the_banner
                add_to_list = 'none'

            self.message_maker(stock, data, banner, chat_target, add_to_list)

    def tv_thread_loop(self):
        while True:
            thread_list = []
            now = datetime.now(tz=self.est)
            day = now.isoweekday()
            hour = now.time()

            if day > 5:
                self.alerted_stocks = set()
                self.news_updates = set()
                self.alerted_stocks_clean = set()
                sleep(3600)
                continue

            if self.premarket_start <= hour <= self.day_start:

                arguments = ('premarket', 'Premarket Gainer', 'gainers', [('premarket_change', 'egreater', 25)])
                thread_list.append((self.tv_fv_gainers_wrapper, arguments))

            elif self.day_start <= hour <= self.day_end:

                arguments = ('daytime', 'Daytime Gainer', 'gainers', [('change_from_open', 'egreater', 25)])
                thread_list.append((self.tv_fv_gainers_wrapper, arguments))

            elif self.day_end <= hour <= self.post_end:
                pass
                # arguments = ('postmarket', 'Postmarket Gainer', 'gainers', [('postmarket_change', 'egreater', 25)])
                # thread_list.append((tv_fv_gainers_wrapper, arguments))

            else:
                self.alerted_stocks = set()
                self.news_updates = set()
                self.alerted_stocks_clean = set()
                print(f'{hour} is Zzzzz time')
                sleep(9)
                continue

            if thread_list:
                sleep_time_alerts = 10.0 / len(thread_list)

                for target_fucntion, function_args in thread_list:
                    self.threadify(target_fucntion, function_args)
                    sleep(sleep_time_alerts)

    def news_thread_loop(self):
        while True:

            now = datetime.now(tz=self.est)
            day = now.isoweekday()
            if day > 5:
                sleep(3600)
                continue

            if self.alerted_stocks_clean:
                for arguments in self.alerted_stocks_clean.copy():
                    self.threadify(self.thread_news_checker, arguments)
                    sleep(10)
