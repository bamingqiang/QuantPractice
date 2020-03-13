import pandas as pd
from datetime import datetime, timedelta
from math import ceil
import time
import message as msg


def next_run_time(time_interval, ahead_time=1, dif_minute=0):
    """计算最近一次获取交易K线数据时间点（邢大编写）

    :argument
        time_interval: string, 获取数据频次间隔时间，以“数字 + m”形式，表示多少分钟，例：15m
        ahead_time: 预留的空余时间以做好准备：若现在距离目标时间太短（小于ahead_time + 1秒）则跳过一次
        dif_minute: 与整倍的time_interval时间错开的时间分钟数
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
    for i in range(10):
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
            if i == 9:
                content = '获取K线数据失败达到10次，重新开始循环！\n'
                content += '退出的本次时间：' + datetime.strftime(end_time, '%Y-%m-%d %H:%M:%S')
                msg.send_dingding_msg(content)
                print(e)
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
        # print('K线数据量不足，无法计算买卖信号。')
        return 'nothing'

    # 1. 算出三条线, upper/middle/lower
    # 标准差只有第period_interval(标准差计算的K线个数)，标准差数据才是准确的，之前的K线的标准差不需要计算了
    candle_data['std'] = candle_data['close'].rolling(period_interval).std(ddof=0)
    candle_data['middle'] = candle_data['close'].rolling(period_interval).mean()
    candle_data['upper'] = candle_data['middle'] + candle_data['std'] * std_times
    candle_data['lower'] = candle_data['middle'] - candle_data['std'] * std_times

    # 2. 确定多空平信号，只需要确定最后一根K线是否产生信号即可。
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


def okex_time_trans(time):
    """时间格式转换

    OKEX交易所API返回的UTC0的string型时间，如'2020-03-10T13:00:53.000Z'，
    转换为string型的北京时间，且形式为'2020-03-10 21:00:53'

    :param time: OKEX交易所API返回的UTC0的string型时间
    :return: string型的北京时间
    """
    t = datetime.strptime(time[:-5], '%Y-%m-%dT%H:%M:%S') + timedelta(hours=8)
    return datetime.strftime(t, '%Y-%m-%d %H:%M:%S')


def okex_place_order(exchange, symbol, amount, price, side):
    """下单

    最多尝试5次，只下限价单，不下市价单；只下“高级限价单”中的“全部成交或立即取消”（FillOrKill）
    保证资金不被挂单占用。而且是以市价浮动2%的价格下单，成功成交概率大。

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
                # 发送钉钉
                params = {'instrument_id': symbol.replace('/', '-'), 'state': 2}
                order_info = exchange.margin_get_orders(params)[0]   #取最新的成交订单
                content = ''
                content += '下单成交！\n'
                content += '币对：' + order_info['instrument_id'] + '\n'
                content += '类型：' + side + '\n'
                content += '价格：' + order_info['price_avg'] + '\n'
                content += '数量：' + order_info['filled_size'] + '\n'
                content += '总额：' + order_info['filled_notional'] + '\n'
                content += '时间：' + okex_time_trans(order_info['created_at']) + '\n'
                content += '单号：' + order_info['order_id'] + '\n'
                msg.send_dingding_msg(content)
                # 返回下单结果
                return order_info['order_id']
        except Exception as e:
            print(e)
            continue
            # time.sleep(1)  # 1秒后重试
    return  # 否则，返回None


