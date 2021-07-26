# -*- coding: utf-8 -*-
import os
"""COMMUNICATION CONSTANTS"""

MAX_PACKET_SIZE = 0x40
BUFF_SIZE = 0x7fff
LADDR_BOUND = bytearray([0x00] * 2)
HADDR_BOUND = bytearray([0x7f, 0xff])
FTDI_TIMEOUT = 1  # milliseconds
TDC_WRITE_TIMEOUT = 5  # seconds
NODE_ADDRESS = 0x01

TIMESTAMP_LEN = 8
BIN_TIMELEN = 12.5e-9
ADC_CAPACITY = 2 ** 12
HIST_CAPACITY = 100000
CHANNELS_NUMBER = 4

MAX_READ_TIMEOUT = 2

CALIBRATION_HELPER = os.path.join("CAH", "%d.calibration_helper")


class TConstants:

    @classmethod
    def values(cls):
        return cls.__dict__.values()


class RecievedShiftedBytes(TConstants):

    START = 0x00
    END = 0x01
    SHIFT = 0x02


class ByteConstants(TConstants):

    START = 0xfd
    END = 0xfe
    SHIFT = 0xff
    #OKREPLY_CODE = b'\xda'
    #EMPTYCOMM_BYTE = b'\xdb'


class Commands(TConstants):

    ECHO = [0x0f]
    GETID = [0x0e]
    RESET_POINTERS = [0x14, 0xff]  # \x14\xff
    W_BRAMBLK = [0x11]  # Get write pointer
    R_BRAMBLK = [0x12]  # Read BRAM block from #### size ####
    W_ADDR = [0x13]  # Get current write address
    R_ADDR = [0x10]  # Get current read address


class Errors(TConstants):

    LENGHT_MISMATCH = 0xe0
    CHECKSUM_MISMATCH = 0xe1
    CMD_ABSENT = 0xe2
    BAD_START = 0xfd
    BAD_END = 0xfe
