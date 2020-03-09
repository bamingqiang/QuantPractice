import pandas as pd
from datetime import datetime, timedelta
import time


def next_run_time(time_interval, ahead_time=1):
    """计算最近一次获取交易K线数据时间点（邢大编写）

    :argument
        time_interval: string, 获取数据频次间隔时间，以“数字 + m”形式，表示多少分钟，例：15m
        ahead_time: 预留的空余时间以做好准备：若现在距离目标时间太短（小于ahead_time + 1秒）则跳过一次

    :return
        target_time: 最近一次获取交易所K线数据计算交易信号的时间，与现在时间至少间隔两秒；

    """
    if time_interval.endswith('m'):
        now_time = datetime.now()
        time_interval = int(time_interval.strip('m'))

        target_minute = (int(now_time.minute / time_interval) + 1) * time_interval
        if target_minute < 60:
            target_time = now_time.replace(minute=target_minute, second=0, microsecond=0)
        else:
            if now_time.hour == 23:
                target_time = now_time.replace(hour=0, minute=0, second=0, microsecond=0)
                target_time += timedelta(days=1)
            else:
                target_time = now_time.replace(hour=now_time.hour + 1, minute=0, second=0, microsecond=0)

        # sleep直到靠近目标时间之前
        if (target_time - datetime.now()).seconds < ahead_time + 1:  # 与现在时间至少间隔两秒；
            target_time += timedelta(minutes=time_interval)
        return target_time


def get_candle_data(exchange, time_interval, symbol, end_time):
    """获取实时数据并验证

    :argument
        exchange: 获取数据的交易所
        time_interval: string, K线周期
        symbol: string, K线币对，“/”分隔，例：'BCT/USDT'
        end_time: datetime.datetime 数据的截止K线的结束时间，用于验证数据

    :return
        df: pandas.DataFrame，指定交易所和币对的K线数据
            'candle_begin_time_GMT8'： pd.datetime, 北京时间
            'open': float
            'high': float
            'low': float
            'close': float
            'volume': float
        None: 数据不合格时返回
    """
    try:
        df = pd.DataFrame(exchange.fetch_ohlcv(symbol, time_interval, since=0), dtype=float)
        df.rename(columns={0: 'UTC', 1: 'open', 2: 'high', 3: 'low', 4: 'close', 5: 'volume'}, inplace=True)
        df['candle_begin_time_GMT8'] = pd.to_datetime(df['UTC'], unit='ms') + timedelta(hours=8)
        df = df[['candle_begin_time_GMT8', 'open', 'high', 'low', 'close', 'volume']]
        # 验证数据是否包含最新一根K线，以及是否包含多余一根K线（K线时间未完成）
        if (df.iat[-1, 0] + timedelta(minutes=int(time_interval.strip('m')))) > end_time:
            df = df[0:-1]  # 去除最后一根多余K线
        if (df.iat[-1, 0] + timedelta(minutes=int(time_interval.strip('m')))) != end_time:
            return  # 最后一根K线不是最近一根，获取的不是最新数据，返回None
        return df
    except Exception as e:
        print('Can not get data.')
        return


def get_brin_signal(candle_data, period_interval=100, std_times=2):
    """按布林线策略计算交易信号

    根据传入数据，按照布林策略计算交易信号，只需计算最后一根K线的信号即可

    :argument
        candle_data: pandas.DataFrame，指定交易所和币对的K线数据，记录数必须大于period_interval
            'candle_begin_time_GMT8'： pd.datetime, 北京时间
            'open': float
            'high': float
            'low': float
            'close': float
            'volume': float
        period_interval: int 布林策略需要的每周期K线根数
        std_times: int 布林策略的标准差倍数

    :return
        long: 开多仓；
        short: 开空仓；
        closing: 平仓；
        nothin: 无操作
    """

    signal_trade = {1.0: 'long', -1.0: 'short', 0.0: 'closing', 9: 'nothing'}

    if len(candle_data) < period_interval:
        # raise ('K线数据量不足，无法计算买卖信号。')
        print('K线数据量不足，无法计算买卖信号。')
        return 'nothing'

    # 1. 算出三条线, upper/middle/lower
    # 标准差只有第period_interval(标准差计算的K线个数)，标准差数据才是准确的，之前的K线的标准差不需要计算了
    candle_data['std'] = candle_data['close'].rolling(period_interval).std(ddof=0)
    candle_data['middle'] = candle_data['close'].rolling(period_interval).mean()
    candle_data['upper'] = candle_data['middle'] + candle_data['std'] * std_times
    candle_data['lower'] = candle_data['middle'] - candle_data['std'] * std_times

    # 2. 确定多空平信号，只需要确定最后一根K线是否产生信号即可。
    # candle_data['signal'] = pd.NaT
    # long
    c1 = candle_data['close'] > candle_data['upper']
    c2 = candle_data['close'].shift(1) < candle_data['upper']
    candle_data.loc[c1 & c2, 'signal'] = 1.0
    # long closing
    c1 = candle_data['close'] < candle_data['middle']
    c2 = candle_data['close'].shift(1) > candle_data['middle']
    candle_data.loc[c1 & c2, 'signal'] = 0.0
    # short
    c1 = candle_data['close'] < candle_data['lower']
    c2 = candle_data['close'].shift(1) > candle_data['lower']
    candle_data.loc[c1 & c2, 'signal'] = -1.0
    # short closing
    c1 = candle_data['close'] > candle_data['middle']
    c2 = candle_data['close'].shift(1) < candle_data['middle']
    candle_data.loc[c1 & c2, 'signal'] = 0.0

    candle_data['signal'].fillna(value=9, inplace=True)

    return signal_trade[candle_data.iat[-1, -1]]  # 只要最后一根K线的信号