def okex_borrow(exchange, symbol, coin, lever_times):
    """借币，适用于OKEX交易所，币币杠杆账户

    根据币币杠杆账户余额、以及允许的杠杆（交易所允许的杠杆倍数和个人设定的杠杆
    倍数取最小值），来确定可借币的数量，并完成借币操作

    :param exchange: 交易所
    :param symbol: 交易币对
    :param coin: 需要借的币
    :param lever_times: 允许的最大杠杆倍数
    :return:
        borrow_id: 借币订单号
        None: 借币失败
    """
    for i in range(5):
        try:
            # 获取杠杆配置信息
            params = {'instrument_id': symbol.replace('/', '-')}
            lever_info = exchange.margin_get_accounts_instrument_id_availability(params)
            # 确定杠杆倍数
            lever_time_available = float(lever_info[0]['currency:' + coin]['leverage'])
            lever = min(lever_times, lever_time_available)  # lever int型变量
            # 确定借币数量
            f1 = float(lever_info[0]['currency:' + coin]['available'])          # 最大可借币数
            f2 = lever_time_available - 1.0                                     # 最大可借杠杆倍数（-1为本金数量为1倍）
            borrow_amount = int(f1 / f2 * (lever - 1) * 100000000) / 100000000  # 取整小数点后前8位，避免数值过长出错
            # 借币
            params = {'instrument_id': symbol.replace('/', '-'), 'currency': coin, 'amount': str(borrow_amount)}
            borrowed_info = exchange.margin_post_accounts_borrow(params)
            if not borrowed_info['result']:  # 如果借币失败，那么…………
                content = 'borrowed failed! Can not borrowed from exchange!'
                msg.send_dingding_msg(content)
                return
            # 发送钉钉借币成功消息
            params = {'instrument_id': symbol.replace('/', '-'), 'state': 0}  # 获取借币信息
            info = exchange.margin_get_accounts_instrument_id_borrowed(params)
            content = '借币成功！\n'
            content += '币种：' + info[0]['currency'] + '\n'
            content += '数量：' + info[0]['amount'] + '\n'
            content += '币对：' + info[0]['instrument_id'] + '\n'
            content += '时间：' + okex_time_trans(info[0]['timestamp']) + '\n'
            content += '单号：' + info[0]['borrow_id'] + '\n'
            content += '限时：' + okex_time_trans(info[0]['force_repay_time']) + '\n'
            content += '利率：' + info[0]['rate'] + '\n'
            msg.send_dingding_msg(content)
            # 返回结果
            return borrowed_info['borrow_id']
        except Exception as e:
            if i == 4:
                content = '借币报错次数达到5次，失败！请检查代码或网络。'
                msg.send_dingding_msg(content)
            print(e)
            continue
    return


def okex_repayment(exchange, symbol, coin):
    """还币，适用于OKEX交易所，币币杠杆账户，且只还最近的一笔未还清借款。

    :param exchange: 交易所
    :param symbol: 交易币对，以‘/’连接，例“BTC/USDT”
    :param coin: 需要还的币种

    :return:
        repayment_id: str，订单号；
        exit: 任意原因导致还款失败，则退出程序。
    """

    try:
        params = {'instrument_id': symbol.replace('/', '-'), 'state': 0}  # 获取借币信息
        info = exchange.margin_get_accounts_instrument_id_borrowed(params)
        info_balance = exchange.fetch_balance({'type': 'margin'})[symbol]
        f = float(info[0]['amount']) + float(info[0]['interest'])  # 还币，成功前提：只有一笔未还借款。
        amount = ceil(f * 100000000) / 100000000     # 保留小点后8位，进一
        if float(info_balance[coin]['free']) < amount:
            content = '账户余额不足，无法还币，请及时补充余额减少利息！程序退出！'
            msg.send_dingding_msg(content)
            exit()
        params = {'instrument_id': symbol.replace('/', '-'), 'currency': coin, 'amount': amount}
        info_repay = exchange.margin_post_accounts_repayment(params)    # 还币
        if info_repay['result']:
            return info_repay['repayment_id']
        elif not info_repay['result']:
            content = '还款结果返回False，还款不成功，程序退出。请及时还币减少利息，再行启动策略程序！'
            msg.send_dingding_msg(content)
            exit()
        return
    except Exception as e:
        content = 'OKEX交易所还币函数异常，请及时还币后，再行启动策略程序。'
        msg.send_dingding_msg(content)
        print(e)
        exit()


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
