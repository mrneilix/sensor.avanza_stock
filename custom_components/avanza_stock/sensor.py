"""
Support for getting stock data from avanza.se.

For more details about this platform, please refer to the documentation at
https://github.com/claha/sensor.avanza_stock/blob/master/README.md
"""
import logging
from datetime import (
    timedelta, datetime)

import homeassistant.helpers.config_validation as cv
import requests
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_MONITORED_CONDITIONS)
from homeassistant.helpers.entity import Entity

__version__ = '0.0.6'

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Avanza Stock'

CONF_STOCK = 'stock'

SCAN_INTERVAL = timedelta(minutes=60)

MONITORED_CONDITIONS = [
    'brokerTradeSummary',
    'change',
    'changePercent',
    'country',
    'currency',
    'dividends',
    'flagCode',
    'hasInvestmentFees',
    'highestPrice',
    'id',
    'isin',
    'lastPrice',
    'lastPriceUpdated',
    # 'latestTrades',
    'loanFactor',
    'lowestPrice',
    'marketList',
    'marketMakerExpected',
    'marketPlace',
    'marketTrades',
    'morningStarFactSheetUrl',
    'name',
    'numberOfOwners',
    # 'orderDepthLevels',
    'orderDepthReceivedTime',
    'priceAtStartOfYear',
    'priceFiveYearsAgo',
    'priceOneMonthAgo',
    'priceOneWeekAgo',
    'priceOneYearAgo',
    'priceSixMonthsAgo',
    'priceThreeMonthsAgo',
    'priceThreeYearsAgo',
    'pushPermitted',
    'quoteUpdated',
    'shortSellable',
    'superLoan',
    'tickerSymbol',
    'totalValueTraded',
    'totalVolumeTraded',
    'tradable',
]

MONITORED_CONDITIONS_KEYRATIOS = [
    'directYield',
    'priceEarningsRatio',
    'volatility',
]
MONITORED_CONDITIONS += MONITORED_CONDITIONS_KEYRATIOS

MONITORED_CONDITIONS_COMPANY = [
    'description',
    'marketCapital',
    'sector',
    'totalNumberOfShares',
]
MONITORED_CONDITIONS += MONITORED_CONDITIONS_COMPANY

MONITORED_CONDITIONS_DIVIDENDS = [
    'amountPerShare',
    'exDate',
    'paymentDate',
]

MONITORED_CONDITIONS_DEFAULT = [
    'change',
    'changePercent',
    'name',
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STOCK): cv.positive_int,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS,
                 default=MONITORED_CONDITIONS_DEFAULT):
    vol.All(cv.ensure_list, [vol.In(MONITORED_CONDITIONS)]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Avanza Stock sensor."""
    stock = config.get(CONF_STOCK)
    name = config.get(CONF_NAME)
    if config.get(CONF_NAME) is None:
        name = DEFAULT_NAME + ' ' + str(stock)
    monitored_conditions = config.get(CONF_MONITORED_CONDITIONS)
    add_entities([AvanzaStockSensor(stock, name, monitored_conditions)], True)


class AvanzaStockSensor(Entity):
    """Representation of a Avanza Stock sensor."""

    def __init__(self, stock, name, monitored_conditions):
        """Initialize a Avanza Stock sensor."""
        self._stock = stock
        self._name = name
        self._monitored_conditions = monitored_conditions
        self._icon = "mdi:cash"
        self._state = 0
        self._state_attributes = {}
        self._unit_of_measurement = ''

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._state_attributes

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data from the Avanza Stock API."""
        url = 'https://www.avanza.se/_mobile/market/stock/{}'
        url = url.format(self._stock)
        response = requests.get(url)
        if response.status_code == requests.codes.ok:
            data = response.json()
            keyRatios = data.get('keyRatios', {})
            company = data.get('company', {})
            dividends = data.get('dividends', [])
            self._state = data['lastPrice']
            self._unit_of_measurement = data['currency']
            for condition in self._monitored_conditions:
                if condition in MONITORED_CONDITIONS_KEYRATIOS:
                    self._state_attributes[condition] = keyRatios.get(
                        condition, None)
                elif condition in MONITORED_CONDITIONS_COMPANY:
                    self._state_attributes[condition] = company.get(
                        condition, None)
                elif condition == 'dividends':
                    self.update_dividends(dividends)
                else:
                    self._state_attributes[condition] = data.get(
                        condition, None)

    def update_dividends(self, dividends):
        """Update dividend attributes."""
        # Crreate empty dividend attributes, will be overwritten with valid
        # data if information is available
        for dividend_condition in MONITORED_CONDITIONS_DIVIDENDS:
            attribute = 'dividend0_{0}'.format(dividend_condition)
            self._state_attributes[attribute] = 'unknown'

        # Check that each dividend has the attributes needed.
        # Dividends from the past sometimes misses attributes
        # but we are not interested in them anyway.
        for i, dividend in reversed(list(enumerate(dividends))):
            has_all_attributes = True
            for dividend_condition in MONITORED_CONDITIONS_DIVIDENDS:
                if dividend_condition not in dividend:
                    has_all_attributes = False
            if not has_all_attributes:
                del dividends[i]

        # Sort dividends by payment date
        dividends = sorted(dividends, key=lambda d: d['paymentDate'])

        # Loop over data
        i = 0
        for dividend in dividends:
            paymentDate = datetime.strptime(dividend['paymentDate'],
                                            '%Y-%m-%d')
            if paymentDate >= datetime.now():
                for dividend_condition in MONITORED_CONDITIONS_DIVIDENDS:
                    attribute = 'dividend{0}_{1}'.format(i, dividend_condition)
                    self._state_attributes[attribute] = dividend[
                        dividend_condition]
                i += 1
