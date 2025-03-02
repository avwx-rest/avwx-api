"""Test parameter validators."""

import pytest
from voluptuous import Invalid

from avwx_api import validate


def test_split_in():
    """Tests that SplitIn returns a split string only containing certain values"""
    validator = validate.SplitIn(("test", "values", "here"))
    good_strings = ("test,values,here", "here", "values,test")
    for string in good_strings:
        assert string.split(",") == validator(string)
    bad_strings = ("testvalues", "test,stuff", "crazy,nulls", "what?", "really,")
    for string in bad_strings:
        with pytest.raises(Invalid):
            validator(string)
