"""
UPS Shipping Module
You must have a UPS account to use this module.
You may register at ups.com

This module uses the XML online tools for maximum flexibility.  It is
primarily created for use in the US but reconfiguring for international
shipping or more advanced uses should be straightforward.

It is recommended that you refer to the UPS shipper developer documents
(available when you register at UPS) in order to tailor this to your
unique needs.
"""

from decimal import Decimal
from django.template import Context, loader
from django.utils.translation import ugettext as _
from livesettings import config_get_group, config_value
from keyedcache import cache_key, cache_get, cache_set, NotCachedError
from shipping import signals
from shipping.modules.base import BaseShipper
import datetime
import logging
import urllib2

try:
    from xml.etree.ElementTree import fromstring, tostring
except ImportError:
    from elementtree.ElementTree import fromstring, tostring

log = logging.getLogger('ups.shipper')

# map the codes returned by the time in transit api to the ones in the shipping api (sigh)
# even worse is that the published codes in their API don't match what we actually get.
#
# reference:
# 1DA=UPS Next Day Air
# 1DAS=UPS Next Day Air (Saturday Delivery)
# 1DM=UPS Next Day Air Early A.M.
# 1DMS=UPS Next Day Air Early A.M. (Saturday Delivery)
# 1DP=UPS Next Day Air Saver
# 2DA=UPS 2nd Day Air
# 3DS=UPS 3 Day Select
# GND=UPS Ground

TRANSIT_CODE_MAP = {
    '1DA' : '01',
    '2DA' : '02',
    'GND' : '03',
    '3DS' : '12',
    '1DP' : '13',
    '1DM' : '14',
    '2DM' : '59'  #guessing, I've never seen this code come back
    }

