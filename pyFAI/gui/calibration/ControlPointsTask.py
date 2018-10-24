# coding: utf-8
# /*##########################################################################
#
# Copyright (C) 2016-2018 European Synchrotron Radiation Facility
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# ###########################################################################*/

from __future__ import absolute_import
from scipy.stats._continuous_distns import chi

__authors__ = ["V. Valls"]
__license__ = "MIT"
__date__ = "24/10/2018"

import logging
import numpy

from silx.gui import qt
import silx.gui.plot
import silx.gui.icons

import pyFAI.utils
from pyFAI.gui.calibration.AbstractCalibrationTask import AbstractCalibrationTask
from . import utils
from .CalibrationContext import CalibrationContext
from ..utils import validators
from .helper.MarkerManager import MarkerManager

_logger = logging.getLogger(__name__)


class ControlPointsPlot(qt.QFrame):

    def __init__(self, parent=None):
        super(ControlPointsPlot, self).__init__(parent)

        self.__invalidated = False

        self.__plot = self.__createPlot(self)
        self.__ringItems = {}
        self.__pixelBasedPlot = False

        layout = qt.QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.addWidget(self.__plot)

        # markerModel = CalibrationContext.instance().getCalibrationModel().markerModel()
        # self.__markerManager = MarkerManager(self.__plot, markerModel)

        colormap = CalibrationContext.instance().getRawColormap()
        self.__plot.setDefaultColormap(colormap)

    def getDefaultColormap(self):
        return self.__plot.getDefaultColormap()

    def __createPlot(self, parent):
        plot2d = silx.gui.plot.PlotWidget(parent)
        plot2d.setGraphXLabel("Radial")
        plot2d.setGraphYLabel("Azimuthal")

        from silx.gui.plot import tools
        toolBar = tools.InteractiveModeToolBar(parent=self, plot=plot2d)
        plot2d.addToolBar(toolBar)

        toolBar = tools.ImageToolBar(parent=self, plot=plot2d)
        colormapDialog = CalibrationContext.instance().getColormapDialog()
        toolBar.getColormapAction().setColorDialog(colormapDialog)
        previousResetZoomAction = toolBar.getResetZoomAction()
        resetZoomAction = qt.QAction(toolBar)
        resetZoomAction.triggered.connect(self.resetZoom)
        resetZoomAction.setIcon(previousResetZoomAction.icon())
        resetZoomAction.setText(previousResetZoomAction.text())
        resetZoomAction.setToolTip(previousResetZoomAction.toolTip())
        toolBar.insertAction(previousResetZoomAction, resetZoomAction)
        previousResetZoomAction.setVisible(False)
        self.__resetZoomAction = resetZoomAction
        plot2d.addToolBar(toolBar)

        return plot2d

    def resetZoom(self):
        self.__plot.resetZoom()

    def __clear(self):
        """Remove of ring item cached on the plots"""
        for item in self.__ringItems.values():
            legend = item.getLegend()
            if legend.startswith("ring"):
                self.__plot.removeMarker(legend)
            else:
                self.__plot.removeCurve(legend)
        self.__ringItems = {}

    def toPlotUnit(self, tthRad, chiRad):
        # FIXME: Input and output do not have the same order (dangerous)
        if self.__pixelBasedPlot:
            raise TypeError("Not supported for pixel based plots")

        try:
            tth = utils.from2ThRad(tthRad,
                                   unit=self.__radialUnit,
                                   wavelength=self.__wavelength,
                                   directDist=self.__directDist)
        except Exception:
            _logger.debug("Backtrace", exc_info=True)
            tth = None

        if chiRad is not None:
            chi = numpy.rad2deg(chiRad)
        else:
            chi = None

        return chi, tth

    def setProcessingResult(self, result):
        """
        :param IntegrationProcess integrationProcess: Result of the integration
            process
        """
        self.__clear()

        context = CalibrationContext.instance()
        calibrationModel = context.getCalibrationModel()
        calibrant = calibrationModel.experimentSettingsModel().calibrantModel().calibrant()
        wavelength = calibrationModel.fittedGeometry().wavelength().value()
        peaks = calibrationModel.peakSelectionModel()

        self.__radialUnit = result.radialUnit()
        self.__wavelength = result.wavelength()
        self.__directDist = result.directDist()
        ai = result.geometry()
        self.__ai = ai

        items = {}

        # plot rings
        ringAngles = result.ringAngles()
        for ringId, ringAngle in enumerate(ringAngles):
            legend = "ring-%i" % (ringId,)
            color = context.getMarkerColor(ringId, mode="numpy")
            self.__plot.addXMarker(x=ringAngle, color=color, legend=legend)
            item = self.__plot._getMarker(legend)
            items[legend] = item

        # plot control points
        for groupId, ring in enumerate(peaks):
            ringNumber = ring.ringNumber()
            color = ring.color()
            numpyColor = numpy.array([color.redF(), color.greenF(), color.blueF(), 0.5])

            # from IPython.core.debugger import Pdb
            # qt.pyqtRemoveInputHook()
            # Pdb().set_trace()

            coords = numpy.array(ring.coords())
            ay, ax = coords[:, 0], coords[:, 1]
            tth = ai.tth(ay, ax)
            chi = ai.chi(ay, ax)
            chi, tth = self.toPlotUnit(tth, chi)

            legend = "group-%i" % (groupId,)
            self.__plot.addCurve(x=tth, y=chi,
                                 legend=legend,
                                 linestyle=' ',
                                 selectable=False,
                                 symbol='o',
                                 color=numpyColor,
                                 resetzoom=False)
            item = self.__plot.getCurve(legend)
            items[legend] = item

        self.__ringItems = items
        self.resetZoom()

    def setProcessing(self):
        self.__clear()
        self.__processingOverlay = utils.createProcessingWidgetOverlay(self.__plot)

    def unsetProcessing(self):
        if self.__processingOverlay is not None:
            self.__processingOverlay.deleteLater()
            self.__processingOverlay = None


