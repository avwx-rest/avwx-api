"""
Handle forecast report requests
"""

# pylint: disable=missing-class-docstring

# module
import avwx
from avwx_api.handle.base import ReportHandler


class MavHandler(ReportHandler):
    parser = avwx.Mav


class MexHandler(ReportHandler):
    parser = avwx.Mex