class Shipper(BaseShipper):

    def __init__(self, cart=None, contact=None, service_type=None):
        self._calculated = False
        self.cart = cart
        self.contact = contact
        if service_type:
            self.service_type_code = service_type[0]
            self.service_type_text = service_type[1]
        else:
            self.service_type_code = "99"
            self.service_type_text = "Uninitialized"
        self.id = u"UPS-%s-%s" % (self.service_type_code, self.service_type_text)
        self.raw = "NO DATA"
        #if cart or contact:
        #    self.calculate(cart, contact)

    def __str__(self):
        """
        This is mainly helpful for debugging purposes
        """
        return "UPS"

    def description(self):
        """
        A basic description that will be displayed to the user when selecting their shipping options
        """
        return _("UPS - %s" % self.service_type_text)

    def cost(self):
        """
        Complex calculations can be done here as long as the return value is a decimal figure
        """
        assert(self._calculated)
        settings =  config_get_group('shipping.modules.ups')
        if settings.HANDLING_FEE and Decimal(str(settings.HANDLING_FEE)) > Decimal(0):
            self.charges = Decimal(self.charges) + Decimal(str(settings.HANDLING_FEE))

        return(Decimal(self.charges))

    def method(self):
        """
        Describes the actual delivery service (Mail, FedEx, DHL, UPS, etc)
        """
        return _("UPS")

    def expectedDelivery(self):
        """
        Can be a plain string or complex calcuation returning an actual date
        """
        if self.delivery_days <> "1":
            return _("%s business days" % self.delivery_days)
        else:
            return _("%s business day" % self.delivery_days)

    def valid(self, order=None):
        """
        Can do complex validation about whether or not this option is valid.
        For example, may check to see if the recipient is in an allowed country
        or location.
        """
        return self.is_valid

    def _process_request(self, connection, request):
        """
        Post the data and return the XML response
        """
        conn = urllib2.Request(url=connection, data=request.encode("utf-8"))
        f = urllib2.urlopen(conn)
        all_results = f.read()
        self.raw = all_results
        return(fromstring(all_results))

    def calculate(self, cart, contact):
        """
        Based on the chosen UPS method, we will do our call to UPS and see how much it will
        cost.
        We will also need to store the results for further parsing and return via the
        methods above
        """
        from satchmo_store.shop.models import Config

        settings =  config_get_group('shipping.modules.ups')
        self.delivery_days = _("3 - 4") #Default setting for ground delivery
        shop_details = Config.objects.get_current()
        # Get the code and description for the packaging
        container = settings.SHIPPING_CONTAINER.value
        container_description = settings.SHIPPING_CONTAINER.choices[int(container)][1]
        configuration = {
            'xml_key': settings.XML_KEY.value,
            'account': settings.ACCOUNT.value,
            'userid': settings.USER_ID.value,
            'password': settings.USER_PASSWORD.value,
            'container': container,
            'container_description': container_description,
            'pickup': settings.PICKUP_TYPE.value,
            'ship_type': self.service_type_code,
            'shop_details':shop_details,
        }

        shippingdata = {
            'single_box': False,
            'config': configuration,
            'contact': contact,
            'cart': cart,
            'shipping_address' : shop_details,
            'shipping_phone' : shop_details.phone,
            'shipping_country_code' : shop_details.country.iso2_code
            }

        if settings.SINGLE_BOX.value:
            log.debug("Using single-box method for ups calculations.")

            box_weight = Decimal("0.00")
            for product in cart.get_shipment_list():
                if product.smart_attr('weight') is None:
                    log.warn("No weight on product (skipping for ship calculations): %s", product)
                else:
                    box_weight += product.smart_attr('weight')
                if product.smart_attr('weight_units') and product.smart_attr('weight_units') != "":
                    box_weight_units = product.smart_attr('weight_units')
                else:
                    log.warn("No weight units for product")

            if box_weight < Decimal("0.1"):
                log.debug("Total box weight too small, defaulting to 0.1")
                box_weight = Decimal("0.1")

            shippingdata['single_box'] = True
            shippingdata['box_weight'] = '%.1f' % box_weight
            shippingdata['box_weight_units'] = box_weight_units.upper()

        total_weight = 0
        for product in cart.get_shipment_list():
            try:
                total_weight += product.smart_attr('weight')
            except TypeError:
                pass

        signals.shipping_data_query.send(Shipper, shipper=self, cart=cart, shippingdata=shippingdata)
        c = Context(shippingdata)
        t = loader.get_template('shipping/ups/request.xml')
        request = t.render(c)
        self.is_valid = False
        if settings.LIVE.value:
            connection = settings.CONNECTION.value
        else:
            connection = settings.CONNECTION_TEST.value

        cachekey = cache_key(
            'UPS_SHIP',
            #service_type = self.service_type_code,
            weight = str(total_weight),
            country = shop_details.country.iso2_code,
            zipcode = contact.shipping_address.postal_code)

        try:
            tree = cache_get(cachekey)
        except NotCachedError:
            tree = None

        if tree is not None:
            self.verbose_log('Got UPS info from cache [%s]', cachekey)
        else:
            self.verbose_log("Requesting from UPS [%s]\n%s", cachekey, request)
            cache_set(cachekey, value=request, length=600)
            tree = self._process_request(connection, request)
            self.verbose_log("Got from UPS [%s]:\n%s", cachekey, self.raw)
            cache_set(cachekey, value=tree)

        try:
            status_code = tree.getiterator('ResponseStatusCode')
            status_val = status_code[0].text
            self.verbose_log("UPS Status Code for cart #%s = %s", int(cart.id), status_val)
        except AttributeError:
            status_val = "-1"

        if status_val == '1':
            self.is_valid = False
            self._calculated = False
            all_rates = tree.getiterator('RatedShipment')
            for response in all_rates:
                if self.service_type_code == response.find('.//Service/Code/').text:
                    self.charges = response.find('.//TotalCharges/MonetaryValue').text
                    if response.find('.//GuaranteedDaysToDelivery').text:
                        self.delivery_days = response.find('.//GuaranteedDaysToDelivery').text
                    self.is_valid = True
                    self._calculated = True

            if not self.is_valid:
                self.verbose_log("UPS Cannot find rate for code: %s [%s]", self.service_type_code, self.service_type_text)

        else:
            self.is_valid = False
            self._calculated = False

            try:
                errors = tree.find('.//Error')
                log.info("UPS %s Error: Code %s - %s" % (errors[0].text, errors[1].text, errors[2].text))
            except AttributeError:
                log.info("UPS error - cannot parse response:\n %s", self.raw)

        if self.is_valid and settings.TIME_IN_TRANSIT.value:
            self.verbose_log('Now getting time in transit for cart')
            self.time_in_transit(contact, cart)

    def time_in_transit(self, contact, cart):
        total = Decimal('0')
        for item in cart.cartitem_set.all():
            if item.is_shippable:
                total += item.line_total

        delivery_days = self.ups_time_in_transit(contact, price=total)
        if delivery_days is not None:
            self.delivery_days = delivery_days

    def ups_time_in_transit(self, contact, pickup_date = None, price=None, test=False):
        """Calculate est delivery days for a zipcode, from Store Zipcode"""

        from satchmo_store.shop.models import Config

        delivery_days = None

        if pickup_date is None:
            pickup_date = datetime.datetime.now() + datetime.timedelta(days=1)

        # UPS doesn't pick up on weekends
        if pickup_date.day == 5:
            pickup_date += datetime.timedelta(days=2)

        if pickup_date.day == 6:
            pickup_date += datetime.timedelta(days=1)

        if price is None:
            price = Decimal('10.0')

        shipaddr = contact.shipping_address
        shop_details = Config.objects.get_current()
        settings =  config_get_group('shipping.modules.ups')

        configuration = {
            'xml_key': settings.XML_KEY.value,
            'account': settings.ACCOUNT.value,
            'userid': settings.USER_ID.value,
            'password': settings.USER_PASSWORD.value,
            'container': settings.SHIPPING_CONTAINER.value,
            'pickup': settings.PICKUP_TYPE.value,
            'shop_details':shop_details,
        }

        shippingdata = {
            'config': configuration,
            'zipcode': shipaddr.postal_code,
            'contact': contact,
            'shipping_address' : shop_details,
            'shipping_phone' : shop_details.phone,
            'shipping_country_code' : shop_details.country.iso2_code,
            'pickup_date' : pickup_date.strftime('%Y%m%d'),
            'price' : "%.2f" % price
        }

        c = Context(shippingdata)
        t = loader.get_template('shipping/ups/transit_request.xml')
        request = t.render(c)

        if settings.LIVE.value and not test:
            connection = 'https://wwwcie.ups.com/ups.app/xml/TimeInTransit'
        else:
            connection = 'https://onlinetools.ups.com/ups.app/xml/TimeInTransit'

        cachekey = cache_key("UPS-TIT", shipaddr.postal_code, pickup_date.strftime('%Y%m%d'), "%.2f" % price)

        try:
            ups = cache_get(cachekey)
        except NotCachedError:
            ups = None

        if ups is None:
            log.debug('Requesting from UPS: %s\n%s', connection, request)
            conn = urllib2.Request(url=connection, data=request.encode("utf-8"))
            f = urllib2.urlopen(conn)
            all_results = f.read()

            self.verbose_log("Received from UPS:\n%s", all_results)
            ups = fromstring(all_results)
            needs_cache = True
        else:
            needs_cache = False

        ok = False
        try:
            ok = ups.find('Response/ResponseStatusCode').text == '1'
        except AttributeError:
            log.warning('Bad response from UPS TimeInTransit')
            pass

        if not ok:
            try:
                response = ups.find('Response/ResponseStatusDescription').text
                log.warning('Bad response from UPS TimeInTransit: %s', response)
            except AttributeError:
                log.warning('Unknown UPS TimeInTransit response')

        if ok:
            services = ups.findall('TransitResponse/ServiceSummary')
            for service in services:
                transit_code = service.find('Service/Code').text
                if self.service_type_code == TRANSIT_CODE_MAP.get(transit_code, ''):
                    try:
                        delivery_days = service.find('EstimatedArrival/BusinessTransitDays').text
                        self.verbose_log('Found delivery days %s for %s', delivery_days, self.service_type_code)
                    except AttributeError:
                        log.warning('Could not find BusinessTransitDays in UPS response')

                    try:
                        delivery_days = int(delivery_days)
                    except ValueError:
                        pass

                    break

            if delivery_days is not None and needs_cache:
                cache_set(cachekey, value=ups, length=600)

        return delivery_days

    def verbose_log(self, *args, **kwargs):
        if config_value('shipping.modules.ups', 'VERBOSE_LOG'):
            log.debug(*args, **kwargs)


