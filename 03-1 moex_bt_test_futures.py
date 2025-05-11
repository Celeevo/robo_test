from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import backtrader as bt
from moex_store import MoexStore

def main():
    tf = '30m'
    contracts = ['EuM4', 'SiU3']
    datas = []
    store = MoexStore()

    for sec_id in contracts:
        fromdate = store.futures.prevexpdate(sec_id)
        todate = store.futures.expdate(sec_id)
        datas.append(store.getdata(sec_id=sec_id,
                             fromdate=fromdate,
                             todate=todate,
                             tf=tf,
                             name=sec_id))

    cerebro = bt.Cerebro()
    for data in datas:
         cerebro.adddata(data)
    cerebro.run()
    cerebro.plot()

if __name__ == '__main__':
    main()