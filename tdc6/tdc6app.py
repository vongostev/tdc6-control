# -*- coding: utf-8 -*-
import sys
import time
import argparse

import ftd2xx

import tdc6util
import tdc_backend

if __name__ != "__main__":
    sys.exit()

sys.stderr.write("=========================================================\n")
ARGS = argparse.ArgumentParser()
ARGS.add_argument(
    "--fname",
    default='/dev/null',
    help="File to save obtained data",
    type=str)
ARGS.add_argument(
    "-t", "--timeout",
    help="Time for reading process, s",
    type=float)
ARGS.add_argument(
    "-n", "--count",
    help="Reading events count",
    type=int)
ARGS.add_argument(
    "-c", "--calibration",
    help="Channels for calibration",
    type=str)
ARGS.add_argument(
    "--test",
    help="Do self-testing",
    type=str)
ARGS = ARGS.parse_args()

if not ftd2xx.listDevices():
    sys.stderr.write(tdc_backend.USB_ERROR_TEMPLATE %
                     "Device is not found. Check your cable\n")
    sys.exit()

TDC = tdc_backend.TDCDevice()
if not TDC.connected():
    sys.exit()

sys.stderr.write("TDC (SN %s) is connected\n" %
                 TDC.device_info()['serial'].decode('utf-8'))

# Commands to prepare device: reset read and write pointers
try:
    TDC.reset_pointers()
except Exception as E:
    sys.stderr.write(tdc_backend.TDC_ERROR_TEMPLATE % (
        "Can not reset pointers: \n=== %s\n=== Check installation\n" % E))
    sys.exit()

r = tdc6util.TDataCollector(TDC, ARGS.calibration)

start_time = time.time()
if ARGS.fname == '/dev/null':
    sys.stderr.write("WARNING: All data will be save in /dev/null\n")
if ARGS.count:
    r.read_by_count(ARGS.count)
elif ARGS.timeout:
    r.read_by_timeout(ARGS.timeout)
elif ARGS.calibration:
    sys.stderr.write(
        "\nCALIBRATION OF CHANNELS %s IS IN PROGRESS...\n" % ','.join(ARGS.calibration))
    r.make_cf(ARGS.calibration)
    sys.stderr.write(
        "\nCALIBRATION DATA FOR CHANNELS %s IS STORED\n" % ','.join(ARGS.calibration))
elif ARGS.test:
    import tdc6test
    ch1, ch2 = map(int, ARGS.test)
    t = tdc6test.TDeviceTests(r)
    #t.test_device_function(ch1, ch2)
    t.test_calibration_capacity(1000, 100000, step=10000, ch1=ch1, ch2=ch2)
    TDC.disconnect()
    sys.exit()


sys.stderr.write("PASS TIME %.2f SECONDS\n" % (time.time() - start_time))
if not ARGS.calibration:
    r.save_data(ARGS.fname)

TDC.disconnect()
