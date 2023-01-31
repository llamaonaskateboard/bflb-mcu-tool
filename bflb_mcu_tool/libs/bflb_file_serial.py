# -*- coding: utf-8 -*-

import os
import sys
import serial
import hashlib
from binascii import *
from libs import bflb_utils

try:
    from serial.tools.list_ports import comports
except ImportError:
    raise exception.GetSerialPortsError(os.name)


class FileSerial(object):

    def _int_to_hex(self, data):
        hex_size = hex(data).replace("0x", "0x00")[-4:]
        low_hex_size = hex_size[-2:]
        hight_hex_size = hex_size[:-2]
        return low_hex_size, hight_hex_size

    def _str_to_hex(self, data):
        message = hexlify(data)
        new_message = ""
        for i in range(0, len(message), 2):
            new_message += message[i:i + 2].decode() + " "
        return new_message

    def _get_file_hash(self, file_path):
        with open(file_path, "rb") as f:
            message = f.read()

        data_sha = hashlib.sha256()
        data_sha.update(message)
        return data_sha.hexdigest()

    def open_listen(self, dev_com, baudrate, file_path, chunk_size=4096, timeout=1):
        sdio_file_ser_dict = {}
        file_dict = {}

        if sys.platform.startswith("win"):
            for p, d, h in comports():
                if not p:
                    continue
                if "PID=1D6B" in h.upper():
                    ser_value = h.split(" ")[2][4:]
                    if ser_value not in sdio_file_ser_dict:
                        sdio_file_ser_dict[ser_value] = p
                    else:
                        if "LOCATION" in h.upper():
                            file_dict[sdio_file_ser_dict[ser_value]] = p
                        else:
                            file_dict[p] = sdio_file_ser_dict[ser_value]
        elif sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
            for p, d, h in comports():
                if not p:
                    continue
                if "PID=1D6B" in h.upper():
                    ser_value = h.split(" ")[2][4:]
                    if ser_value not in sdio_file_ser_dict:
                        sdio_file_ser_dict[ser_value] = p
                    else:
                        if sdio_file_ser_dict[ser_value] > p:
                            file_dict[p] = sdio_file_ser_dict[ser_value]
                        else:
                            file_dict[sdio_file_ser_dict[ser_value]] = p

        if " (" in dev_com:
            sdio_dev = dev_com[:dev_com.find(" (")]
        else:
            sdio_dev = dev_com
        file_com = file_dict[sdio_dev]
        print(file_com)
        _ser = serial.Serial(file_com,
                             int(baudrate),
                             timeout=5.0,
                             xonxoff=False,
                             rtscts=False,
                             write_timeout=None,
                             dsrdtr=False)
        _ser.timeout = timeout
        size = os.path.getsize(file_path)
        hex_size = hex(size).replace("0x", "0x0000000")
        first_message = bytes.fromhex("F0 00 04 00 {} {} {} {}".format(
            hex_size[-2:], hex_size[-4:-2], hex_size[-6:-4], hex_size[-8:-6]))
        _ser.write(first_message)
        recv_message = _ser.read(2)

        if recv_message != b"OK":
            _ser.close()
            bflb_utils.printf("Send Failed! Error 1: First send failed")
            return False

        with open(file_path, "rb") as f:
            while True:
                message = f.read(chunk_size)
                if message:
                    len_mess = len(message)
                    low_middle_size, hight_middle_size = self._int_to_hex(len_mess)
                    if recv_message == b"OK":
                        recv_message = b""
                        new_message = self._str_to_hex(message)
                        middle_message = bytes.fromhex("F1 00 {} {} {}".format(
                            low_middle_size, hight_middle_size, new_message))
                        _ser.write(middle_message)
                        recv_message = _ser.read(2)
                        message = ""
                    else:
                        _ser.close()
                        bflb_utils.printf("Send Failed! Error 2: File send failed")
                        return False
                else:
                    break
        recv_message = b""
        end_message = bytes.fromhex("F2 00 00 00")
        _ser.write(end_message)

        recv_message = _ser.read(66)
        if b"OK" in recv_message:
            file_sha256 = self._get_file_hash(file_path)
            if recv_message[2:].hex() == file_sha256:
                _ser.write(b"check hash")
                _ser.close()
                return True
            else:
                _ser.close()
                bflb_utils.printf("Send Failed! Error 4: Hash check failed")
                return False
        else:
            _ser.close()
            bflb_utils.printf("Send Failed! Error 3: Hash return failed")
            return False


if __name__ == "__main__":
    fs = FileSerial()
    fs.open_listen("/dev/ttyACM1", 2000000,
                   "/home/tanjiaxi/git/bouffalo_dev_cube/chips/bl602/img_create_mcu/img_if.bin")
