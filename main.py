import ccxt
from time import sleep
from datetime import datetime
import functions as fs
import message as msg
from setting import Settings

my_settings = Settings()

myOKEX = ccxt.okex3()
myOKEX.apiKey = ''
myOKEX.secret = ''
myOKEX.password = ''
myOKEX.proxies = {'http': 'socks5h://127.0.0.1:1080',
                  'https': 'socks5h://127.0.0.1:1080'}

# 初始化参数
symbol = 'BTC/USDT'
trade_coin = symbol.split('/')[0]
base_coin = symbol.split('/')[-1]
time_interval = '15m'   # 确定获取哪个时间周期的K线
signal_last = 'closing'  # 上一次交易类型，初始交易状态为平仓
buy_or_sell = ''
order_id = ''
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
    if signal_trade == 'nothing': continue

    # 根据signal_trade和上一次交易类型，确定下买单或下卖单
    signal_verification = {'long': {'long': 'nothing', 'short': 'buy', 'closing': 'buy'},
                           'short': {'long': 'sell', 'short': 'nothing', 'closing': 'sell'},
                           'closing': {'long': 'sell', 'short': 'buy', 'closing': 'nothing'}}
    buy_or_sell = signal_verification[signal_trade][signal_last]
    if buy_or_sell == 'nothing': continue

    # 4.下单
    # 4.1 获取账户余额信息，市场ticker信息，借币信息
    try:
        balance_info = myOKEX.fetch_balance({'type': 'margin'})[symbol]     # 币币杠杆户交易币对余额
        ticker_info = myOKEX.fetch_ticker(symbol)
    except Exception as e:
        print('Can not get account balance and tiker.')
        continue
    # 4.2 下买单、或下卖单
    if buy_or_sell == 'buy':
        if balance_info[base_coin]['free'] > 0:
            price = ticker_info['ask'] * 1.02
            amount = balance_info[base_coin]['free'] / price
            order_id = fs.place_order(myOKEX, symbol, amount, price, buy_or_sell)
        else:
            msg.send_dingding_msg('下买单失败，账户余额不足！')
            continue
    elif buy_or_sell == 'sell':
        if balance_info[trade_coin]['free'] > 0:
            price = ticker_info['bid'] * 0.98
            amount = balance_info[trade_coin]['free']
            order_id = fs.place_order(myOKEX, symbol, amount, price, buy_or_sell)
        else:
            msg.send_dingding_msg('下卖单失败，账户余额不足！')
            continue

    if not order_id is None:    # 如果下单成功，那么……
        sleep(10)   # 延时，
        # 发送钉钉
        params = {'instrument_id': symbol.replace('/', '-'), 'state': 2}
        order_info = myOKEX.margin_get_orders(params)[0]   #取最新的成交订单
        content = ''
        content += '下单成交！\n'
        content += '币对：' + order_info['instrument_id'] + '\n'
        content += '类型：' + buy_or_sell + '\n'
        content += '价格：' + order_info['price_avg'] + '\n'
        content += '数量：' + order_info['filled_size'] + '\n'
        content += '总额：' + order_info['filled_notional'] + '\n'
        content += '杠杆：' + '1' + '\n'
        content += '时间：' + order_info['created_at'] + '\n'
        content += '单号：' + order_info['order_id'] + '\n'
        msg.send_dingding_msg(content)

        signal_last = signal_trade
        signal_trade = 'nothing'
        buy_or_sell = ''
        order_id = ''