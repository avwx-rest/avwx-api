"""
"""

# module
import avwx
from avwx_api.handle.base import ReportHandler


class MavHandler(ReportHandler):
    """
    """

    report_type = "mav"
    parser = avwx.Mav


class MexHandler(ReportHandler):
    """
    """

    report_type = "mex"
    parser = avwx.Mex
