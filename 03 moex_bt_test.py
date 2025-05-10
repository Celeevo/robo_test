from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
from datetime import datetime
from datetime import timedelta

import backtrader as bt
from moex_store import MoexStore
# import datetime

def runstrat():
    contracts = ['EuM5',]
    contracts = ['SBER',]
    datas = []
    for sec_id in contracts:
        tf = '15m'
        store = MoexStore()
        # fromdate = store.futures.prevexpdate(sec_id)
        fromdate = datetime.today() - timedelta(days=30)
        todate = datetime.today()
        # todate = store.futures.expdate(sec_id)
        # data = store.getdata(sec_id=sec_id,
        datas.append(store.getdata(sec_id=sec_id,
                             fromdate=fromdate,
                             todate=todate,
                             tf=tf,
                             name=sec_id))


if __name__ == '__main__':
    runstrat()