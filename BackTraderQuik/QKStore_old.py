import collections
import time
from datetime import datetime, date
from pytz import timezone

from backtrader.metabase import MetaParams
from backtrader.utils.py3 import with_metaclass
from backtrader import Order, BuyOrder, SellOrder
from backtrader.position import Position
from QuikPy import QuikPy

# 1059203

# def log(txt):
#     file = 'debug_log_data.txt'
#     file = f'Logs/{file.split(".")[0]}_{str(datetime.now())[:10]}.{file.split(".")[1]}'.replace(':', '-')
#     f = open(file, "a")
#     f.write(str(datetime.now().time())[:10] + ', Store, ' + txt + '\n')
#     f.close()
#     return


class MetaSingleton(MetaParams):
    """Метакласс для создания Singleton классов"""
    def __init__(cls, *args, **kwargs):
        """Инициализация класса"""
        super(MetaSingleton, cls).__init__(*args, **kwargs)
        cls._singleton = None  # Экземпляра класса еще нет

    def __call__(cls, *args, **kwargs):
        """Вызов класса"""
        if cls._singleton is None:  # Если класса нет в экземплярах класса
            cls._singleton = super(MetaSingleton, cls).__call__(*args, **kwargs)  # то создаем зкземпляр класса
        return cls._singleton  # Возвращаем экземпляр класса


