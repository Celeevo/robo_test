from datetime import datetime  # Дата и время
from QuikPy import QuikPy  # Работа с QUIK из Python через LUA скрипты QUIK#


def get_tiker_info_from_QUIK(qp_provider, class_code, sec) -> None:
    """Получение краткой информации об инструменте из QUIK

    :param QuikPy qp_provider: Провайдер QUIK
    :param str class_code: Код режима торгов
    :param str sec: Код тикера"""

    info = qp_provider.get_symbol_info(class_code, sec)
    if info:
        print(f'Информация об инструменте {sec} из QUIK:\n'
              f'  Короткое имя: {info["short_name"]}, \n'
              f'  Валюта: {info["face_unit"]}, \n'
              f'  Лот: {info["lot_size"]}, \n'
              f'  Шаг цены: {info["min_price_step"]}, \n'
              f'  Кол-во десятичных знаков: {info["scale"]}\n')
        return
    raise RuntimeError(f"QUIK не нашел информацию по инструменту {sec}")


def get_candles_from_QUIK(qp_provider, class_code, sec, tf) -> None:
    """Получение бар из провайдера

    :param QuikPy qp_provider: Провайдер QUIK
    :param str class_code: Код режима торгов
    :param str sec: Код тикера
    :param str tf: Временной интервал https://ru.wikipedia.org/wiki/Таймфрейм
    """

    time_frame, _ = qp_provider.timeframe_to_quik_timeframe(tf)  # Временной интервал QUIK
    print(f'Котировки {sec} на тайм-фрейме {tf} из QUIK:')
    history = qp_provider.get_candles_from_data_source(class_code, sec, time_frame)  # Получаем все бары из QUIK
    if not history or not isinstance(history, dict):
        raise RuntimeError('Функция get_candles_from_data_source() вернула None или не-словарь')
    bars = history.get('data')
    if not bars:  # None или []
        raise RuntimeError(f"В ответе от QUIK нет котировок для {sec}: {history}")

    print('DATE\t\tTIME\tOPEN\tHIGH\tLOW\t\tCLOSE\tVOLUME')

    for bar in history['data']:
        dt = bar['datetime']
        dt_obj = datetime(dt['year'], dt['month'], dt['day'], dt['hour'], dt['min'], dt['sec'])

        date_str = dt_obj.strftime('%d.%m.%y')  # 30.04.2025
        time_str = dt_obj.strftime('%H:%M')  # 17:32

        print(f'{date_str}\t{time_str}\t{bar["open"]}\t{bar["high"]}\t'
              f'{bar["low"]}\t{bar["close"]}\t{int(bar["volume"])}')



if __name__ == '__main__':  
    qp_provider = QuikPy()  # Подключение к локальному запущенному терминалу QUIK
    class_code = 'QJSIM'    # 'QJSIM' используется в демо-QUIK - это аналог TQBR в обычном QUIK 
    sec = 'SBER'           # 'SPBFUT' 'MXM5'
    tf = 'M60'              # Значения https://ru.wikipedia.org/wiki/Таймфрейм
    get_tiker_info_from_QUIK(qp_provider, class_code, sec)
    get_candles_from_QUIK(qp_provider, class_code, sec, tf)
    qp_provider.close_connection_and_thread()

