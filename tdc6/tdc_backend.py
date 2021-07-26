# -*- coding: utf-8 -*-
import time
from decimal import Decimal, getcontext

import ftd2xx as ftd
import tdc_defines as defines

from .tdc_timeout import SetTimeout, TimeoutError
# HIGH PRECISION NUMBERS
getcontext().prec = 28


USB_ERROR_TEMPLATE = "USB ERROR: %s"
TDC_ERROR_TEMPLATE = "TDC ERROR: %s"
OP_ERR = "%s is FAILED"


def SHIFT_SYMBOL(c): return [
    defines.ByteConstants.SHIFT, c - defines.ByteConstants.START]


def UNSHIFT_SYMBOL(c): return defines.ByteConstants.START + c
def CMD_TEMPLATE(cmd, chsum): return bytes(
    [defines.ByteConstants.START, *cmd, chsum, defines.ByteConstants.END])


def FROM_BYTES(x): return ":".join("%.02x" % c for c in x)
def UNPACK_NUM(x): return x[0] * 0x100 + x[1]


DEBUG = True
TIME = False

"""=============== EVENT STRUCTURE AND FOLLOWING ========================="""


def b_bin(T):
    return sum(T[i] << 8 * i for i in range(6))


def b_ch(T):
    return T[-1] >> 5


def b_adcdata(T):
    return T[-2] + (T[-1] & 0b00001111) * 256


def b_errcode(T):
    return (T[-1] & 0b00010000) >> 4


class Event:

    def __init__(self, T):
        if len(T) != 8:
            raise ValueError("Event: Need 8 bytes to unpack")
        self.ch = b_ch(T) + 1
        if self.ch < 1 or self.ch > defines.CHANNELS_NUMBER + 1:
            raise ValueError(
                "Event: Channel number must be in [1, %d]" % defines.CHANNELS_NUMBER + 1)
        self.rbin = b_bin(T)
        if self.rbin < 0:
            raise ValueError("Event: Timebin must be > 0")
        self.adcd = b_adcdata(T)
        if self.adcd < 0 or self.adcd > defines.ADC_CAPACITY:
            raise ValueError(
                "Event: ADC count must be in [0, %d]" % defines.ADC_CAPACITY)
        self.err = b_errcode(T)

    def construct_bin(self, CF):
        self.bin = int(Decimal(self.rbin + CF[self.adcd]) *
                       Decimal(defines.BIN_TIMELEN * 1e12))

    def unpack(self):
        return str(self.bin), str(self.ch)

    def __lt__(self, other):
        return self.bin < other.bin

    def __repr__(self):
        return "<E ch:%d rbin:%d adcd:%d err:%d>" % (self.ch, self.rbin, self.adcd, self.err)


"""========================== COMMAND AND DATA STRUCTURES ========================="""


def checksum(cmd):
    cmd_chsum = 0
    for c in cmd:
        cmd_chsum ^= c
    return cmd_chsum


class TCommand:

    def __init__(self, cmd, *args):
        cmd = [defines.NODE_ADDRESS, *cmd, *args]
        self.cmd = CMD_TEMPLATE(self.packed_data(*cmd), checksum(cmd))

    def packed_data(self, *cmd):
        # First two bytes - node address and command are not shifted
        for c in cmd:
            r = SHIFT_SYMBOL(c) if c in defines.ByteConstants.values() else [c]
            yield from r


class TRecievedData:

    def __init__(self, _rdata):

        if DEBUG:
            print("RECIEVED DATA LEN", len(_rdata))
            print("RECIEVED DATA", FROM_BYTES(_rdata))

        _rdata = _rdata.split(b'%d' % defines.ByteConstants.END)[0]

        if not _rdata:
            raise ValueError(TDC_ERROR_TEMPLATE %
                             "NULL data recieved. See TDC_WRITE_TIMEOUT")

        # First two bytes - node address and command are not shifted
        if _rdata[0] == defines.ByteConstants.START:
            _rdata.pop(0)
        else:
            raise ValueError(TDC_ERROR_TEMPLATE %
                             "Bad start symbol in recieved data")

        if _rdata[-1] == defines.ByteConstants.END:
            _rdata.pop()
            if _rdata[-2] != defines.ByteConstants.SHIFT:
                chsum = _rdata.pop()
            else:
                chsum = UNSHIFT_SYMBOL(_rdata.pop())
                _rdata.pop()
        else:
            raise ValueError(TDC_ERROR_TEMPLATE %
                             "Bad end symbol in recieved data")

        self.rdata = bytearray()
        while _rdata:
            c = _rdata.pop(0)
            if c == defines.ByteConstants.SHIFT:
                self.rdata.append(UNSHIFT_SYMBOL(_rdata.pop(0)))
            else:
                self.rdata.append(c)
        if checksum(self.rdata) != chsum:
            print(FROM_BYTES(self.rdata))
            raise ValueError(TDC_ERROR_TEMPLATE %
                             "Data checksum mismatch %s != %s" % (checksum(self.rdata), chsum))

        self.len = len(self.rdata)

    def __repr__(self):
        return FROM_BYTES(self.rdata)


