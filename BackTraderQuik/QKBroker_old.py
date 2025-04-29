import collections
from datetime import datetime
import time

from backtrader import BrokerBase
from backtrader.utils.py3 import with_metaclass
from backtrader import Order

from BackTraderQuik import QKStore


class MetaQKBroker(BrokerBase.__class__):
    def __init__(cls, name, bases, dct):
        super(MetaQKBroker, cls).__init__(name, bases, dct)  # Инициализируем класс брокера
        QKStore.BrokerCls = cls  # Регистрируем класс брокера в хранилище QUIK


class QKBroker(with_metaclass(MetaQKBroker, BrokerBase)):
    """Брокер QUIK"""
    # TODO Сделать обертку для поддержки множества счетов и брокеров
    # Обсуждение решения: https://community.backtrader.com/topic/1165/does-backtrader-support-multiple-brokers
    # Пример решения: https://github.com/JacobHanouna/backtrader/blob/ccxt_multi_broker/backtrader/brokers/ccxtmultibroker.py

    params = (
        ('use_positions', True),  # При запуске брокера подтягиваются текущие позиции с биржи
        ('Lots', True),  # Входящий остаток в лотах (задается брокером)
        ('ClientCode', '1059203'),  # Код клиента '1059203' '1220'-Demo
        ('FirmId', 'SPBFUT589000'),  # Фирма SPBFUT589000 SPBFUT000000 NC0011100000
        ('TradeAccountId', 'SPBFUTL9hxr'),  # Счет SPBFUTL9hxr SPBFUT0016z
        ('LimitKind', 0),  # День лимита
        ('CurrencyCode', 'SUR'),  # Валюта
        ('IsFutures', True),  # Фьючерсный счет
    )

    def __init__(self, **kwargs):
        super(QKBroker, self).__init__()
        self.store = QKStore(**kwargs)  # Хранилище QUIK
        self.notifs = collections.deque()  # Очередь уведомлений о заявках
        self.tradeNums = dict()  # Список номеров сделок по тикеру для фильтрации дублей сделок
        # self.startingcash = self.cash = 0  # Стартовые и текущие свободные средства по счету
        # self.startingvalue = self.value = 0  # Стартовый и текущий баланс счета
        self.cash = 0  # Стартовые и текущие свободные средства по счету
        self.value = 0  # Стартовый и текущий баланс счета
        # self.already_printed = None

    def start(self):
        super(QKBroker, self).start()
        # self.startingcash = self.cash = self.getcash()  # Стартовые и текущие свободные средства по счету
        # self.startingvalue = self.value = self.getvalue()  # Стартовый и текущий баланс счета
        # ВНИМАНИЕ!!! Закоментил 2 строки ниже, не понимаю зачем они нужны на старте, проверяем корректность без них!!!
        # self.cash = self.getcash()  # Стартовые и текущие свободные средства по счету
        # self.value = self.getvalue()  # Стартовый и текущий баланс счета
        if self.p.use_positions:  # Если нужно при запуске брокера получить текущие позиции на бирже
            self.store.GetPositions(self.p.ClientCode, self.p.FirmId, self.p.LimitKind, self.p.Lots,
                                    self.p.IsFutures)  # То получаем их
        self.store.qpProvider.OnConnected = self.store.OnConnected  # Соединение терминала с сервером QUIK
        self.store.qpProvider.OnDisconnected = self.store.OnDisconnected  # Отключение терминала от сервера QUIK
        self.store.qpProvider.OnTransReply = self.OnTransReply  # Ответ на транзакцию пользователя
        self.store.qpProvider.OnTrade = self.OnTrade  # Получение новой / изменение существующей сделки

    def getcash(self):
        """Свободные средства по счету"""
        if self.store.BrokerCls is not None:  # Если брокер есть в хранилище
            cash = self.store.GetMoneyLimits(self.p.ClientCode, self.p.FirmId, self.p.TradeAccountId, self.p.LimitKind,
                                             self.p.CurrencyCode, self.p.IsFutures)
            if cash is not None:  # Если свободные средства были получены
                self.cash = cash  # то запоминаем их
        return self.cash  # Возвращаем последние известные свободные средства

    def getvalue(self, datas=None):
        """Баланс счета"""
        if self.store.BrokerCls is not None:  # Если брокер есть в хранилище
            value = self.store.GetPositionsLimits(self.p.FirmId, self.p.TradeAccountId, self.p.IsFutures)
            if value is not None:  # Если баланс счета был получен
                self.value = value  # то запоминаем его
        return self.getcash() + self.value  # Возвращаем последний известный баланс счета

    def getposition(self, data, clone=True):
        pos = self.store.positions[
            data._dataname]  # Получаем позицию по тикеру или нулевую позицию если тикера в списке позиций нет
        if clone:  # Если нужно получить копию позиции
            pos = pos.clone()  # то создаем копию
        return pos  # Возвращаем позицию или ее копию

    def buy(self, owner, data, size, price=None, plimit=None, exectype=None, valid=None, tradeid=0, oco=None,
            trailamount=None, trailpercent=None, **kwargs):
        """Заявка на покупку"""
        commInfo = self.getcommissioninfo(
            data)  # По тикеру выставляем комиссии в заявку. Нужно для исполнения заявки в BackTrader
        order = self.store.PlaceOrder(self.p.ClientCode, self.p.TradeAccountId, owner, data, size, price, plimit,
                                      exectype, valid, oco, commInfo, True, **kwargs)
        print(
            f'{datetime.now():%H:%M:%S} QKBroker. Размещен BUY ордер ref {order.ref}, Size={size}, Price={price}, P-limit={plimit}')
        self.notifs.append(order.clone())  # Уведомляем брокера об отправке новой заявки на рынок
        return order

    def sell(self, owner, data, size, price=None, plimit=None, exectype=None, valid=None, tradeid=0, oco=None,
             trailamount=None, trailpercent=None, **kwargs):
        """Заявка на продажу"""
        commInfo = self.getcommissioninfo(
            data)  # По тикеру выставляем комиссии в заявку. Нужно для исполнения заявки в BackTrader
        order = self.store.PlaceOrder(self.p.ClientCode, self.p.TradeAccountId, owner, data, size, price, plimit,
                                      exectype, valid, oco, commInfo, False, **kwargs)
        print(
            f'{datetime.now():%H:%M:%S} QKBroker. Размещен SELL ордер ref {order.ref}, Size={size}, Price={price}, P-limit={plimit}')
        self.notifs.append(order.clone())  # Уведомляем брокера об отправке новой заявки на рынок
        return order

    def cancel(self, order):
        """Отмена заявки"""
        print(f'{datetime.now():%H:%M:%S} QKBroker. Отменяю ордер: {order.ref}')
        return self.store.CancelOrder(order)

    def get_notification(self):
        if not self.notifs:  # Если в списке уведомлений ничего нет
            return None  # то ничего и возвращаем, выходим, дальше не продолжаем
        return self.notifs.popleft()  # Удаляем и возвращаем крайний левый элемент списка уведомлений

    def next(self):
        self.notifs.append(None)  # Добавляем в список уведомлений пустой элемент
        # print(f'QKBroker. NEXT. {datetime.now():%H:%M:%S}')

    def stop(self):
        super(QKBroker, self).stop()
        self.store.qpProvider.OnConnected = self.store.qpProvider.DefaultHandler  # Соединение терминала с сервером QUIK
        self.store.qpProvider.OnDisconnected = self.store.qpProvider.DefaultHandler  # Отключение терминала от сервера QUIK
        self.store.qpProvider.OnTransReply = self.store.qpProvider.DefaultHandler  # Ответ на транзакцию пользователя
        self.store.qpProvider.OnTrade = self.store.qpProvider.DefaultHandler  # Получение новой / изменение существующей сделки
        self.store.BrokerCls = None  # Удаляем класс брокера из хранилища

    def OnTransReply(self, data):
        """Обработчик события ответа на транзакцию пользователя"""
        qkTransReply = data['data']  # Ответ на транзакцию
        transId = int(qkTransReply['trans_id'])  # Номер транзакции заявки
        if transId == 0:  # Заявки, выставленные не из автоторговли / только что (с нулевыми номерами транзакции)
            return  # не обрабатываем, пропускаем
        orderNum = int(qkTransReply['order_num'])  # Номер заявки на бирже
        try:  # Могут приходить другие заявки, не выставленные в автоторговле
            order: Order = self.store.orders[transId]  # Ищем заявку по номеру транзакции
        except KeyError:  # При ошибке
            print(f'Заявка {orderNum} на бирже с номером транзакции {transId} не найдена')
            return  # не обрабатываем, пропускаем
        self.store.orderNums[transId] = orderNum  # Сохраняем номер заявки на бирже
        # TODO Есть поле flags, но оно не документировано. Лучше вместо текстового результата транзакции разбирать по нему
        resultMsg = qkTransReply['result_msg']  # По результату исполнения транзакции (очень плохое решение)
        status = int(qkTransReply['status'])  # Статус транзакции
        if 'зарегистрирована' in resultMsg or status == 15:  # Если пришел ответ по новой заявке
            order.accept()  # Переводим заявку в статус Order.Accepted (регистрация новой заявки)
            self.notifs.append(order.clone())  # Уведомляем брокера о регистрации новой заявки
        # ВНИМАНИЕ! МОЯ ДОРАБОТКА!!! - добавил 'отвергнута':
        elif 'снята' in resultMsg or 'отвергнута' in resultMsg:  # Если пришел ответ по отмене существующей заявки
            print(f'{datetime.now():%H:%M:%S} QKBroker. OnTransReply. Заявка отклонена или снята биржей: {order.ref}')
            # print(f'{datetime.now():%H:%M:%S} QKBroker. OnTransReply. Снятая заявка: {order}')
            try:  # TODO Очень редко возникает ошибка: IndexError: array index out of range
                order.cancel()  # Переводим заявку в статус Order.Canceled (отмена существующей заявки)
            except (KeyError, IndexError):  # При ошибке
                order.status = Order.Canceled  # все равно ставим статус заявки Order.Canceled
            self.notifs.append(order.clone())  # Уведомляем брокера об отмене существующей заявки
            # ВНИМАНИЕ! МОЯ ДОРАБОТКА!!!
            # Для защиты от удаления моих стоп-лос заявок при снятии заявок exit from long/short
            # Проверяем - есть ли у отменяемой заявки привязка осо. У своих я привязку удаляю перед отменой.
            # self.store.OCOCheck(order)  # Проверяем связанные заявки - ЭТО ОРИГИНАЛ
            if order.info.oco:
                self.store.OCOCheck(order)
        elif status in (2, 4, 5, 10, 11, 12, 13, 14, 16):  # Транзакция не выполнена (ошибка заявки)
            if status == 4 and 'Не найдена заявка' in resultMsg or \
                    status == 5 and 'не можете снять' in resultMsg or 'Превышен лимит' in resultMsg:  # Не найдена заявка для удаления / Вы не можете снять данную заявку
                return  # то заявку не отменяем, выходим, дальше не продолжаем

            try:  # TODO Очень редко возникает ошибка: IndexError: array index out of range
                order.reject()  # Переводим заявку в статус Order.Reject
            except (KeyError, IndexError):  # При ошибке
                order.status = Order.Rejected  # все равно ставим статус заявки Order.Rejected
            self.notifs.append(order.clone())  # Уведомляем брокера об ошибке заявки
            self.store.OCOCheck(order)  # Проверяем связанные заявки
        elif status == 6:  # Транзакция не прошла проверку лимитов сервера QUIK
            try:  # TODO В BT очень редко при order.margin() возникает ошибка: IndexError: array index out of range
                order.margin()  # Переводим заявку в статус Order.Margin
            except (KeyError, IndexError):  # При ошибке
                order.status = Order.Margin  # все равно ставим статус заявки Order.Margin
            self.notifs.append(order.clone())  # Уведомляем брокера о недостатке средств
            self.store.OCOCheck(order)  # Проверяем связанные заявки

    def OnTrade(self, data):
        """
        Обработчик события получения новой / изменения существующей сделки.
        Выполняется до события изменения существующей заявки. Нужен для определения цены исполнения заявок.
        """
        qkTrade = data['data']  # Сделка в QUIK
        orderNum = int(qkTrade['order_num'])  # Номер заявки на бирже
        jsonOrder = self.store.qpProvider.GetOrderByNumber(orderNum)[
            'data']  # По номеру заявки в сделке пробуем получить заявку с биржи
        if isinstance(jsonOrder,
                      int):  # Если заявка не найдена, то в ответ получаем целое число номера заявки. Возможно заявка есть, но она не успела прийти к брокеру
            print(
                f'{datetime.now():%H:%M:%S} Заявка с номером {orderNum} не найдена на бирже с 1-ой попытки. Через 3 с будет 2-ая попытка')
            time.sleep(3)  # Ждем 3 секунды, пока заявка не придет к брокеру
            jsonOrder = self.store.qpProvider.GetOrderByNumber(orderNum)[
                'data']  # Снова пробуем получить заявку с биржи по ее номеру
            if isinstance(jsonOrder, int):  # Если заявка так и не была найдена
                print(f'Заявка с номером {orderNum} не найдена на бирже со 2-ой попытки')
                return  # то выходим, дальше не продолжаем

        transId = int(jsonOrder['trans_id'])  # Получаем номер транзакции из заявки с биржи
        if transId == 0:  # Заявки, выставленные не из автоторговли / только что (с нулевыми номерами транзакции)
            return  # не обрабатываем, пропускаем
        self.store.orderNums[
            transId] = orderNum  # Сохраняем номер заявки на бирже (может быть переход от стоп заявки к лимитной с изменением номера на бирже)
        try:  # Бывает, что трейдеры совмещают авто и ручную торговлю. Это делать нельзя, но кто это будет слушать?
            order: Order = self.store.orders[transId]  # Ищем заявку по номеру транзакции
        except KeyError:  # Если пришла заявка из ручной торговли, то заявки по номеру транзакции в автоторговле не будет, получим ошибку
            print(f'Заявка с номером {orderNum} и номером транзакции {transId} была выставлена не из торговой системы')
            print(f'Broker.OnTrade {qkTrade["sec_code"] = }, '
                  f'{int(qkTrade["qty"]) = }, {float(qkTrade["price"]) = }, '
                  f'Buy? = {qkTrade["flags"] & 0b100 == 0b100}')
            return  # выходим, дальше не продолжаем
        classCode = qkTrade['class_code']  # Код площадки
        secCode = qkTrade['sec_code']  # Код тикера
        dataname = f'{classCode}.{secCode}'  # self.store.ClassSecCodeToDataName(classCode, secCode)  # Получаем название тикера по коду площадки и коду тикера
        tradeNum = int(qkTrade['trade_num'])  # Номер сделки (дублируется 3 раза)
        if dataname not in self.tradeNums.keys():  # Если это первая сделка по тикеру
            self.tradeNums[dataname] = []  # то ставим пустой список сделок
        elif tradeNum in self.tradeNums[dataname]:  # Если номер сделки есть в списке (фильтр для дублей)
            return  # то выходим, дальше не продолжаем
        self.tradeNums[dataname].append(
            tradeNum)  # Запоминаем номер сделки по тикеру, чтобы в будущем ее не обрабатывать (фильтр для дублей)
        size = int(qkTrade[
                       'qty'])  # Абсолютное кол-во # if self.p.Lots:  # Если входящий остаток в лотах #     size = self.store.LotsToSize(classCode, secCode, size)  # то переводим кол-во из лотов в штуки
        if qkTrade['flags'] & 0b100 == 0b100:  # Если сделка на продажу (бит 2)
            size *= -1  # то кол-во ставим отрицательным
        price = float(qkTrade[
                          'price'])  # self.store.QKToBTPrice(classCode, secCode, float(qkTrade['price']))  # Переводим цену исполнения за лот в цену исполнения за штуку
        # 04-06-24
        # print(f'+++\n{datetime.now().time()} QKBroker.OnTrade: {secCode}, {orderNum = }, {tradeNum = }, {size = }, {price = }')
        try:  # TODO Очень редко возникает ошибка: IndexError: array index out of range
            dt = order.data.datetime[0]  # Дата и время исполнения заявки. Последняя известная
        except (KeyError, IndexError):  # При ошибке
            dt = datetime.now(QKStore.MarketTimeZone)  # Берем текущее время на рынке
        pos = self.getposition(order.data,
                               clone=False)  # Получаем позицию по тикеру или нулевую позицию если тикера в списке позиций нет
        psize, pprice, opened, closed = pos.update(size, price)  # Обновляем размер/цену позиции на размер/цену сделки
        order.execute(dt, size, price, closed, 0, 0, opened, 0, 0, 0, 0, psize, pprice)  # Исполняем заявку в BackTrader
        if order.executed.remsize:  # Если заявка исполнена частично (осталось что-то к исполнению)
            # 04-06-24
            print(f'{datetime.now().time()} QKBroker.OnTrade PARTIAL ORDER EXEC-I: {orderNum = }, {tradeNum = }, {transId} , {order.executed.remsize = }, {order.ref = }')
            if order.status != order.Partial:  # Если заявка переходит в статус частичного исполнения (может исполняться несколькими частями)
                order.partial()  # Переводим заявку в статус Order.Partial
                print(f'{datetime.now().time()} QKBroker.OnTrade PARTIAL ORDER EXEC-II: {order.getstatusname() = }')
                self.notifs.append(order.clone())  # Уведомляем брокера о частичном исполнении заявки
        else:  # Если заявка исполнена полностью (ничего нет к исполнению)
            order.completed()  # Переводим заявку в статус Order.Completed
            self.notifs.append(order.clone())  # Уведомляем брокера о полном исполнении заявки
            # Снимаем oco-заявку только после полного исполнения заявки
            # Если нужно снять oco-заявку на частичном исполнении, то прописываем это правило в ТС
            self.store.OCOCheck(order)  # Проверяем связанные заявки

    def get_multiplicator(self, sec_name):
        step_price_cost = float(
            self.store.qpProvider.GetParamEx("SPBFUT", sec_name, "STEPPRICE")["data"]["param_value"])
        step_price = float(
            self.store.qpProvider.GetParamEx("SPBFUT", sec_name, "SEC_PRICE_STEP")["data"]["param_value"])
        return step_price_cost / step_price

    def get_bayer_go(self, sec_name):
        # ГО покупателя
        return float(self.store.qpProvider.GetParamEx("SPBFUT", sec_name, "BUYDEPO")["data"]["param_value"])

    def get_seller_go(self, sec_name):
        return float(self.store.qpProvider.GetParamEx("SPBFUT", sec_name, "SELLDEPO")["data"]["param_value"])

    def get_futures_limits(self):
        # Фьючерсные лимиты. https://luaq.ru/getFuturesLimit.html
        try:
            if int(f'{datetime.now():%H}') == 7:  # !!! Уход от ошибки Futures limit returns nil утром
                return 0, 0, 0, 0, 0
            limits = self.store.qpProvider.GetFuturesLimit(self.p.FirmId, self.p.TradeAccountId, 0, "SUR")["data"]
            cbplimit = float(limits["cbplimit"])
            cbplplanned = float(limits["cbplplanned"])  # Плановые чистые позиции
            cbplused_for_positions = float(limits["cbplused_for_positions"])  # Тек чистые позиции (под откр. позиции)
            cbplused_for_orders = float(limits["cbplused_for_orders"])  # Текущие чистые позиции (под заявки)
            varmargin = float(limits["varmargin"])  # Вариационная маржа
        except Exception as err:  # При ошибке Futures limit returns nil
            print(f'QKBroker. QUIK не вернул фьючерсные лимиты с FirmId={self.p.FirmId}, '
                  f'TradeAccountId={self.p.TradeAccountId}. Проверьте правильность значений')
            cbplimit, cbplplanned, cbplused_for_positions, cbplused_for_orders, varmargin = 0, 0, 0, 0, 0
        return cbplimit, cbplplanned, cbplused_for_positions, cbplused_for_orders, varmargin

    def get_QUIK_position(self, sec_name):
        # Запрашиваем позицию по фьючерсу sec_name в Quik. https://luaq.ru/getFuturesHolding.html
        try:
            all_sec = self.store.qpProvider.GetFuturesHoldings()["data"]
            for row in all_sec:
                if row['sec_code'] == sec_name:
                    size = int(float(row["totalnet"]))
                    price = float(row["avrposnprice"])
                    print(f'{datetime.now():%H:%M:%S} QKBroker. get_QUIK_positions(): {size = }, {price = }')
                    return size, price
            # pos = self.store.qpProvider.GetFuturesHolding(self.p.FirmId, self.p.TradeAccountId, sec_name, 0)["data"]
            return 0, 0
        except Exception as err:  # При ошибке returns nil
            print(
                f'{datetime.now():%H:%M:%S} QKBroker. get_QUIK_positions() не вернул фьючерсные позиции для {sec_name}, соррян: {err}')
            return None, None

    def fixup_position(self, data, size, price):
        pos = self.getposition(data, clone=False)  # Получаем позицию по тикеру или нулевую позицию если тикера в списке позиций нет
        # p = pos.update(size, price)  # self.size, self.price, opened, closed
        if not pos.fix(size, price):  # return self.size == oldsize
            print(f'{datetime.now():%H:%M:%S} QKBroker. fixup_position(): Позиция обновлена успешно')
            return int(self.getposition(data, clone=False).size)  # self.size, self.price, opened, closed
        print(f'{datetime.now():%H:%M:%S} QKBroker. fixup_position(): НЕ УДАЛОСЬ ОБНОВИТЬ ПОЗИЦИЮ!!!')
        return size
        # return p[0]  # size

    # def get_QUIK_active_positions_number(self):
    #     all_sec = self.store.qpProvider.GetFuturesHoldings()["data"]
    #     act_pos = [sec for sec in all_sec if sec['totalnet'] != 0]
    #     return len(act_pos)
    #
    # def get_TEST_position(self, sec_name):
    #     # Запрашиваем позицию по фьючерсу sec_name в Quik. https://luaq.ru/getFuturesHolding.html
    #     try:
    #         pos = self.store.qpProvider.GetFuturesHolding(self.p.FirmId, self.p.TradeAccountId, sec_name, 2)["data"]
    #         print(f'TEST!!! {pos = }')
    #         return pos
    #     except Exception as err:  # При ошибке returns nil
    #         print(f'{datetime.now():%H:%M:%S} QKBroker. get_TEST_positions() TEST для {sec_name}, соррян: {err}')
    #         return err
    #
    def test_GetStopOrders(self, sec_name, oref, onum):  #, trans_id=2):  #'716958297'):
        print("Мы в test_GetStopOrders")
        stop_orders = self.store.qpProvider.GetAllStopOrders()["data"]
        find_order = [o for o in stop_orders if o['seccode'] == sec_name and o['trans_id'] == oref and o['ordernum'] == onum]
        print("Ушел из test_GetStopOrders")
        return bool(len(find_order))

    def test_GetAllStopOrders(self):
        print("Мы в test_GetAllStopOrders")
        # classCode = "SPBFUT"
        stop_orders = self.store.qpProvider.GetAllStopOrders()["data"]
        print(stop_orders)
        for o in stop_orders:
            print(o)
        print("Ушел из test_GetAllStopOrders")
        return None

    def get_order_number(self, order_ref):  # Для поиска биржевого номера и снятия стоп-лосс заявок при выходе по тейк-профиту
        try:
            r = str(self.store.orderNums[order_ref])
        except KeyError:
            print(f'QKBroker. Мы в get_order_number. Стоп-лосс заявка # {order_ref} не найдена в словаре заявок. '
                  f'Словарь: {self.store.orderNums}')
            r = None
        return r

    def check_StopOrder(self, sec_name, oref, onum):  #, trans_id=2):  #'716958297'):
        stop_orders = self.store.qpProvider.GetAllStopOrders()["data"]
        find_order = [o for o in stop_orders if o['seccode'] == sec_name and o['trans_id'] == oref and o['ordernum'] == onum]
        return bool(len(find_order))

    def kill_StopOrder(self, onum, oref, sec_name):
        print("QKBroker. Мы в kill_missed_stop_order. Проверяем, не выставлена ли лимитная заявка по нашей стоп-лосс заявке")
        check_for_limit = self.store.qpProvider.GetOrderByNumber(int(onum), int(oref))['data']
        if isinstance(check_for_limit, int):  #лимитная заявка не выставлена
            print("QKBroker. Проверили, не выставлена")
            transaction = {
                'TRANS_ID': oref,  # Номер транзакции задается клиентом (Это ВТ order ref). Строка!
                'CLASSCODE': "SPBFUT",  # Код площадки
                'SECCODE': sec_name,  # Код тикера
                'ACTION': 'KILL_STOP_ORDER',  # Будем удалять стоп заявку
                'STOP_ORDER_KEY': onum  # Номер стоп заявки на бирже. Строка!
            }
            self.store.qpProvider.SendTransaction(transaction)  # Отправляем транзакцию на рынок
            return True
        else:
            print("QKBroker. Проверку не прошли. Выходим из kill_missed_stop_order.")
            print(sec_name, onum, oref, check_for_limit)
            return False