class QKStore(with_metaclass(MetaSingleton, object)):
    """Хранилище QUIK"""
    params = (
        ('Host', '127.0.0.1'),  # Адрес/IP компьютера с QUIK
        ('RequestsPort', 34130),  # Номер порта для запросов и ответов
        ('CallbacksPort', 34131),  # Номер порта для получения событий
    )
    BrokerCls = None  # Класс брокера будет задан из брокера
    DataCls = None  # Класс данных будет задан из данных

    MarketTimeZone = timezone('Europe/Moscow')  # Биржа работает по московскому времени
    # StopSteps = 5  # Размер в минимальных шагах цены инструмента для исполнения стоп заявок

    @classmethod
    def getdata(cls, *args, **kwargs):
        """Returns DataCls with args, kwargs"""
        return cls.DataCls(*args, **kwargs)

    @classmethod
    def getbroker(cls, *args, **kwargs):
        """Returns broker with *args, **kwargs from registered BrokerCls"""
        return cls.BrokerCls(*args, **kwargs)

    def __init__(self):
        super(QKStore, self).__init__()
        self.notifs = collections.deque()  # Уведомления хранилища
        self.isConnected = True  # Считаем, что изначально QUIK подключен к серверу брокера
        self.qpProvider = QuikPy(Host=self.p.Host, RequestsPort=self.p.RequestsPort, CallbacksPort=self.p.CallbacksPort)  # Вызываем конструктор QuikPy с адресом хоста и портами по умолчанию
        self.classCodes = self.qpProvider.GetClassesList()['data']  # Список классов. В некоторых таблицах тикер указывается без кода класса
        self.subscribedSymbols = []  # Список подписанных тикеров/интервалов
        self.securityInfoList = []  # Кэш параметров тикеров
        self.newBars = []  # Новые бары по подписке из QUIK
        self.positions = collections.defaultdict(Position)  # Список позиций
        self.orders = collections.OrderedDict()  # Список заявок, отправленных на рынок
        self.newTransId = 1  # Следующий внутренний номер транзакции заявки (задается пользователем)
        self.orderNums = {}  # Словарь заявок на бирже. Индекс - номер транзакции, значение - номер заявки на бирже
        self.ocos = {}  # Список связанных заявок

    def start(self):
        self.qpProvider.OnNewCandle = self.OnNewCandle  # Обработчик новых баров по подписке из QUIK

    def put_notification(self, msg, *args, **kwargs):
        self.notifs.append((msg, args, kwargs))

    def get_notifications(self):
        """Выдача уведомлений хранилища"""
        self.notifs.append(None)
        return [x for x in iter(self.notifs.popleft, None)]

    def stop(self):
        self.qpProvider.OnNewCandle = self.qpProvider.DefaultHandler  # Возвращаем обработчик по умолчанию
        self.qpProvider.CloseConnectionAndThread()  # Закрываем соединение для запросов и поток обработки функций обратного вызова

    # Функции конвертации

    def DataNameToClassSecCode(self, dataname):
        """Код площадки и код тикера из названия тикера (с кодом площадки или без него)"""
        return tuple(dataname.split('.'))

    def GetSecurityInfo(self, ClassCode, SecCode):
        """Параметры тикера из кэша / по запросу"""
        si = [securityInfo for securityInfo in self.securityInfoList if securityInfo['class_code'] == ClassCode and securityInfo['sec_code'] == SecCode]  # Ищем в кэше параметры тикера
        if len(si) == 0:  # Если параметры тикера не найдены в кэше
            si = self.qpProvider.GetSecurityInfo(ClassCode, SecCode)['data']  # то делаем запрос параметров тикера
            self.securityInfoList.append(si)  # Добавляем полученные параметры тикера в кэш
            return si  # Возвращаем их
        else:  # Если параметры тикера найдены в кэше
            return si[0]  # то возвращаем первый элемент

    # QKBroker: Функции

    def GetPositions(self, ClientCode, FirmId, LimitKind, Lots, IsFutures=True):
        """
        Все активные позиции по счету
        Для фьючерсных счетов нужно установить параметр IsFutures=True
        """
        if IsFutures:  # Для фьючерсов свои расчеты
            futuresHoldings = self.qpProvider.GetFuturesHoldings()["data"]  # Все фьючерсные позиции
            activeFuturesHoldings = [futuresHolding for futuresHolding in futuresHoldings if futuresHolding['totalnet'] != 0]  # Активные фьючерсные позиции
            for activeFuturesHolding in activeFuturesHoldings:  # Пробегаемся по всем активным фьючерсным позициям
                classCode = 'SPBFUT'  # Код площадки
                secCode = activeFuturesHolding['sec_code']  # Код тикера
                dataname = f'{classCode}.{secCode}'  # self.ClassSecCodeToDataName(classCode, secCode)  # Получаем название тикера по коду площадки и коду тикера
                size = int(activeFuturesHolding['totalnet'])  # Кол-во
                # if Lots:  # Если входящий остаток в лотах
                #     size = self.LotsToSize(classCode, secCode, size)  # то переводим кол-во из лотов в штуки
                price = float(activeFuturesHolding['avrposnprice'])  # Цена приобретения
                # price = self.QKToBTPrice(classCode, secCode, price)  # Переводим цену приобретения за лот в цену приобретения за штуку
                self.positions[dataname] = Position(size, price)  # Сохраняем в списке открытых позиций

    def GetMoneyLimits(self, ClientCode, FirmId, TradeAccountId, LimitKind, CurrencyCode, IsFutures=True):
        """
        Свободные средства по счету
        Для фьючерсных счетов нужно установить параметр IsFutures=True
        """
        if IsFutures:  # Для фьючерсов свои расчеты
            # Видео: https://www.youtube.com/watch?v=u2C7ElpXZ4k
            # Баланс = Лимит откр.поз. + Вариац.маржа + Накоплен.доход
            # Лимит откр.поз. = Сумма, которая была на счету вчера в 19:00 МСК (после вечернего клиринга)
            # Вариац.маржа = Рассчитывается с 19:00 предыдущего дня без учета комисии. Перейдет в Накоплен.доход и обнулится в 14:00 (на дневном клиринге)
            # Накоплен.доход включает Биржевые сборы
            # Тек.чист.поз. = Заблокированное ГО под открытые позиции
            # План.чист.поз. = На какую сумму можете открыть еще позиции
            try:
                if int(f'{datetime.now():%H}') == 7:  # !!! Уход от ошибки Futures limit returns nil
                    return 0
                futuresLimit = self.qpProvider.GetFuturesLimit(FirmId, TradeAccountId, 0, 'SUR')['data']  # Фьючерсные лимиты
                return float(futuresLimit['cbplimit']) + float(futuresLimit['varmargin']) + float(futuresLimit['accruedint'])  # Лимит откр.поз. + Вариац.маржа + Накоплен.доход
            except Exception:  # При ошибке Futures limit returns nil
                print(f'{datetime.now():%H:%M:%S}. QKStore. GetMoneyLimits. QUIK не вернул фьючерсные лимиты с FirmId={FirmId}, TradeAccountId={TradeAccountId}. Проверьте правильность значений')
                return None

    def GetPositionsLimits(self, FirmId, TradeAccountId, IsFutures=True):
        """
        Стоимость позиций по счету
        Для фьючерсных счетов нужно установить параметр IsFutures=True
        """
        if IsFutures:  # Для фьючерсов свои расчеты
            try:
                if int(f'{datetime.now():%H}') == 7:  # !!! Уход от ошибки Futures limit returns nil утром
                    return 0
                return float(self.qpProvider.GetFuturesLimit(FirmId, TradeAccountId, 0, 'SUR')['data']['cbplused'])  # Тек.чист.поз. (Заблокированное ГО под открытые позиции)
            except Exception:  # При ошибке Futures limit returns nil
                print(f'{datetime.now():%H:%M:%S}. QKStore. GetPositionsLimits. QUIK не вернул фьючерсные лимиты с FirmId={FirmId}, TradeAccountId={TradeAccountId}. Проверьте правильность значений')
                return None

    def PlaceOrder(self, ClientCode, TradeAccountId, owner, data, size, price=None, plimit=None, exectype=None, valid=None, oco=None, CommInfo=None, IsBuy=True, **kwargs):
        # TODO: Организовать работу группы заявок с 'parent' и 'transmit'
        order = BuyOrder(owner=owner, data=data, size=size, price=price, pricelimit=plimit, exectype=exectype, oco=oco) if IsBuy \
            else SellOrder(owner=owner, data=data, size=size, price=price, pricelimit=plimit, exectype=exectype, oco=oco)  # Заявка на покупку/продажу
        # if order:
        #     print(f'{datetime.now():%H:%M:%S} QKStore.PlaceOrder. Создана заявка (BT order).')
        order.addinfo(**kwargs)  # Передаем все дополнительные параметры
        order.addcomminfo(CommInfo)  # По тикеру выставляем комиссии в заявку. Нужно для исполнения заявки в BackTrader
        classCode, secCode = self.DataNameToClassSecCode(data._dataname)  # Из названия тикера получаем код площадки и тикера
        # size = self.SizeToLots(classCode, secCode, size)  # Размер позиции в лотах
        if price is None:  # Если цена не указана для рыночных заявок
            price = 0.00  # Цена рыночной заявки должна быть нулевой (кроме фьючерсов)
        if order.exectype == Order.Market:  # Для рыночных заявок
            if classCode == 'SPBFUT':  # Для рынка фьючерсов
                lastPrice = float(self.qpProvider.GetParamEx(classCode, secCode, 'LAST')['data']['param_value'])  # Последняя цена сделки
                minPriceStep = self.GetSecurityInfo(classCode, secCode)['min_price_step']  # Минимальный шаг цены
                # ВНИМАНИЕ! МОЯ ПРАВКА!!! Меняю ниже 10 на 2
                #price = lastPrice + 10 * minPriceStep if IsBuy else lastPrice - 10 * minPriceStep  # Наихудшая цена (на 10 шагов хуже последней цены). Все равно, заявка исполнится по рыночной цене
                price = lastPrice + 2 * minPriceStep if IsBuy else lastPrice - 2 * minPriceStep  # Наихудшая цена (на 2 шагов хуже последней цены). Все равно, заявка исполнится по рыночной цене
        # else:  # Для остальных заявок
        #     price = self.BTToQKPrice(classCode, secCode, price)  # Переводим цену из BackTrader в QUIK
        scale = int(self.GetSecurityInfo(classCode, secCode)['scale'])  # Кол-во значащих цифр после запятой
        price = round(price, scale)  # Округляем цену до кол-ва значащих цифр
        if price.is_integer():  # Целое значение цены мы должны отправлять без десятичных знаков
            price = int(price)  # поэтому, приводим такую цену к целому числу
        transaction = {  # Все значения должны передаваться в виде строк
            'TRANS_ID': str(self.newTransId),  # Номер транзакции задается клиентом
            'CLIENT_CODE': ClientCode,  # Код клиента. Для фьючерсов его нет
            'ACCOUNT': TradeAccountId,  # Счет
            'CLASSCODE': classCode,  # Код площадки
            'SECCODE': secCode,  # Код тикера
            'OPERATION': 'B' if IsBuy else 'S',  # B = покупка, S = продажа
            'PRICE': str(price),  # Цена исполнения
            'QUANTITY': str(size)}  # Кол-во в лотах
        if order.exectype in [Order.Stop, Order.StopLimit]:  # Для стоп заявок
            transaction['ACTION'] = 'NEW_STOP_ORDER'  # Новая стоп заявка
            transaction['STOPPRICE'] = str(price)  # Стоп цена срабатывания
            # Я закоментил Блок про slippage, проскальзывание учтено в BT!!!
            # slippage = float(self.GetSecurityInfo(classCode, secCode)['min_price_step']) * self.StopSteps  # Размер проскальзывания в деньгах
            # if slippage.is_integer():  # Целое значение проскальзывания мы должны отправлять без десятичных знаков
            #     slippage = int(slippage)  # поэтому, приводим такое проскальзывание к целому числу
            if plimit is not None:  # Если задана лимитная цена исполнения
                #limitPrice = plimit  # то ее и берем     Я добавил !!!
                if plimit.is_integer():                 # Я добавил !!!
                    limitPrice = int(plimit)            # Я добавил !!!
                else:                                   # Я добавил !!!
                    limitPrice = round(plimit, scale)   # Я добавил !!!
            # elif IsBuy:                         # Я закоментил, проскальзывание учтено в BT!!!
            #     limitPrice = price + slippage   # Я закоментил, проскальзывание учтено в BT!!!
            # else:                               # Я закоментил, проскальзывание учтено в BT!!!
            #     limitPrice = price - slippage   # Я закоментил, проскальзывание учтено в BT!!!
            transaction['PRICE'] = str(limitPrice)  # Лимитная цена исполнения
            expiryDate = 'GTC'  # По умолчанию будем держать заявку до отмены GTC = Good Till Cancelled
            if valid in [Order.DAY, 0]:  # Если заявка поставлена на день
                expiryDate = 'TODAY'  # то будем держать ее до окончания текущей торговой сессии
            elif isinstance(valid, date):  # Если заявка поставлена до даты
                expiryDate = valid.strftime('%Y%m%d')  # то будем держать ее до указанной даты
            transaction['EXPIRY_DATE'] = expiryDate  # Срок действия стоп заявки
        else:  # Для рыночных или лимитных заявок
            transaction['ACTION'] = 'NEW_ORDER'  # Новая рыночная или лимитная заявка
            transaction['TYPE'] = 'L' if order.exectype == Order.Limit else 'M'  # L = лимитная заявка (по умолчанию), M = рыночная заявка
        order.ref = self.newTransId  # Ставим номер транзакции в заявку
        self.newTransId += 1  # Увеличиваем номер транзакции для будущих заявок
        if oco is not None:  # Если есть связанная заявка
            self.ocos[order.ref] = oco.ref  # то заносим в список родительских заявок
        response = self.qpProvider.SendTransaction(transaction)  # Отправляем транзакцию на рынок
        order.submit(self)  # Переводим заявку в статус Order.Submitted
        if response['cmd'] == 'lua_transaction_error':  # Если возникла ошибка при постановке заявки на уровне QUIK
            print(f'{datetime.now():%H:%M:%S}'
                  f'{response["data"]["CLASSCODE"]}.{response["data"]["SECCODE"]}{response["lua_error"]}')
            # то заявка не отправляется на биржу, выводим сообщение об ошибке
            order.reject()  # Переводим заявку в статус Order.Reject
        self.orders[order.ref] = order  # Сохраняем в списке заявок
        return order  # Возвращаем заявку

    def CancelOrder(self, order):
        """Отмена заявки"""
        if not order.alive():  # Если заявка уже была завершена
            print(f'QKStore. Отмена заявки. Заявка не живая')
            return False  # то выходим, дальше не продолжаем

        if not self.orders.get(order.ref, False):  # Если заявка не найдена
            print(f'QKStore. Отмена заявки. Заявка не найдена')
            return False  # то выходим, дальше не продолжаем

        if order.ref not in self.orderNums:  # Если заявки нет в словаре заявок на бирже
            print(f'QKStore. Отмена заявки. Заявка не в списке заявок')
            return False  # то выходим, дальше не продолжаем

        orderNum = self.orderNums[order.ref]  # Номер заявки на бирже
        classCode, secCode = self.DataNameToClassSecCode(order.data._dataname)  # По названию тикера получаем код площадки и код тикера
        isStop = order.exectype in [Order.Stop, Order.StopLimit] and \
            isinstance(self.qpProvider.GetOrderByNumber(orderNum)['data'], int)  # Задана стоп заявка и лимитная заявка не выставлена
        transaction = {
            'TRANS_ID': str(order.ref),  # Номер транзакции задается клиентом
            'CLASSCODE': classCode,  # Код площадки
            'SECCODE': secCode}  # Код тикера
        if isStop:  # Для стоп заявки
            transaction['ACTION'] = 'KILL_STOP_ORDER'  # Будем удалять стоп заявку
            transaction['STOP_ORDER_KEY'] = str(orderNum)  # Номер стоп заявки на бирже
        else:  # Для лимитной заявки
            transaction['ACTION'] = 'KILL_ORDER'  # Будем удалять лимитную заявку
            transaction['ORDER_KEY'] = str(orderNum)  # Номер заявки на бирже
        self.qpProvider.SendTransaction(transaction)  # Отправляем транзакцию на рынок
        return order  # В список уведомлений ничего не добавляем. Ждем события OnTransReply

    def OCOCheck(self, order):
        """Проверка связанных заявок"""
        for orderRef, ocoRef in self.ocos.items():  # Пробегаемся по списку родительских заявок
            if ocoRef == order.ref:  # Если эта заявка для какой-то является родительской
                self.CancelOrder(self.orders[orderRef])  # то удаляем ту заявку
        if order.ref in self.ocos.keys():  # Если у этой заявки есть родительская заявка
            ocoRef = self.ocos[order.ref]  # то получаем номер родительской заявки
            self.CancelOrder(self.orders[ocoRef])  # и удаляем родительскую заявку

    # QKBroker: Обработка событий подключения к QUIK / отключения от QUIK
    def OnConnected(self, data):
        #dt = datetime.now(QKStore.MarketTimeZone)  # Берем текущее время на рынке
        #self.put_notification('QUIK Connected')
        print(f'{datetime.now():%d.%m.%y %H:%M:%S} QUIK Connected')
        self.isConnected = True  # QUIK подключен к серверу брокера
        #print(f'Проверка подписки тикеров ({len(self.subscribedSymbols)})' + '\n')
        for subscribedSymbol in self.subscribedSymbols:  # Пробегаемся по всем подписанным тикерам
            classCode = subscribedSymbol['class']  # Код площадки
            secCode = subscribedSymbol['sec']  # Код тикера
            interval = subscribedSymbol['interval']  # Временной интервал
            #print(f'{classCode}.{secCode} на интервале {interval}', end=' ')
            if not self.qpProvider.IsSubscribed(classCode, secCode, interval)['data']:  # Если нет подписки на тикер/интервал
                self.qpProvider.SubscribeToCandles(classCode, secCode, interval)  # то переподписываемся
                #print('нет подписки. Отправлен запрос на новую подписку')
            # else:  # Если подписка была, то переподписываться не нужно
                #print('есть подписка')

    def OnDisconnected(self, data):
        if not self.isConnected:  # Если QUIK отключен от сервера брокера
            return  # то не нужно дублировать сообщение, выходим, дальше не продолжаем
        #dt = datetime.now(QKStore.MarketTimeZone)  # Берем текущее время на рынке
        self.put_notification('QUIK Disconnected')
        self.isConnected = False  # QUIK отключен от сервера брокера

    # QKData: Обработка событий получения новых баров
    def OnNewCandle(self, data):
        self.newBars.append(data['data'])  # Добавляем новый бар в список новых баров
