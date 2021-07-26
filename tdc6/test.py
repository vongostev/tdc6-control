# -*- coding: utf-8 -*-
import os
import numpy as np
from matplotlib import pyplot as plt


def FWHM(X, Y):
    half_max = np.max(Y) / 2.
    # find when function crosses line half_max (when sign of diff flips)
    # take the 'derivative' of signum(half_max - Y[])
    d = np.where(Y - half_max >= 0)
    # find the left and right most indexes
    return X[d[0]] - X[d[-1]]


def histogram_FWHM(events, ch1, ch2):
    timelist = []
    for i in range(len(events) - 1):
        if events[i].ch == ch1 and events[i + 1].ch == ch2:
            timelist.append(events[i].bin - events[i + 1].bin)
            if events[i].ch == ch2 and events[i + 1].ch == ch1:
                timelist.append(events[i + 1].bin - events[i].bin)
    times = np.array(timelist)
    hist, bins = np.histogram(times, bins=351)
    return FWHM(bins, hist)


class TDeviceTests:

    def __init__(self, tdc_thread):
        self.tdevice = tdc_thread

    def get_test_data(self, ch1, ch2, data_size):
        self.tdevice.read_by_count(data_size)
        self.tdevice.collect_events_data()
        self.tdevice.make_binned_data()
        chs_edata = [
            e for e in self.tdevice.events_data
            if e.ch == ch1 or e.ch == ch2]
        chs_edata.sort(key=lambda x: x.bin)
        return chs_edata

    def test_device_function(self, ch1, ch2, data_size=5000):
        chs_edata = self.get_test_data(ch1, ch2, data_size)

        temp_file = "chan[%d,%d]_diff_data.txt" % (ch1, ch2)
        lines = ['\t'.join(T.unpack()) for T in chs_edata]
        with open(temp_file, "w") as f:
            f.write('\n'.join(lines))
        os.system("python histogram.py %s --start=-1 --end=1" % temp_file)

    def test_calibration_capacity(self, n_from, n_to, step=10000, ch1=1, ch2=2):
        hwidths = []
        for n in range(n_from, n_to, step):
            self.tdevice.make_cf("%d%d" % (ch1, ch2), N=n)
            self.tdevice._get_calibration_helpers()
            chs_edata = self.get_test_data(ch1, ch2, n)
            width = histogram_FWHM(chs_edata, ch1, ch2)
            hwidths.append(width)
        plt.plot(np.arange(n_from, n_to, step), hwidths)
        plt.show()
