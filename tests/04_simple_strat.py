from __future__ import (absolute_import, division, print_function, unicode_literals)
from datetime import datetime, time, timedelta
from BackTraderQuik.QKStore import QKStore
from logger_config import logger
import backtrader as bt
import backtrader.indicators as btind

class VerySimpleJuniorStrat(bt.Strategy):

    def __init__(self):
        """Статус полученного бара: False - исторический, True - живой"""
        self.is_live = False
        self.entry_bar = 0

    def next(self):
        if not self.is_live: # выходим, если идет чтение истории
            return

        logger.info(
            f'Обработка нового бара в next(). '
            f'D-T-O-H-L-C-V: {bt.num2date(self.data.datetime[0])}, '
            f'{self.data.open[0]}, {self.data.high[0]}, {self.data.low[0]}, '
            f'{self.data.close[0]}, {self.data.volume[0]}')

        logger.info(f'Позиция: {self.getposition().size}, текущ. бар: {len(self)}')

        if not self.position.size:
            if self.data.close[0] <= self.data.open[0] and self.data.close[-1] <= self.data.open[-1]:
                logger.info(f'Сигнал в Шорт!')
                self.sell(size=10)
            elif self.data.close[0] >= self.data.open[0] and self.data.close[-1] >= self.data.open[-1]:
                self.bo = self.buy(self.datas[0], exectype=bt.Order.Limit,
                                   price=self.data.close[0], name='long', size=10)
                logger.info(f'Сигнал в Лонг!')
            self.entry_bar = len(self)
        elif len(self) >= self.entry_bar + 2:
            logger.info(f'Сигнал на выход! Позиция: {self.getposition().size}, бар входа: {self.entry_bar}, текущ. бар: {len(self)}')
            self.close()

    def notify_data(self, data, status, *args, **kwargs):
        """Изменение статуса приходящих баров"""
        data_status = data._getstatusname(status)
        logger.info(f'Источник данных: {data.p.dataname}, статус: {data_status}')
        self.is_live = data_status == 'LIVE'

    def stop(self):
        super(VerySimpleJuniorStrat, self).stop()


def main():
    print(f'Тест интеграции QUIK и Backtrader, время: {datetime.now():%d.%m.%y %H:%M:%S}')

    dataname = 'QJSIM.SBER'
    # dataname = 'EQRP_INFO.SBER'
    # dataname = 'SPBFUT.MMM5'

    cerebro = bt.Cerebro(stdstats=False, quicknotify=True)
    store = QKStore()
    broker = store.getbroker()
    cerebro.setbroker(broker)  # Устанавливаем брокера
    # fromdate = (datetime.today() - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    fromdate = datetime.today().date()
    data = store.getdata(dataname=dataname, timeframe=bt.TimeFrame.Minutes,
                         compression=1, fromdate=fromdate, live_bars=True)
    cerebro.adddata(data)
    cerebro.addstrategy(VerySimpleJuniorStrat)
    cerebro.run()



if __name__ == '__main__':
    main()