def place_order(exchange, symbol, amount, price, side):
    """下单

    只下限价单，不下市价单；只下“高级限价单”中的“全部成交或立即取消”（FillOrKill）
    保证资金不被挂单占用。而且是以市价浮动2%的价格下单，成功成交概念大。

    :param exchange: 交易所
    :param symbol: string; 交易币对，以“/”分隔，BTC/USDT
    :param amount: float; 交易数量
    :param price: float; 交易价格
    :param side: sting; buy（买入）或sell（卖出）
    :return:
        order_id：下单成功，返回订单号
        None： 下单失败
    """
    for i in range(5):
        try:
            params = {'client_oid': '',
                      'type': 'limit',
                      'side': side,
                      'instrument_id': symbol.replace('/', '-'),
                      'order_type': 2,
                      'margin_trading': 2,
                      'price': price,
                      'size': amount}
            order_info = exchange.margin_post_orders(params)
            if order_info['result']:
                return order_info['order_id']
        except Exception as e:
            time.sleep(1)  # 1秒后重试
    return  # 否则，返回None


# --------助教，下面两个函数没有使用----------
def judge_signal_rationality(signal, signal_last):
    """判断交易信号的合理性

    根据最近一次交易类型，判断本次计算得出的交易类型是否合理可行。如：最近一次为short，本次就不能为short或long。

    :param signal: 被判断的交易信号（short, long, closing）
    :param signal_last: 最近一次成功交易类型（short, long, closing）
    :return:
        True: 合理，可执行
        False: 不合理，不予执行
    """
    rationality_100 = {'long': 'closing',
                       'short': 'closing',
                       'closing': 'long_short'}
    if signal not in ('long', 'short', 'closing'):
        return False
    if signal_last in rationality_100[signal]:
        return True
    else:
        return False


def judge_signal_on_balance(exchange, symbol, account_type, settings, signal_trade, signal_trade_last):
    """根据余额判断交易是否可行

    开多仓，basecoin余额必须足够；开空仓，tradecoin必须足够；平仓与此类似。

    Args:
        exchange: 使用ccxt创建的交易所
        symbol: 交易币对，BTC/USDT形式，以“/”分隔
        settings: 用户配置类，取其trade_coin_min（允许交易的最小值）
        account_type: 账户类型，spot/margin/future/swap
        signal_trade: 计算的交易信号，'long', 'short', 'closing'三者之一；
        signal_trade_last: 最近一次交易类型， 'long', 'short', 'closing'三者之一；

    Return:
        True: 余额足够，交易可行
        False: 余额不足，无法交易
    """

    trade_coin = symbol.split('/')[0]
    base_coin = symbol.split('/')[-1]
    balance_info = exchange.fetch_balance({'type': account_type})
    ticker_info = exchange.fetch_ticker(symbol)
    if (signal_trade == 'long' and signal_trade_last == 'closing') or \
            (signal_trade == 'closing' and signal_trade_last == 'short'):
        # 判断USDT是否足够购买最少0.001个比特币
        condition1 = (balance_info[symbol][base_coin]['free'] / (ticker_info['ask'] * 1.02)) > settings.trade_coin_min
        if condition1: return True
    elif (signal_trade == 'short' and signal_trade_last == 'closing') or \
            (signal_trade == 'closing' and signal_trade_last == 'long'):
        condition1 = balance_info[symbol][trade_coin]['free'] > settings.okex_trade_coin_min
        if condition1: return True
    return False
