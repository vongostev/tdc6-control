# -*- coding: utf-8 -*-
import numpy as np

import matplotlib.pyplot as plt
import tdc_defines as defines

DEBUG = True


class TCalibrationHelper:

    ch = None
    zeros = np.zeros(defines.ADC_CAPACITY)

    def __init__(self, ch, events):
        if ch < 1 or ch > defines.CHANNELS_NUMBER + 1:
            raise ValueError(
                "Calibration: Channel to calibrate must be number from 1 to %d"
                % defines.CHANNELS_NUMBER + 1)
        if not events:
            raise ValueError("Calibration: No data were registered")
        self.ch = ch
        self.events = [e.adcd for e in events if e.ch == ch]
        if not self.events:
            raise ValueError(
                "Calibration: No data for channel %d were registered" % ch)
        self.N = len(self.events)
        self._make_histogram()

    def _make_histogram(self):
        self.histogram = np.copy(self.zeros)
        for adcd in self.events:
            self.histogram[adcd] += 1
        print(self.histogram)
        if DEBUG:
            plt.plot(self.histogram)
            X = np.arange(defines.ADC_CAPACITY)
            plt.plot(X, np.vectorize(self.CF)(X))
            plt.show()

    def CF(self, n):
        return 1 - np.sum(self.histogram[:n]) / self.N
