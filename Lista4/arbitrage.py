import requests
import time
from main import load_api_data_from_json

CRYPTOCURRIRNCIES = ["ETH", "BTC", "XRP"]
NORMALIZED_OPERATIONS = ['bids', 'asks']
WAITING_TIME = 5
ARTIFICIAL_LOOP_LIMIT = 2


def parse_bitrex_orderbook(jsondata):
    resultDictionary = {}
    if jsondata.get("result", None):
        table = []
        if jsondata["result"].get("buy", None):
            pair = []
            for dictionary in jsondata["result"]["buy"]:
                pair.append(dictionary["Rate"])
                pair.append(dictionary["Quantity"])
                table.append(pair.copy())
                pair.clear()
            resultDictionary[NORMALIZED_OPERATIONS[0]] = table.copy()
            table.clear()
        if jsondata["result"].get("sell", None):
            pair = []
            for dictionary in jsondata["result"]["sell"]:
                pair.append(dictionary["Rate"])
                pair.append(dictionary["Quantity"])
                table.append(pair.copy())
                pair.clear()
            resultDictionary[NORMALIZED_OPERATIONS[1]] = table.copy()
            table.clear()
    return resultDictionary


def get_api_response(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print("Request not succesful: " + response.reason)
        return None


def get_offers(currency, market, basecurrency, apiinfo):
    if market == apiinfo["Api"]["bitbay"]["name"]:
        offers = get_api_response(f'{apiinfo["Api"]["bitbay"]["url_orderbook"]}{currency}'
                                  f'{basecurrency}{apiinfo["Api"]["bitbay"]["orderbook_ending"]}')
        if offers is not None:
            return offers

    elif market == apiinfo["Api"]["bitrex"]["name"]:
        offers = get_api_response(f'{apiinfo["Api"]["bitrex"]["url_orderbook"]}{basecurrency}'
                                  f'{apiinfo["Api"]["bitrex"]["orderbook_separator"]}'
                                  f'{currency}{apiinfo["Api"]["bitrex"]["orderbook_ending"]}')
        if offers is not None:
            return parse_bitrex_orderbook(offers)

    else:
        return None


def calculate_percentage_difference(order1, order2):
    return round(((order1 - order2) / order1) * 100, 2)


def include_taker_fee(cost, market, operation):
    if operation == NORMALIZED_OPERATIONS[1]:
        return cost * (1 + market["taker"])
    elif operation == NORMALIZED_OPERATIONS[0]:
        return cost * (1 - market["taker"])


def calculate_order_value(price, amount):
    return price * amount


def calculate_arbitrage(offerstobuyfrom, offerstosellto, buyingmarket, sellingmarket, currency, basecurrency):
    volume = 0.0
    spentMoney = 0.0
    gainedMoney = 0.0
    transferFee = buyingmarket['transferFee'][currency]
    transferFeePaidNumber = 0
    operationNumber = 0

    while offerstobuyfrom and offerstosellto and offerstobuyfrom[0][0] < offerstosellto[0][0]:
        operationNumber += 1
        buyVolume = min(offerstobuyfrom[0][1], offerstosellto[0][1])
        sellVolume = buyVolume
        if transferFee > 0:
            if sellVolume > transferFee:
                sellVolume -= transferFee
                transferFee = 0
                transferFeePaidNumber = operationNumber
            else:
                transferFee -= buyVolume
                sellVolume = 0
        buyValue = calculate_order_value(offerstobuyfrom[0][0], buyVolume)
        buyCost = include_taker_fee(buyValue, buyingmarket, NORMALIZED_OPERATIONS[1])
        sellValue = calculate_order_value(offerstosellto[0][0], sellVolume)
        sellGain = include_taker_fee(sellValue, sellingmarket, NORMALIZED_OPERATIONS[0])

        if buyCost < sellGain or transferFee > 0 or (transferFee == 0.0 and operationNumber == transferFeePaidNumber):
            volume += buyVolume
            spentMoney += buyCost
            gainedMoney += sellGain

            if transferFee > 0 or (transferFee == 0.0 and operationNumber == transferFeePaidNumber):
                print(f" Checking for negative profit until transfer fee is covered:"
                      f" {round(gainedMoney - spentMoney, 2)} {basecurrency}")

            offerstosellto[0][1] -= sellVolume
            if offerstosellto[0][1] == 0:
                del offerstosellto[0]
            offerstobuyfrom[0][1] -= buyVolume
            if offerstobuyfrom[0][1] == 0:
                del offerstobuyfrom[0]

        else:
            break

    if spentMoney == 0 and gainedMoney == 0:
        profitability = 0
    else:
        profitability = round(((gainedMoney - spentMoney) / spentMoney) * 100, 2)

    return {'volume': volume, 'profitability': profitability, 'profit': round(gainedMoney - spentMoney, 2)}


def zad2(base_currency):
    apiInfo = load_api_data_from_json()
    for crypto in CRYPTOCURRIRNCIES:
        print("Cryptocurrency: " + crypto)
        i = 0
        while i < ARTIFICIAL_LOOP_LIMIT:
            offer1 = get_offers(crypto, apiInfo["Api"]["bitbay"]["name"], base_currency, apiInfo)
            offer2 = get_offers(crypto, apiInfo["Api"]["bitrex"]["name"], base_currency, apiInfo)
            if offer1 is not None and offer2 is not None:
                if offer1.get(NORMALIZED_OPERATIONS[0], None) and offer1.get(NORMALIZED_OPERATIONS[1], None) \
                        and offer2.get(NORMALIZED_OPERATIONS[0], None) and offer2.get(NORMALIZED_OPERATIONS[1], None):
                    print(f'{apiInfo["Api"]["bitbay"]["name"]} - selling offers: {offer1[NORMALIZED_OPERATIONS[1]]}\n'
                          f'{apiInfo["Api"]["bitbay"]["name"]} - buying offers: {offer1[NORMALIZED_OPERATIONS[0]]}')
                    print(f'{apiInfo["Api"]["bitrex"]["name"]} - selling offer: {offer2[NORMALIZED_OPERATIONS[1]]}\n'
                          f'{apiInfo["Api"]["bitrex"]["name"]} - buying offers: {offer2[NORMALIZED_OPERATIONS[0]]}')
                    resultFrom1To2 = calculate_arbitrage(offer1[NORMALIZED_OPERATIONS[1]],
                                                         offer2[NORMALIZED_OPERATIONS[0]],
                                                         apiInfo["Api"]["bitbay"], apiInfo["Api"]["bitrex"], crypto,
                                                         base_currency)
                    if resultFrom1To2['profit'] <= 0:
                        print(f"There are no profitable transactions buying in {apiInfo['Api']['bitbay']['name']}"
                              f" and selling in {apiInfo['Api']['bitrex']['name']}")
                    else:
                        print(f"Buying from {apiInfo['Api']['bitbay']['name']}:\n "
                              f"Volume: {resultFrom1To2['volume']} {crypto},"
                              f" profit: {resultFrom1To2['profit']} {base_currency},"
                              f" gain: {resultFrom1To2['profitability']}%")
                    resultFrom2To1 = calculate_arbitrage(offer2[NORMALIZED_OPERATIONS[1]],
                                                         offer1[NORMALIZED_OPERATIONS[0]],
                                                         apiInfo["Api"]["bitrex"], apiInfo["Api"]["bitbay"], crypto,
                                                         base_currency)
                    if resultFrom2To1['profit'] <= 0:
                        print(f"There are no profitable transactions buying in {apiInfo['Api']['bitbay']['name']}"
                              f" and selling in {apiInfo['Api']['bitbay']['name']}")
                    else:
                        print(f"Buying from {apiInfo['Api']['bitrex']['name']}:\n "
                              f"Volume: {resultFrom2To1['volume']} {crypto},"
                              f" profit: {resultFrom2To1['profit']} {base_currency},"
                              f" gain: {resultFrom2To1['profitability']}%")
                else:
                    print("Orderbooks do not contain buying and selling prices!")
            else:
                print("Something gone wrong during data acquisition")
            time.sleep(WAITING_TIME)
            i += 1
            print()


if __name__ == '__main__':
    try:
        zad2("USD")
    except requests.ConnectionError:
        print("Failed to connect to API")
