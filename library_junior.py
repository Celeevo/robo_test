import time
import backtrader as bt
from datetime import datetime
import backtrader.indicators as btind
from logger_config import logger

class JuniorStrat(bt.Strategy):
    params = dict(
        ma_period=None,
    )
    def __init__(self):
        self.isLive = False  # Сначала будут приходить исторические данные
        self.ma = btind.EMA(period=self.p.ma_period)
        self.signal = self.data.close > self.ma

    def next(self):
        if not self.isLive:
            return

        print("Мы в NEXT()")

        # logger.info(
        print(
            f'LIVE-D-T-O-H-L-C-V-MA: {self.isLive}, {bt.num2date(self.data.datetime[0])}, '
            f'{self.data.open[0]}, {self.data.high[0]}, {self.data.low[0]}, '
            f'{self.data.close[0]}, {self.data.volume[0]}, {self.ma[0] = }')

    def notify_data(self, data, status, *args, **kwargs):
        """Изменение статуса приходящих баров"""
        data_status = data._getstatusname(status)  # Получаем статус (только при LiveBars=True)
        print(f'DATA Notification: Data-Status: {data.p.dataname}-{data_status}')
        if kwargs:
            for k, v in kwargs.items():
                print(f'Сообщение из QKData: {v}')
        # if 'H' in data.p.name:
        self.isLive = data_status == 'LIVE'
        print(f'{data.p.dataname} live? = {self.isLive}')

    def stop(self):
        super(JuniorStrat, self).stop()
