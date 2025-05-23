from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
from datetime import datetime, timedelta
import backtrader as bt
from moex_store import MoexStore

def main():
    tf = '1h'
    stocks = ['SBER', 'GAZP']
    datas = []
    store = MoexStore()
    cerebro = bt.Cerebro()

    for sec in stocks:
        fromdate = datetime.today() - timedelta(days=30)
        todate = datetime.today()
        data_feed = store.getdata(sec_id=sec,
                             fromdate=fromdate,
                             todate=todate,
                             tf=tf,
                             name=sec)
        datas.append(data_feed)

    for data in datas:
         cerebro.adddata(data)
    cerebro.run()
    cerebro.plot()

if __name__ == '__main__':
    main()