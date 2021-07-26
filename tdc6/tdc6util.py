# -*- coding: utf-8 -*-
import time
import sys
import pickle
import asyncio
import itertools

import numpy as np

import tdc_defines as defines
from tdc_backend import Event, TDC_ERROR_TEMPLATE, TRecievedData
from tdc6calibration import TCalibrationHelper


DEBUG = True


class TDataCollector:

    CAHS = {}
    data = []
    events_data = []

    def __init__(self, tdc_device, calibration=False):
        self.device = tdc_device
        if not calibration:
            self._get_calibration_helpers()

    def _get_calibration_helpers(self):
        for ch in range(1, defines.CHANNELS_NUMBER + 1):
            try:
                with open(defines.CALIBRATION_HELPER % ch, "rb") as f:
                    cur_helper = pickle.load(f)
                if not any(cur_helper.histogram):
                    raise IndexError
                self.CAHS[ch] = np.vectorize(cur_helper.CF)(
                    np.arange(defines.ADC_CAPACITY))
            except (FileNotFoundError, IndexError) as E:
                sys.stderr.write(
                    TDC_ERROR_TEMPLATE % """
                    There are no calibration data for channel %d:
                    %s
                    Use --calibration=%d argument\n
                    """ % (ch, E, ch))
                sys.exit()

    def get_pointers(self):
        init_r_pointer = self.device.get_init_r_pointer()
        #!!!TODO:HACK TO NEUTRALIZE BAD START BYTE
        if init_r_pointer[1] > 0:
            init_r_pointer[1] -= 1
        curr_w_pointer = self.device.get_curr_w_pointer()
        return init_r_pointer, curr_w_pointer

    def read_by_pointers(self):
        while True:
            ip, cp = self.get_pointers()
            d1, d2 = map(lambda x: x[0] - x[1], zip(cp, ip))
            delta = d1 * 0x100 + d2
            if delta > 1000 * defines.TIMESTAMP_LEN or cp < ip:
                return self.device.read_bramblock(ip, cp)

    def read_by_count(self, events_count=defines.BUFF_SIZE / defines.TIMESTAMP_LEN):
        while events_count > 0:
            d, err, t = self.read_by_pointers()
            if err:
                continue
            self.data.append(d)
            events_count -= len(b''.join(d)) // defines.TIMESTAMP_LEN
            print('.', end="", flush=True)
        print()

    def read_by_timeout(self, timeout):
        while timeout > 0:
            timeout += time.time()
            d, err, t = self.read_by_pointers()
            timeout -= time.time()
            if err:
                if DEBUG:
                    print("\nNo data. Terminated by timeout\n")
                continue
            self.data.append(d)
            print('.', end="", flush=True)
        print()

    async def _make_events_data(self, d):
        _d = b''.join(TRecievedData(x).rdata for x in d)
        _d = _d[:-(len(_d) % defines.TIMESTAMP_LEN)]
        nd = np.frombuffer(_d, np.uint8).reshape(-1, defines.TIMESTAMP_LEN)

        evd = [Event(t) for t in nd]
        evd = [T for T in evd if not T.err]
        self.events_data.append(evd)

    def collect_events_data(self):
        collecting_loop = asyncio.get_event_loop()
        tasks = asyncio.gather(*[self._make_events_data(d) for d in self.data])
        collecting_loop.run_until_complete(tasks)
        self.events_data = list(itertools.chain(*self.events_data))

    def make_binned_data(self):
        for T in self.events_data:
            if T.ch not in self.CAHS.keys():
                raise ValueError(
                    TDC_ERROR_TEMPLATE % "\n=== Channel %d is uncalibrated" % T.ch)
            T.construct_bin(self.CAHS[T.ch])
        self.events_data.sort(key=lambda x: x.bin)

    def make_cf(self, chs, N=defines.HIST_CAPACITY):
        chs = [int(c) for c in chs]
        self.read_by_count(N * len(chs))
        self.collect_events_data()

        for ch in chs:
            cfc = TCalibrationHelper(ch, self.events_data)
            with open(defines.CALIBRATION_HELPER % ch, 'wb') as store_file:
                pickle.dump(cfc, store_file)
            sys.stderr.write("HELPER FOR CHANNEL %d IS STORED\n" % ch)

    def save_data(self, fname):
        self.collect_events_data()
        self.make_binned_data()

        lines = ['\t'.join(T.unpack()) for T in self.events_data]
        with open(fname, "w") as f:
            f.write('\n'.join(lines))

        sys.stderr.write("%d EVENTS ARE STORED TO '%s'\n" %
                         (len(lines), fname))
