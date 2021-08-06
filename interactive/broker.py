from ibw.client import IBClient
from config.config import Interactive

config = Interactive()

ib_client = IBClient(
    username=config.PAPER_USERNAME,
    account=config.PAPER_ACCOUNT
)

# create a new session.
ib_client.create_session()

# grab the account data.
account_data = ib_client.portfolio_accounts()

# print the data.
print(account_data)

# Grab historical prices.
aapl_prices = ib_client.market_data_history(conid=['265598'], period='1d', bar='5min')

# print the prices.
print(aapl_prices)

# close the current session.
ib_client.close_session()
