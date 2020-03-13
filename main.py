import ccxt
from time import sleep
from datetime import datetime
import functions as fs
import message as msg
from setting import Settings

my_settings = Settings()

myOKEX = ccxt.okex3()
myOKEX.apiKey = my_settings.okex_entry['apikey']
myOKEX.secret = my_settings.okex_entry['secret']
myOKEX.password = my_settings.okex_entry['password']
myOKEX.proxies = my_settings.proxies

# 初始化参数
symbol = 'BTC/USDT'     # ccxt采用“/”连接币对，OKEX采用“-”连接
trade_coin = symbol.split('/')[0]
base_coin = symbol.split('/')[-1]
time_interval = '15m'   # 确定获取哪个时间周期的K线

# ----有问题------------------有问题--------------有问题--------------有问题
signal_last = 'closing'  # 上一次交易类型，初始交易状态为平仓
# ----有问题------------------有问题--------------有问题--------------有问题

# 开始主循环
while True:
    # 1、取得并等到获取数据的时间点
    run_time = fs.next_run_time(time_interval)
    sleep(max(0, (run_time - datetime.now()).seconds))
    while True:
        if datetime.now() < run_time:
            continue
        else:
            break

    # 2.获取实时数据并验证
    candle_data = fs.get_candle_data(myOKEX, time_interval, symbol, run_time)
    if candle_data is None: continue    # 获取数据失败，则重新开始循环

    # 3.根据最新数据计算买卖信号
    signal_trade = fs.get_brin_signal(candle_data)

    # 删除部分------------------------------------------------------------------------------------
    print(signal_trade)
    # 删除部分------------------------------------------------------------------------------------

    if signal_trade == 'nothing': continue

    # 4.下单
    # 4.1 获取账户余额信息，市场ticker信息
    try:
        balance_info = myOKEX.fetch_balance({'type': 'margin'})[symbol]     # 币币杠杆户交易币对余额
        ticker_info = myOKEX.fetch_ticker(symbol)
    except Exception as e:
        print('Can not get account balance and tiker.')
        continue
    # 4.2 交易信号组合，共6种（本次交易信号只会有三种，上一次交易也只会有三种）
    # 第一种情况：平空仓，开多仓
    if signal_trade == 'long' and signal_last == 'short':
        price = ticker_info['ask'] * 1.02
        # 01\平掉空仓，下买单
        amount = int(float(balance_info[base_coin]['free']) / price * 10**8) / 10**8
        order_id = fs.okex_place_order(myOKEX, symbol, amount, price, 'buy')
        if order_id is None: continue
        # 02\还币（BTC）
        fs.okex_repayment(myOKEX, symbol, trade_coin)
        # 03\借币（USDT）
        fs.okex_borrow(myOKEX, symbol, base_coin, my_settings.lever_times)
        # 04\加杠杆，下买单
        balance_info = myOKEX.fetch_balance({'type': 'margin'})[symbol]
        amount = int(float(balance_info[base_coin]['free']) / price * 10**8) / 10**8
        fs.okex_place_order(myOKEX, symbol, amount, price, 'buy')
    # 第二种情况：开多仓。之前的平仓分两种情况，平多仓和平空仓，不需区分情况写代码，用以下代码结果一样。
    elif signal_trade == 'long' and signal_last == 'closing':
        # 01\借币(USDT)
        fs.okex_borrow(myOKEX, symbol, base_coin, my_settings.lever_times)
        # 02\加杠杆，下买单
        price = ticker_info['ask'] * 1.02
        balance_info = myOKEX.fetch_balance({'type': 'margin'})[symbol]
        amount = int(float(balance_info[base_coin]['free']) / price * 10**8) / 10**8
        fs.okex_place_order(myOKEX, symbol, amount, price, 'buy')
    # 第三种情况：平多仓，开空仓
    elif signal_trade == 'short' and signal_last == 'long':
        price = float(ticker_info['bid']) * 0.98
        # 01\平多仓，下卖单
        amount = float(balance_info[trade_coin]['free'])
        fs.okex_place_order(myOKEX, symbol, amount, price, 'sell')
        # 02\还币(USDT)
        fs.okex_repayment(myOKEX, symbol, base_coin)
        # 03\借币(BTC)
        fs.okex_borrow(myOKEX, symbol, trade_coin, my_settings.lever_times)
        # 04\加杠杆，下卖单
        balance_info = myOKEX.fetch_balance({'type': 'margin'})[symbol]
        amount = float(balance_info[trade_coin]['free'])
        fs.okex_place_order(myOKEX, symbol, amount, price, 'sell')
    # 第四种情况：开空仓
    elif signal_trade == 'short' and signal_last == 'closing':
        # 01\借币(BTC)
        fs.okex_borrow(myOKEX, symbol, trade_coin, my_settings.lever_times)
        # 02\加杠杆，下卖单
        price = ticker_info['bid'] * 0.98
        balance_info = myOKEX.fetch_balance({'type': 'margin'})[symbol]
        amount = float(balance_info[trade_coin]['free'])
        fs.okex_place_order(myOKEX, symbol, amount, price, 'sell')
    # 第五种情况：平多仓
    elif signal_trade == 'closing' and signal_last == 'long':
        # 01\下卖单
        price = ticker_info['bid'] * 0.98
        amount = float(balance_info[trade_coin]['free'])
        fs.okex_place_order(myOKEX, symbol, amount, price, 'sell')
        # 02\还币(USDT)
        fs.okex_repayment(myOKEX, symbol, base_coin)
    # 第六种情况：平空仓
    elif signal_trade == 'closing' and signal_last == 'short':
        # 01\下买单
        price = ticker_info['ask'] * 1.02
        amount = int(float(balance_info[base_coin]['free']) / price * 10**8) / 10**8
        fs.okex_place_order(myOKEX, symbol, amount, price, 'buy')
        # 02\还币(BTC)
        fs.okex_repayment(myOKEX, symbol, trade_coin)
    else: continue

    signal_last = signal_trade
    signal_trade = 'nothing'