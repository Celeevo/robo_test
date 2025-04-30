from __future__ import (absolute_import, division, print_function, unicode_literals)
from datetime import datetime, time, timedelta
from BackTraderQuik.QKStore import QKStore
from logger_config import logger
import backtrader as bt
import backtrader.indicators as btind

class JuniorStrat(bt.Strategy):

    def __init__(self):
        self.isLive = False  # Сначала будут приходить исторические данные

    def next(self):
        if not self.isLive: # выходим, если идет чтение истории
            return

        logger.info(
            f'Обработка нового бара в next(). D-T-O-H-L-C-V: {bt.num2date(self.data.datetime[0])}, '
            f'{self.data.open[0]}, {self.data.high[0]}, {self.data.low[0]}, '
            f'{self.data.close[0]}, {self.data.volume[0]}')

    def notify_data(self, data, status, *args, **kwargs):
        """Изменение статуса приходящих баров"""
        data_status = data._getstatusname(status)  # Получаем статус (только при LiveBars=True)
        logger.info(f'Data Status: {data.p.dataname}-{data_status}')
        self.isLive = data_status == 'LIVE'

    def stop(self):
        super(JuniorStrat, self).stop()

def main():
    print(f'Время пошло, {datetime.now():%d.%m.%y %H:%M:%S}')

    dataname = 'QJSIM.SBER'
    # dataname = 'SPBFUT.MXM5'

    cerebro = bt.Cerebro(stdstats=False, quicknotify=True)
    store = QKStore()
    broker = store.getbroker()
    cerebro.setbroker(broker)  # Устанавливаем брокера
    # fromdate = (datetime.today() - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    fromdate = datetime.today().date()
    data = store.getdata(dataname=dataname, timeframe=bt.TimeFrame.Minutes, compression=1, fromdate=fromdate, live_bars=True)
    cerebro.adddata(data)
    cerebro.addstrategy(JuniorStrat)
    cerebro.run()



if __name__ == '__main__':
    main()