"""=================== TDC CLASS =====================\
        docs are coming soon"""


class TDCDevice:

    device = None

    def __init__(self,
                 read_timeout=defines.FTDI_TIMEOUT,
                 write_timeout=defines.FTDI_TIMEOUT):
        # Connect to first FTDI chip in devices list
        try:
            self.device = ftd.open(0)
        except Exception as E:
            raise ftd.DeviceError(USB_ERROR_TEMPLATE % E)

        if self.device.type == ftd.ftd2xx.DEVICE_2232H:
            print("=== FTDI 2232H is used ===")
        elif self.device.type == ftd.ftd2xx.DEVICE_232R:
            print(
                """=== FTDI 232R is used ===\n
                === Working boudrate may be decreased
                """)
        else:
            raise ftd.DeviceError("Unknown type of USB device:\n\t%s (type %d)\n" %
                                  (self.device.description, self.device.type))
        if self.device.resetDevice():
            raise ftd.DeviceError(
                USB_ERROR_TEMPLATE % (OP_ERR % "FT_ResetDevice"))
        if self.device.purge():
            raise ftd.DeviceError(
                USB_ERROR_TEMPLATE % (OP_ERR % "FT_Purge"))
        # set RX/TX timeouts
        if self.device.setTimeouts(read_timeout, write_timeout):
            raise ftd.DeviceError(
                USB_ERROR_TEMPLATE % (OP_ERR % "FT_SetTimeouts"))
        #self.device.setBaudRate(int(2 * 10**6))

    def _cmd_exchange(self, cmd, data_size, *args):
        if TIME:
            t = time.time()
        cmd = TCommand(cmd, *args)
        self.write(cmd.cmd)
        if TIME:
            print("C", time.time() - t)
        return self.read(data_size)

    def cmd_exchange(self, cmd, *args, data_size=16):
        data = self._cmd_exchange(cmd, data_size, *args)
        return TRecievedData(data).rdata

    def read_cmd_exchange(self, cmd, *args, data_size):
        return self._cmd_exchange(cmd, data_size, *args)

    def write(self, cmd):
        try:
            msg_len = self.device.write(cmd)
            if DEBUG:
                print('%d bytes: "%s" was sent'
                      % (msg_len, FROM_BYTES(cmd)))
        except Exception as E:
            raise ftd.DeviceError(
                USB_ERROR_TEMPLATE % ('Error in writing cmd "%s": %s' % (FROM_BYTES(cmd), E)))

    def read(self, data_size):
        if TIME:
            t = time.time()
        try:
            data = bytearray(self.device.read(2 * data_size))
            if defines.ByteConstants.END not in data:
                while defines.ByteConstants.END not in data:
                    data += self.device.read(data_size)
        except TimeoutError:
            return bytearray()
        if TIME:
            print("T", time.time() - t)
        return data.split(b'%d' % defines.ByteConstants.END)[0]

    def reset_pointers(self):
        return self.cmd_exchange(defines.Commands.RESET_POINTERS)

    def get_init_r_pointer(self):
        return self.cmd_exchange(defines.Commands.R_ADDR)

    def get_curr_w_pointer(self):
        cwp1, cwp2 = self.cmd_exchange(defines.Commands.W_ADDR)
        # Cous of the first bit is always zero
        return bytearray([cwp1 & 0x7f, cwp2])

    def _read_bramblock(self, init_r_pointer, curr_w_pointer):
        data_size = UNPACK_NUM(curr_w_pointer) - UNPACK_NUM(init_r_pointer)
        byte_data_size = bytearray([data_size // 0x100, data_size % 0x100])
        if DEBUG:
            print(">> DATA SIZE", data_size)
            print(">> TEST POINTERS", FROM_BYTES(
                curr_w_pointer), FROM_BYTES(init_r_pointer))
        try:
            if TIME:
                t = time.time()
            with SetTimeout(defines.MAX_READ_TIMEOUT):
                d = self.read_cmd_exchange(defines.Commands.R_BRAMBLK,
                                           *init_r_pointer,
                                           *byte_data_size,
                                           data_size=data_size)
            if TIME:
                print("D", time.time() - t)
        except TimeoutError:
            return bytearray(), True
        return d, False

    def read_bramblock(self, init_r_pointer, curr_w_pointer):
        t = time.time()
        if curr_w_pointer < init_r_pointer:
            d1, err1 = self._read_bramblock(
                init_r_pointer, defines.HADDR_BOUND)
            d2, err2 = self._read_bramblock(
                defines.LADDR_BOUND, curr_w_pointer)
            return [d1, d2], err1 | err2, time.time() - t
        elif curr_w_pointer > init_r_pointer:
            d, err = self._read_bramblock(init_r_pointer, curr_w_pointer)
            return [d], err, time.time() - t

    def connected(self):
        return self.device.status

    def device_info(self):
        return self.device.getDeviceInfo()

    def disconnect(self):
        return self.device.close()
