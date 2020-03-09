class Settings():
    """用户配置信息类

    所有的配置信息，都存放在这个类中，实现程序功能与配置相分离

    Contents:
        client_oid，由您设置的订单ID来识别您的订单 ，类型为字母（大小写）+数字或者纯字母（大小写），1-32位字符
        交易类型：6位，不足用0代替（下同）spot margin future swap
        交易信号：1位，l\s\c
        交易币对：10位，BTC-USDT
        交易时间：8位，北京时间
        流水号  ：3位，
        例如： marginl00BTC/USDT20200303001

    """
    def __init__(self):

        self.okex_entry = {'apikey': '',
                              'secret': '',
                              'password': ''}
        self.proxies = {'http': 'socks5h://127.0.0.1:1080',
                        'https': 'socks5h://127.0.0.1:1080'}

        self.signal_trade = {1.0: 'long', -1.0: 'short', 0.0: 'closing', 9: 'nothing'}
        self.lever_times = 3  # 杠杆倍数

        # 100%全仓资金策略下，根据多空平持仓情况，判断可行的交易信号是否正确
        self.judge_trade_signal_100 = {'long': 'closing',
                                       'short': 'closing',
                                       'closing': 'long_short'}
        # 与交易所有关的信息，以交易所名称为前缀，例：okex_xxxx
        self.okex_trade_coin_min = 0.001  # 最小交易数量

        # 与策略所有关的信息，以策略名称为前缀，例：brin_xxxx