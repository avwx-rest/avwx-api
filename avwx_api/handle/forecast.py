"""Handle forecast report requests."""

import avwx

from avwx_api.handle.base import ReportHandler


class MavHandler(ReportHandler):
    parser = avwx.Mav


class MexHandler(ReportHandler):
    parser = avwx.Mex


class NbhHandler(ReportHandler):
    parser = avwx.Nbh


class NbsHandler(ReportHandler):
    parser = avwx.Nbs


class NbeHandler(ReportHandler):
    parser = avwx.Nbe


class NbxHandler(ReportHandler):
    parser = avwx.Nbx
