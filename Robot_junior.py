from __future__ import (absolute_import, division, print_function, unicode_literals)
from datetime import datetime, time, timedelta
from BackTraderQuik.QKStore import QKStore
import library_junior as lib
import backtrader as bt

# Предыдущий файл Robot12_18-06-23, этот оптимизирован 20/07/23
# оптимизация 17-09-2023, предыдущие в файле Robot12_20-07-23
# 18-11-23: вместо затягивания баров с начала контракта - 15 дней, тянем за последние 3 дня
# (чтобы при запуске в понедельник попала пятница)
# 08-12-23: пересчет после ужасной серии минусов подряд, файл mix_MINUTES30_AE4_23-12-08_v0.xlsx
# 11-(4, 5, 4)-6-23-9
# 27-03-24: переходим на ТФ 15 минут: 7-(7,9,8)-11-11-5. Запущен 29.03.24 в 10:02
# 02-05-24: 6-(6,11,8)-5-10-5 volume 350
# 05-05-24: 6-(4, 25, 8)-8-8-5-4
# 16-05-24: 6-(4, 25, 8)-10-8-5-4
# В связи с печальными, мягко говоря, результатами, 06-08-24 меня параметры на 8-(4, 12, 8)-8-12-5-5
# 22-09-24: 7-(6, 13, 7)-8-11-5-9
# 18-10-24: 6-(9, 17, 10)-12-5-2, use_local_extr=False
# 10-01-25: переход на MIX - 36-35-(9, 28, 15)
# 23-01-25: 28-26-(4, 30, 4)
# 30-01-25: trail_amount=2 -> 10
# 24-03-25: 8-15-40-(4, 25, 5)-MIX, 36-31-(6, 23, 15)-7-6-MXI
# 20-04-25: risk-check_bar-rsi-entry_ma-exit_ma-macd_pp-rsi_filter_for_entry-asset - 5-6-12-27-40-(4, 15, 6)-True-MIX

def main():
    print(f'Время пошло, {datetime.now():%d.%m.%y %H:%M:%S}')

    sec = 'SBER'
    sec = 'MXM5'
    class_code = 'QJSIM'
    class_code = 'TQBR'
    class_code = 'SPBFUT'

    param = dict(ma_period=20)


    cerebro = bt.Cerebro()  # maxcpus=1)  # , maxcpus=2) optreturn=False, tradehistory=False
    store = QKStore()
    broker = store.getbroker()  # FirmId='SPBFUT589000', TradeAccountId='SPBFUTL9hxr', use_positions=True
    # broker = store.getbroker(FirmId='SPBFUT000000', TradeAccountId='SPBFUT000mm')
    # Prod - Фирма: SPBFUT589000 Счет: SPBFUTL9hxr
    # Demo - Фирма: SPBFUT000000  Счет: SPBFUT000mm
    # clientCode = 'SPBFUT0016z'  # 'SPBFUTL9hxr' SPBFUT0016z # Код клиента (присваивается брокером)
    # firmId = 'SPBFUT000mm'  # 'SPBFUT589000' SPBFUT000000 # Код фирмы (присваивается брокером)

    cerebro.setbroker(broker)  # Устанавливаем брокера
    dataname = f'{class_code}.{sec}'
    date_needed = (datetime.today() - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    data = store.getdata(dataname=dataname, timeframe=bt.TimeFrame.Minutes, compression=1, fromdate=date_needed, LiveBars=True)
    cerebro.adddata(data)
    cerebro.addstrategy(lib.JuniorStrat, **param)
    cerebro.run()  # tradehistory=True,


    # symbol = [f'SPBFUT.{x}' for x in exch]
    # print(symbol)
    #
    # data_needed = (datetime.today() - timedelta(days=10)).replace(hour=0, minute=0, second=0, microsecond=0)
    # print(data_needed)
    # data1 = store.getdata(dataname=symbol[0], timeframe=bt.TimeFrame.Minutes, compression=30,  # name='RIZ2',
    #                      fromdate=data_needed, LiveBars=True)  # Исторические и новые бары за все время
    # data2 = store.getdata(dataname=symbol[1], timeframe=bt.TimeFrame.Minutes, compression=60,  # name='RIZ2',
    #                      fromdate=data_needed, LiveBars=True)  # Исторические и новые бары за все время
    #
    # cerebro.addsizer(lib.SizeFinder)
    # cerebro.adddata(data1)
    # cerebro.adddata(data2)
    # cerebro.addstrategy(lib.TrioVesperFin, **param_mix)
    # cerebro.addstrategy(lib.UniSec, **param_mxi)
    # cerebro.run(stdstats=False, quicknotify=True, maxcpus=2)  # tradehistory=True,


if __name__ == '__main__':
    main()