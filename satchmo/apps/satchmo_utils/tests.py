from decimal import Decimal
from django.test import TestCase
from satchmo_utils.numbers import round_decimal, trunc_decimal
from satchmo_utils.unique_id import slugify

class TestRoundedDecimals(TestCase):

    def testRoundingDecimals(self):
        """Test Partial Unit Rounding Decimal Conversion behavior"""
        val = round_decimal(val=3.40, places=5, roundfactor=.5, normalize=True)
        self.assertEqual(val, Decimal("3.5"))

        val = round_decimal(val=3.40, places=5, roundfactor=-.5, normalize=True)
        self.assertEqual(val, Decimal("3"))

        val = round_decimal(val=0, places=5, roundfactor=-.5, normalize=False)
        self.assertEqual(val, Decimal("0.00000"))

        val = round_decimal(0, 5, -.5, False)
        self.assertEqual(val, Decimal("0.00000"))

        val = round_decimal(0)
        self.assertEqual(val, Decimal("0"))

        val = round_decimal(3.23,4,-.25)
        self.assertEqual(val, Decimal("3"))

        val = round_decimal(-3.23,4,-.25)
        self.assertEqual(val, Decimal("-3"))
        val = round_decimal(-3.23,4,.25)
        self.assertEqual(val, Decimal("-3.25"))

        val = round_decimal(3.23,4,.25)
        self.assertEqual(val, Decimal("3.25"))

        val = round_decimal(3.23,4,.25,False)
        self.assertEqual(val, Decimal("3.2500"))

        val = round_decimal(3.23,1,.25,False)
        self.assertEqual(val, Decimal("3.2"))

        val = round_decimal(2E+1, places=2)
        self.assertEqual(val, Decimal('20.00'))

    def testTruncDecimal(self):
        """Test trunc_decimal's rounding behavior."""
        # val = trunc_decimal("0.004", 2)
        # self.assertEqual(val, Decimal("0.00"))
        val = trunc_decimal("0.005", 2)
        self.assertEqual(val, Decimal("0.01"))
        val = trunc_decimal("0.009", 2)
        self.assertEqual(val, Decimal("0.01"))

        val = trunc_decimal("2E+1", places=2)
        self.assertEqual(val, Decimal('20.00'))

        val = trunc_decimal(2.1E+1, places=2)
        self.assertEqual(val, Decimal('21.00'))

        val = trunc_decimal(2.1223E+1, places=2)
        self.assertEqual(val, Decimal('21.23'))

        val = trunc_decimal("2.1223E+1", places=2)
        self.assertEqual(val, Decimal('21.23'))


class TestSlugify(TestCase):
    def testSlugify(self):
        # 3x A acute + 2x S caron
        val = slugify('&Aacute;&#193;&#xc1;&#352;&#x160;')
        self.assertEqual(val, 'aaass')
        # the same with disabled all "&" conversions (is not nice)
        val = slugify('&Aacute;&#193;&#xc1;&#352;&#x160;', entities=False, decimal=False, hexadecimal=False)
        self.assertEqual(val, 'aacute-193-xc1-352-x160')
        # A acute + S caron
        val = slugify(u'\xc1\u0160')
        self.assertEqual(val, 'as')
        # Greek alpha beta gamma can not be converted to ascii
        val = slugify('&alpha;&beta;&gamma;')
        self.assertEqual(val, '')
        # arguments instance, slug_field and filter_dict can be better tested in 'product' tests