class ControlPointsTask(AbstractCalibrationTask):

    def _initGui(self):
        qt.loadUi(pyFAI.utils.get_ui_file("calibration-controlpoints.ui"), self)
        icon = silx.gui.icons.getQIcon("pyfai:gui/icons/task-cake")
        self.setWindowIcon(icon)

        self.initNextStep()

        self.__dataOutDated = False

        self.__plot = ControlPointsPlot(self)
        layout = qt.QVBoxLayout(self._imageHolder)
        layout.addWidget(self.__plot)
        layout.setContentsMargins(1, 1, 1, 1)
        self._imageHolder.setLayout(layout)

        self._processButton.beforeExecuting.connect(self.__process)
        self._processButton.setDisabledWhenWaiting(True)
        self._processButton.finished.connect(self.__processingFinished)

    def __invalidateData(self):
        if self.isVisible():
            if not self._processButton.isWaiting():
                self._processButton.executeCallable()
            else:
                # integration is processing
                # but data are already outdated
                self.__dataOutdated = True
        else:
            # We can process data later
            self.__dataOutdated = True

    def __widgetShow(self):
        if not self.__integrationUpToDate:
            self._processButton.executeCallable()

    def __updateGuiWhileProcessing(self):
        self.__plot.setProcessing()
        qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)

    def __updateGUIWithProcessResult(self, result):
        self.__plot.setProcessingResult(result)

    def __process(self):
        from .IntegrationTask import IntegrationProcess
        self.__integrationProcess = IntegrationProcess(self.model())

        if not self.__integrationProcess.isValid():
            self.__integrationProcess = None
            return
        self.__updateGuiWhileProcessing()
        self._processButton.setCallable(self.__integrationProcess.run)
        self.__dataOutdated = False

    def __processingFinished(self):
        self.__plot.unsetProcessing()
        qt.QApplication.restoreOverrideCursor()

        self.__updateGUIWithProcessResult(self.__integrationProcess)
        self.__integrationProcess = None
        if self.__dataOutdated:
            # Maybe it was invalidated while priocessing
            self._processButton.executeCallable()

    def _updateModel(self, model):
        # connect model
        model.experimentSettingsModel().calibrantModel().changed.connect(self.__invalidateData)
        model.experimentSettingsModel().changed.connect(self.__invalidateData)
        model.peakSelectionModel().changed.connect(self.__invalidateData)
        model.fittedGeometry().changed.connect(self.__invalidateData)
