"""
Michael duPont - michael@mdupont.com
tests/test_validators.py - Test parameter validators
"""

# library
import pytest
from voluptuous import Invalid
# module
import avwx_api.validators as validators

def test_splitin():
    """
    Tests that SplitIn returns a split string only containing certain values
    """
    validator = validators.SplitIn(('test', 'values', 'here'))
    good_strings = (
        'test,values,here',
        'here',
        'values,test'
    )
    for string in good_strings:
        assert string.split(',') == validator(string)
    bad_strings = (
        'testvalues',
        'test,stuff',
        'crazy,nulls',
        'what?'
        'really,'
    )
    for string in bad_strings:
        with pytest.raises(Invalid):
            validator(string)
