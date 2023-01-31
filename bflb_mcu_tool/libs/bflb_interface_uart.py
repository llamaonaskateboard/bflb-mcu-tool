# -*- coding:utf-8 -*-
#  Copyright (C) 2021- BOUFFALO LAB (NANJING) CO., LTD.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all
#  copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#  SOFTWARE.

import os
import sys
import time
import binascii
import serial
import threading
import traceback
from queue import Queue
from queue import Empty

from libs import bflb_utils

try:
    from serial.tools.list_ports import comports
except ImportError:
    raise serial.serialutil.SerialException


class BflbUartPort(object):

    def __init__(self):
        self._device = "COM1"
        self._baudrate = 115200
        self._isp_baudrate = 2000000
        self._ser = None
        self._shakehand_flag = False
        self._chiptype = "bl602"
        self._chipname = "bl602"

    def if_init(self, device, rate, chiptype="bl602", chipname="bl602"):
        try:
            if self._ser is None:
                self._baudrate = rate

                if " (" in device:
                    dev = device[:device.find(" (")]
                else:
                    dev = device
                self._device = dev.upper()

                for i in range(5):
                    try:
                        self._ser = serial.Serial(dev,
                                                  rate,
                                                  timeout=2.0,
                                                  xonxoff=False,
                                                  rtscts=False,
                                                  write_timeout=None,
                                                  dsrdtr=False)
                    except Exception as error:
                        bflb_utils.printf(error)
                        time.sleep(1)
                    else:
                        break
            else:
                self._ser.baudrate = rate
                self._baudrate = rate
            self._602a0_dln_fix = False
            self._chiptype = chiptype
            self._chipname = chipname
        except Exception as e:
            bflb_utils.printf("Error: %s" % e)

    def if_init_tmall(self, device, rate, chiptype="bl602", chipname="bl602"):
        try:
            if self._ser is None:
                self._baudrate = rate

                if " (" in device:
                    dev = device[:device.find(" (")]
                else:
                    dev = device
                self._device = dev.upper()
                self._ser = serial.Serial(None,
                                          rate,
                                          timeout=0.2,
                                          xonxoff=False,
                                          rtscts=False,
                                          write_timeout=None,
                                          dsrdtr=False)
                self._ser.port = dev
                self._ser.dtr = False
                self._ser.rts = False
                self._ser.set_buffer_size(rx_size=12800, tx_size=12800)
                self._ser.open()
            else:
                self._ser.baudrate = rate
                self._baudrate = rate
            self._602a0_dln_fix = False
            self._chiptype = chiptype
            self._chipname = chipname
        except Exception as e:
            bflb_utils.printf("Error: %s" % e)

    def flush_buffers(self):
        if self._ser:
            self._ser.flushInput()
        #self._ser.flushOutput()

    def if_clear_buf(self):
        if self._ser:
            timeout = self._ser.timeout
            self._ser.timeout = 0.1
            self._ser.read_all()
            self._ser.timeout = timeout

    def if_set_rx_timeout(self, val):
        if self._ser:
            self._ser.timeout = val

    def if_set_dtr(self, val):
        if self._ser:
            self._ser.setDTR(val)

    def if_set_rts(self, val):
        if self._ser:
            self._ser.setRTS(val)

    def if_set_isp_baudrate(self, baudrate):
        bflb_utils.printf("isp mode speed: ", baudrate)
        self._isp_baudrate = baudrate

    def if_get_rate(self):
        return self._baudrate

    def if_write(self, data_send):
        # bflb_utils.printf("sending ", binascii.hexlify(data_send))
        if self._ser:
            self._ser.write(data_send)

    def if_raw_read(self):
        if self._ser:
            return self._ser.read(self._ser.in_waiting or 1)

    def if_raw_read_tmall(self):
        if self._ser:
            return self._ser.read(self._ser.in_waiting or 200)

    # this function return bytearray or bytes type
    def if_read(self, data_len):
        data = bytearray(0)
        received = 0
        if self._ser:
            try:
                while received < data_len:
                    if self._ser:
                        tmp = self._ser.read(data_len - received)
                        if len(tmp) == 0:
                            break
                        data += tmp
                        received += len(tmp)
                if len(data) != data_len:
                    return 0, data
                return 1, data
            except Exception as e:
                bflb_utils.printf("Error: %s" % e)
        else:
            return 0, data

    def _if_get_sync_bytes(self, length):
        try:
            data = bytearray(length)
            i = 0
            while i < length:
                data[i] = 0x55
                i += 1
            return data
        except Exception as e:
            bflb_utils.printf("Error: %s" % e)

    def if_set_602a0_download_fix(self, val):
        self._602a0_dln_fix = val

    def if_send_55(self):
        try:
            while True:
                if self._shakehand_flag is True:
                    break
                if self._chiptype == "bl702" or self._chiptype == "bl702l":
                    self._ser.write(self._if_get_sync_bytes(int(0.003 * self._baudrate / 10)))
                else:
                    self._ser.write(self._if_get_sync_bytes(int(0.006 * self._baudrate / 10)))
        except Exception as e:
            bflb_utils.printf("Error: %s" % e)

    def bl_usb_serial_write(self, cutoff_time, reset_revert):
        try:
            boot_revert = 0
            bflb_utils.printf("usb serial port")
            if cutoff_time != 0:
                boot_revert = 0
                if cutoff_time > 1000:
                    boot_revert = 1
            data = bytearray()
            specialstr = bflb_utils.string_to_bytearray("BOUFFALOLAB5555RESET")
            for b in specialstr:
                data.append(b)
            data.append(boot_revert)
            data.append(reset_revert)
            self._ser.write(data)
            time.sleep(0.05)
        except Exception as e:
            bflb_utils.printf("Error: %s" % e)

    def check_bl_usb_serial(self, dev):
        if sys.platform.startswith("win"):
            ports = []
            for p, d, h in comports():
                if "Virtual" in d or not p:
                    continue
                if "PID=FFFF" in h.upper() or "PID=42BF:B210" in h.upper():
                    if p.upper() == dev.upper():
                        return True
        elif sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
            ports = []
            for p, d, h in comports():
                if not p:
                    continue
                if "PID=FFFF" in h.upper() or "PID=42BF:B210" in h.upper():
                    if p.upper() == dev.upper():
                        return True
        else:
            return False
        return False

    # this function return str type
    def if_shakehand(self,
                     do_reset=False,
                     reset_hold_time=100,
                     shake_hand_delay=100,
                     reset_revert=True,
                     cutoff_time=0,
                     shake_hand_retry=2,
                     isp_timeout=0,
                     boot_load=False):
        if self._ser:
            try:
                timeout = self._ser.timeout
                blusbserialwriteflag = False
                if isp_timeout > 0:
                    wait_timeout = isp_timeout
                    self._ser.timeout = 0.1
                    self._shakehand_flag = False
                    # do not auto toggle DTR&RTS
                    cutoff_time = 0
                    do_reset = False
                    # set baudrate to 2000000 for shakehand with boot2
                    baudrate = self._baudrate
                    self.if_init(self._device, self._isp_baudrate, self._chiptype, self._chipname)
                    self._baudrate = baudrate
                    # send reboot to make sure boot2 is running
                    self._ser.write(b"\r\nispboot if\r\nreboot\r\n")
                    # send 5555 to boot2, boot2 jump to bootrom if mode
                    fl_thrx = None
                    fl_thrx = threading.Thread(target=self.if_send_55)
                    fl_thrx.setDaemon(True)
                    fl_thrx.start()

                    bflb_utils.printf("Please Press Reset Key!")
                    # reset low
                    self._ser.setRTS(1)
                    # RC delay is 100ms
                    time.sleep(0.2)
                    # reset high
                    self._ser.setRTS(0)

                    time_stamp = time.time()
                    while time.time() - time_stamp < wait_timeout:
                        if self._chiptype == "bl602" or self._chiptype == "bl702":
                            self._ser.timeout = 0.01
                            success, ack = self.if_read(3000)
                            if ack.find(b'Boot2 ISP Shakehand Suss') != -1:
                                self._shakehand_flag = True
                                if ack.find(b'Boot2 ISP Ready') != -1:
                                    bflb_utils.printf("isp ready")
                                    self.if_write(bytearray.fromhex("a0000000"))
                                    self._ser.timeout = timeout
                                    return "OK"
                        else:
                            success, ack = self.if_read(3000)
                            if ack.find(b'Boot2 ISP Ready') != -1:
                                bflb_utils.printf("isp ready")
                                self._shakehand_flag = True
                        if self._shakehand_flag is True:
                            self._ser.timeout = timeout
                            tmp_timeout = self._ser.timeout
                            self._ser.timeout = 0.1
                            if self._chiptype == "bl602" or self._chiptype == "bl702":
                                self._ser.timeout = 0.5
                                # read 15 byte key word
                                ack = self._ser.read(15)
                                # reduce timeout and read 15 byte again, make sure recv all key word
                                self._ser.timeout = 0.005
                                ack += self._ser.read(15)
                                self._ser.timeout = tmp_timeout
                                bflb_utils.printf("read ready")
                                if ack.find(b'Boot2 ISP Ready') == -1:
                                    bflb_utils.printf("Boot2 isp is not ready")
                                    return "FL"
                                else:
                                    self.if_write(bytearray.fromhex("a0000000"))
                                    return "OK"
                            else:
                                while True:
                                    # clear boot2 log
                                    ack = self.if_raw_read()
                                    if len(ack) == 0:
                                        break
                                time.sleep(0.1)
                                while True:
                                    # clear boot2 log
                                    ack = self.if_raw_read()
                                    if len(ack) == 0:
                                        break
                            self._ser.timeout = tmp_timeout
                            break

                    self._shakehand_flag = True
                    self._ser.timeout = timeout
                    # set actual baudrate
                    self.if_init(self._device, self._baudrate, self._chiptype, self._chipname)
                    time.sleep(2.2)

                if self.check_bl_usb_serial(self._device) and boot_load:
                    blusbserialwriteflag = True
                while shake_hand_retry > 0:
                    # cut of tx rx power and rst
                    if cutoff_time != 0 and blusbserialwriteflag is not True:
                        cutoff_revert = False
                        if cutoff_time > 1000:
                            cutoff_revert = True
                            cutoff_time = cutoff_time - 1000
                        # MP_TOOL_V3 generate rising pulse to make D trigger output low
                        # reset low
                        self._ser.setRTS(1)
                        # RC delay is 100ms
                        time.sleep(0.2)
                        # reset high
                        self._ser.setRTS(0)
                        time.sleep(0.05)
                        # do power off
                        # reset low
                        self._ser.setRTS(1)
                        if cutoff_revert:
                            # dtr high, power off
                            self._ser.setDTR(0)
                        else:
                            # dtr low, power off
                            self._ser.setDTR(1)
                        bflb_utils.printf("tx rx and power off, press the machine!")
                        bflb_utils.printf("cutoff time is ", cutoff_time / 1000.0)
                        time.sleep(cutoff_time / 1000.0)
                        if cutoff_revert:
                            # dtr low, power on
                            self._ser.setDTR(1)
                        else:
                            # dtr high, power on
                            self._ser.setDTR(0)
                        bflb_utils.printf("power on tx and rx ")
                        time.sleep(0.1)
                    else:
                        self._ser.setDTR(0)
                        bflb_utils.printf("default set DTR high ")
                        time.sleep(0.1)
                    if do_reset is True and blusbserialwriteflag is not True:
                        # MP_TOOL_V3 reset high to make boot pin high
                        self._ser.setRTS(0)
                        time.sleep(0.2)
                        if reset_revert:
                            # reset low for reset revert to make boot pin high when cpu rset
                            self._ser.setRTS(1)
                            time.sleep(0.001)
                        reset_cnt = 2
                        if reset_hold_time > 1000:
                            reset_cnt = int(reset_hold_time // 1000)
                            reset_hold_time = reset_hold_time % 1000
                        while reset_cnt > 0:
                            if reset_revert:
                                # reset high
                                self._ser.setRTS(0)
                            else:
                                # reset low
                                self._ser.setRTS(1)
                            # Boot high
                            # self._ser.setDTR(0)
                            time.sleep(reset_hold_time / 1000.0)
                            if reset_revert:
                                # reset low
                                self._ser.setRTS(1)
                            else:
                                # reset high
                                self._ser.setRTS(0)
                            if shake_hand_delay > 0:
                                time.sleep(shake_hand_delay / 1000.0)
                            else:
                                time.sleep(5 / 1000.0)

                            # do reset agian to make sure boot pin is high
                            if reset_revert:
                                # reset high
                                self._ser.setRTS(0)
                            else:
                                # reset low
                                self._ser.setRTS(1)
                            # Boot high
                            # self._ser.setDTR(0)
                            time.sleep(reset_hold_time / 1000.0)
                            if reset_revert:
                                # reset low
                                self._ser.setRTS(1)
                            else:
                                # reset high
                                self._ser.setRTS(0)
                            if shake_hand_delay > 0:
                                time.sleep(shake_hand_delay / 1000.0)
                            else:
                                time.sleep(5 / 1000.0)
                            reset_cnt -= 1
                        bflb_utils.printf("reset cnt: " + str(reset_cnt) + ", reset hold: " +
                                          str(reset_hold_time / 1000.0) + ", shake hand delay: " +
                                          str(shake_hand_delay / 1000.0))
                    if blusbserialwriteflag:
                        self.bl_usb_serial_write(cutoff_time, reset_revert)
                    # clean buffer before start
                    bflb_utils.printf("clean buf")
                    self._ser.timeout = 0.1
                    ack = self._ser.read_all()
                    # change tiemout value when shake hand
                    if self._602a0_dln_fix:
                        self._ser.timeout = 0.5
                    else:
                        self._ser.timeout = 0.1
                    bflb_utils.printf("send sync")
                    # send keep 6ms ,N*10/baudrate=0.01
                    if self._chiptype == "bl702" or self._chiptype == "bl702l":
                        self._ser.write(self._if_get_sync_bytes(int(0.003 * self._baudrate / 10)))
                    else:
                        self._ser.write(self._if_get_sync_bytes(int(0.006 * self._baudrate / 10)))
                    if self._chipname == "bl808":
                        time.sleep(0.3)
                        self._ser.write(bflb_utils.hexstr_to_bytearray("5000080038F0002000000018"))
                    if self._602a0_dln_fix:
                        time.sleep(4)
                    success, ack = self.if_read(1000)
                    bflb_utils.printf("ack is ", binascii.hexlify(ack))
                    if ack.find(b'\x4F') != -1 or ack.find(b'\x4B') != -1:
                        self._ser.timeout = timeout
                        if self._602a0_dln_fix:
                            self._ser.write(bytearray(2))
                        time.sleep(0.03)
                        return "OK"
                    if len(ack) != 0:
                        # peer is alive, but shake hand it's not expected, do again
                        bflb_utils.printf("reshake")
                        if do_reset is False:
                            bflb_utils.printf("sleep")
                            # tmp=0
                            # while tmp<60:
                            #    time.sleep(2)
                            #    bflb_utils.printf("Pls check eflash loader log")
                            #    tmp+=1
                            time.sleep(3)
                    else:
                        bflb_utils.printf("retry")
                    shake_hand_retry -= 1
                self._ser.timeout = timeout
                return "FL"
            except Exception as e:
                bflb_utils.printf("Error: %s" % e)
        else:
            return "FL"

    def if_toggle_boot(self,
                       do_reset=False,
                       reset_hold_time=100,
                       shake_hand_delay=100,
                       reset_revert=True,
                       cutoff_time=0,
                       shake_hand_retry=2,
                       isp_timeout=0,
                       boot_load=False):
        try:
            timeout = self._ser.timeout
            blusbserialwriteflag = False

            if isp_timeout > 0:
                wait_timeout = isp_timeout
                self._ser.timeout = 0.1
                self._shakehand_flag = False
                # do not auto toggle DTR&RTS
                cutoff_time = 0
                do_reset = False
                # set baudrate to 2000000 for shakehand with boot2
                baudrate = self._baudrate
                self.if_init(self._device, self._isp_baudrate, self._chiptype, self._chipname)
                self._baudrate = baudrate
                # send reboot to make sure boot2 is running
                self._ser.write(b"\r\nispboot if\r\nreboot\r\n")
                # send 5555 to boot2, boot2 jump to bootrom if mode
                fl_thrx = None
                fl_thrx = threading.Thread(target=self.if_send_55)
                fl_thrx.setDaemon(True)
                fl_thrx.start()

                bflb_utils.printf("Please Press Reset Key!")
                # reset low
                self._ser.setRTS(1)
                # RC delay is 100ms
                time.sleep(0.2)
                # reset high
                self._ser.setRTS(0)

                time_stamp = time.time()
                while time.time() - time_stamp < wait_timeout:
                    if self._chiptype == "bl602" or self._chiptype == "bl702":
                        self._ser.timeout = 0.01
                        success, ack = self.if_read(3000)
                        if ack.find(b'Boot2 ISP Shakehand Suss') != -1:
                            self._shakehand_flag = True
                            if ack.find(b'Boot2 ISP Ready') != -1:
                                bflb_utils.printf("isp ready")
                                self.if_write(bytearray.fromhex("a0000000"))
                                self._ser.timeout = timeout
                                return "OK"
                    else:
                        success, ack = self.if_read(3000)
                        if ack.find(b'Boot2 ISP Ready') != -1:
                            bflb_utils.printf("isp ready")
                            self._shakehand_flag = True
                    if self._shakehand_flag is True:
                        self._ser.timeout = timeout
                        tmp_timeout = self._ser.timeout
                        self._ser.timeout = 0.1
                        if self._chiptype == "bl602" or self._chiptype == "bl702":
                            self._ser.timeout = 0.5
                            # read 15 byte key word
                            ack = self._ser.read(15)
                            # reduce timeout and read 15 byte again, make sure recv all key word
                            self._ser.timeout = 0.005
                            ack += self._ser.read(15)
                            self._ser.timeout = tmp_timeout
                            bflb_utils.printf("read ready")
                            if ack.find(b'Boot2 ISP Ready') == -1:
                                bflb_utils.printf("Boot2 isp is not ready")
                                return "FL"
                            else:
                                self.if_write(bytearray.fromhex("a0000000"))
                                return "OK"
                        else:
                            while True:
                                # clear boot2 log
                                ack = self.if_raw_read()
                                if len(ack) == 0:
                                    break
                            time.sleep(0.1)
                            while True:
                                # clear boot2 log
                                ack = self.if_raw_read()
                                if len(ack) == 0:
                                    break
                        self._ser.timeout = tmp_timeout
                        break

                self._shakehand_flag = True
                self._ser.timeout = timeout
                # set actual baudrate
                self.if_init(self._device, self._baudrate, self._chiptype, self._chipname)
                time.sleep(2.2)

            if self.check_bl_usb_serial(self._device) and boot_load:
                blusbserialwriteflag = True
            # cut of tx rx power and rst
            if cutoff_time != 0 and blusbserialwriteflag is not True:
                cutoff_revert = False
                if cutoff_time > 1000:
                    cutoff_revert = True
                    cutoff_time = cutoff_time - 1000
                # MP_TOOL_V3 generate rising pulse to make D trigger output low
                # reset low
                self._ser.setRTS(1)
                # RC delay is 100ms
                time.sleep(0.2)
                # reset high
                self._ser.setRTS(0)
                time.sleep(0.05)
                # do power off
                # reset low
                self._ser.setRTS(1)
                if cutoff_revert:
                    # dtr high, power off
                    self._ser.setDTR(0)
                else:
                    # dtr low, power off
                    self._ser.setDTR(1)
                bflb_utils.printf("tx rx and power off, press the machine!")
                bflb_utils.printf("cutoff time is ", cutoff_time / 1000.0)
                time.sleep(cutoff_time / 1000.0)
                if cutoff_revert:
                    # dtr low, power on
                    self._ser.setDTR(1)
                else:
                    # dtr high, power on
                    self._ser.setDTR(0)
                bflb_utils.printf("power on tx and rx ")
                time.sleep(0.1)
            if do_reset is True and blusbserialwriteflag is not True:
                # MP_TOOL_V3 reset high to make boot pin high
                self._ser.setRTS(0)
                time.sleep(0.2)
                if reset_revert:
                    # reset low for reset revert to make boot pin high when cpu rset
                    self._ser.setRTS(1)
                    time.sleep(0.001)
                reset_cnt = 2
                if reset_hold_time > 1000:
                    reset_cnt = int(reset_hold_time // 1000)
                    reset_hold_time = reset_hold_time % 1000
                while reset_cnt > 0:
                    if reset_revert:
                        # reset high
                        self._ser.setRTS(0)
                    else:
                        # reset low
                        self._ser.setRTS(1)
                    # Boot high
                    # self._ser.setDTR(0)
                    time.sleep(reset_hold_time / 1000.0)
                    if reset_revert:
                        # reset low
                        self._ser.setRTS(1)
                    else:
                        # reset high
                        self._ser.setRTS(0)
                    if shake_hand_delay > 0:
                        time.sleep(shake_hand_delay / 1000.0)
                    else:
                        time.sleep(5 / 1000.0)
                    # do reset agian to make sure boot pin is high
                    if reset_revert:
                        # reset high
                        self._ser.setRTS(0)
                    else:
                        # reset low
                        self._ser.setRTS(1)
                    # Boot high
                    # self._ser.setDTR(0)
                    time.sleep(reset_hold_time / 1000.0)
                    if reset_revert:
                        # reset low
                        self._ser.setRTS(1)
                    else:
                        # reset high
                        self._ser.setRTS(0)
                    if shake_hand_delay > 0:
                        time.sleep(shake_hand_delay / 1000.0)
                    else:
                        time.sleep(5 / 1000.0)
                    reset_cnt -= 1
                bflb_utils.printf("reset cnt: " + str(reset_cnt) + ", reset hold: " +
                                  str(reset_hold_time / 1000.0) + ", shake hand delay: " +
                                  str(shake_hand_delay / 1000.0))
            if blusbserialwriteflag:
                self.bl_usb_serial_write(cutoff_time, reset_revert)
            # clean buffer before start
            bflb_utils.printf("clean buf")
            self._ser.timeout = 0.1
            self._ser.read_all()
            self._ser.timeout = timeout
            return "OK"
        except Exception as e:
            bflb_utils.printf("Error: %s" % e)

    def if_close(self):
        if self._ser:
            try:
                self._ser.setDTR(1)
                self._ser.close()
                self._ser = None
            except Exception as e:
                bflb_utils.printf("Error: %s" % e)

    # this function return str type
    def if_deal_ack(self, dmy_data=True):
        try:
            success, ack = self.if_read(2)
            if success == 0:
                bflb_utils.printf("ack is ", str(binascii.hexlify(ack)))
                return ack.decode("utf-8")
            if ack.find(b'\x4F') != -1 or ack.find(b'\x4B') != -1:
                # if dmy_data:
                #    success, ack = self.if_read(14)
                #    if success == 0:
                #        return "FL"
                return "OK"
            elif ack.find(b'\x50') != -1 or ack.find(b'\x44') != -1:
                return "PD"
            success, err_code = self.if_read(2)
            if success == 0:
                bflb_utils.printf("err code is ", str(binascii.hexlify(err_code)))
                return "FL"
            err_code_str = str(binascii.hexlify(err_code[1:2] + err_code[0:1]).decode('utf-8'))
            ack = "FL"
            try:
                ret = ack + err_code_str + \
                    "(" + bflb_utils.get_bflb_error_code(err_code_str) + ")"
            except Exception:
                ret = ack + err_code_str + " unknown"
            bflb_utils.printf(ret)
            return ret
        except Exception as e:
            bflb_utils.printf("Error: %s" % e)

    # this function return bytearray or bytes type
    def if_deal_response(self):
        try:
            ack = self.if_deal_ack()
            if ack == "OK":
                success, len_bytes = self.if_read(2)
                if success == 0:
                    bflb_utils.printf("Get length error")
                    bflb_utils.printf("len error is ", binascii.hexlify(len_bytes))
                    return "Get length error", len_bytes
                tmp = bflb_utils.bytearray_reverse(len_bytes)
                data_len = bflb_utils.bytearray_to_int(tmp)
                success, data_bytes = self.if_read(data_len)
                if success == 0 or len(data_bytes) != data_len:
                    bflb_utils.printf("Read data error,maybe not get excepted length")
                    # bflb_utils.printf("ack is ", str(binascii.hexlify(data_bytes)))
                    return "Read data error,maybe not get excepted length", data_bytes
                # bflb_utils.printf("ack is ", str(binascii.hexlify(data_bytes)))
                return ack, data_bytes
            bflb_utils.printf("Not ack OK")
            bflb_utils.printf(ack)
            return ack, None
        except Exception as e:
            bflb_utils.printf("Error: %s" % e)


class CliInfUart(object):

    def __init__(self, recv_cb_objs=None, baudrate=115200):
        self._baudrate = baudrate
        self._ser = None
        # self._logfile = None
        self._rx_thread = None
        self._rx_thread_running = False
        self._tx_thread = None
        self._tx_thread = None
        self._tx_queue = None
        if recv_cb_objs is not None:
            self._recv_cb_objs = recv_cb_objs
        else:
            self._recv_cb_objs = []
        self._boot = 0
        self.uart = ""
        self.mode = "general"

    def add_observer(self, recv_cb_obj):
        if recv_cb_obj is not None:
            self._recv_cb_objs.append(recv_cb_obj)
            return True
        else:
            return False

    def set_baudrate(self, baudrate):
        self._baudrate = baudrate
        if self._ser:
            self._ser.baudrate = baudrate

    def is_open(self):
        if self._ser is None:
            return False
        else:
            if self._ser.isOpen():
                return True
            else:
                return False

    def open(self, dev_com, baudrate=None):
        try:
            if not dev_com:
                bflb_utils.printf("No Serial Port Found")
                return False
            if self._ser is None:
                try:
                    if " (" in dev_com:
                        dev = dev_com[:dev_com.find(" (")]
                    else:
                        dev = dev_com

                    for p, d, h in comports():
                        if dev == p:
                            if "VID:PID=42BF:B210" in h or "VID:PID=FFFF:FFFF" in h:
                                self.mode = "bouffalo"
                            else:
                                self.mode = "general"
                    bflb_utils.printf('serial type is ' + self.mode)

                    if baudrate:
                        self._baudrate = baudrate
                    self._ser = serial.Serial(dev,
                                              self._baudrate,
                                              timeout=5.0,
                                              xonxoff=False,
                                              rtscts=False,
                                              write_timeout=None,
                                              dsrdtr=False)

                    if self.mode == "bouffalo":
                        self._ser.write(b"BOUFFALOLAB5555DTR0")
                        time.sleep(0.01)
                        self._ser.write(b"BOUFFALOLAB5555RTS0")
                        time.sleep(0.01)
                        self._ser.write(b"BOUFFALOLAB5555RTS1")
                    else:
                        self._ser.setDTR(1)  # DTR拉低
                        self._ser.setRTS(1)
                        time.sleep(0.01)
                        self._ser.setRTS(0)
                        time.sleep(0.01)
                        #self._ser.setDTR(0) # DTR拉高

                    self._tx_queue = Queue()
                    self._rx_thread = threading.Thread(target=self._read)
                    self._rx_thread_running = True
                    self._rx_thread.setDaemon(True)
                    self._rx_thread.start()
                    self._tx_thread = threading.Thread(target=self._write)
                    self._tx_thread_running = True
                    self._tx_thread.setDaemon(True)
                    self._tx_thread.start()
                except serial.SerialException:
                    bflb_utils.printf("Open %s Fail" % (dev))
                    return False
                except TypeError:
                    if self._ser is not None:
                        self._ser.close()
                    return False
                else:
                    bflb_utils.printf("Open %s Success" % (dev))
                    return True
        except Exception as e:
            bflb_utils.printf("Error: %s" % e)

    def close(self):
        try:
            if self._ser is not None:
                port = self._ser.port
                self._ser.setDTR(1)
                self._ser.close()
                # self._logfile.close()
                self._ser = None
                # self._logfile = None
                self._rx_thread_running = False
                if self._rx_thread:
                    self._rx_thread.join()
                self._tx_thread_running = False
                if self._tx_thread:
                    self._tx_thread.join()
                self._tx_queue = None
                self._boot = 0
                bflb_utils.printf("Close %s Success" % (port))
        except Exception as e:
            bflb_utils.printf("Error: %s" % e)

    def write(self, data_send):
        try:
            # data_send type is bytes
            if self._ser is not None:
                # return self._ser.write(data_send)
                self._tx_queue.put(data_send)
            else:
                return 0
        except Exception as e:
            bflb_utils.printf("Error: %s" % e)

    def read(self):
        time.sleep(0.1)
        return self.msg

    def _write(self):
        try:
            while self._tx_thread_running:
                try:
                    data = self._tx_queue.get(timeout=1)
                except Empty:
                    pass
                else:
                    self._ser.write(data)
        except Exception as e:
            bflb_utils.printf("Error: %s" % e)

    def _check_boot_cond(self, data):

        def bl60x_is_active(data):
            if len(data) > 10:
                return True

        def bl60x_bootup_filter(data):
            if data.find('Compile Date Time') == 0:
                return True
            if data.find('rf init') == 0:
                return True
            return False

        if bl60x_bootup_filter(data) is True:
            return False

        # bl60x start up info
        if data.find('[RX] Statitics') == 0:
            self._boot = 1
            return True

        # app open first, but bl60x has active
        if self._boot == 0 and bl60x_is_active(data):
            self._boot = 1
            # TODO query version
            return True
        return False

    def _read(self):
        try:
            data = ''
            self.msg = ''
            while self._rx_thread_running:
                try:
                    byte_msg = self._ser.read(1)
                except serial.SerialException:
                    try:
                        self._ser.close()
                    except Exception:
                        pass
                    self._ser = None
                    self._rx_thread_running = False
                    self._tx_thread_running = False
                    self._tx_thread.join()
                    self._tx_queue = None
                except Exception:
                    pass
                else:
                    try:
                        str_msg = bytes.decode(byte_msg)
                    except Exception:
                        continue
                    if str(str_msg) == '\r':
                        if data != '':
                            self.msg = data
                            bflb_utils.printf(data)
                            # check on_boot
                            if self._check_boot_cond(data) is True:
                                if self._recv_cb_objs is not None and len(self._recv_cb_objs) != 0:
                                    for cb in self._recv_cb_objs:
                                        time.sleep(1)
                                        cb.on_boot(self.uart)

                            if self._recv_cb_objs is not None and len(self._recv_cb_objs) != 0:
                                for cb in self._recv_cb_objs:
                                    cb.obs_handle(data)
                            # self._logfile.wrtiteline(data)
                        data = ''
                    elif str(str_msg) != '\n':
                        # data += str_msg.strip()
                        data += str_msg
                    else:
                        if data != '':
                            bflb_utils.printf(data + '\n')
                            data = ''
        except Exception as e:
            bflb_utils.printf("Error: %s" % e)

    '''        
    def _read(self):
        try:
            data = ''
            self.msg = ''
            while self._rx_thread_running:
                try:
                    byte_msg = self._ser.readline()
                except serial.SerialException:
                    try:
                        self._ser.close()
                    except Exception:
                        pass
                    self._ser = None
                    self._rx_thread_running = False
                    self._tx_thread_running = False
                    self._tx_thread.join()
                    self._tx_queue = None
                except Exception:
                    pass
                else:
                    try:
                        str_msg = bytes.decode(byte_msg)
                    except Exception:
                        continue
                    else:
                        bflb_utils.printf(str_msg)
        except Exception as e:
            bflb_utils.printf("Error: %s" % e)
        '''

    def open_listen(self, dev_com, baudrate):
        try:
            if not dev_com:
                bflb_utils.printf("No Serial Port Found")
                return False

            if " (" in dev_com:
                dev = dev_com[:dev_com.find(" (")]
            else:
                dev = dev_com

            for p, d, h in comports():
                if dev == p:
                    if "VID:PID=42BF:B210" in h or "VID:PID=FFFF:FFFF" in h:
                        self.mode = "bouffalo"
                    else:
                        self.mode = "general"
            bflb_utils.printf('serial type is ' + self.mode)

            if self._ser is None:
                try:
                    if " (" in dev_com:
                        dev = dev_com[:dev_com.find(" (")]
                    else:
                        dev = dev_com
                    self._ser = serial.Serial(None,
                                              baudrate,
                                              timeout=5.0,
                                              xonxoff=False,
                                              rtscts=False,
                                              write_timeout=None,
                                              dsrdtr=False)
                    self._ser.port = dev
                    self._ser.dtr = False
                    self._ser.rts = False
                    self._ser.open()

                    if self.mode == "bouffalo":
                        self._ser.write(b"BOUFFALOLAB5555DTR0")
                        time.sleep(0.01)
                        self._ser.write(b"BOUFFALOLAB5555RTS0")
                        time.sleep(0.01)
                        self._ser.write(b"BOUFFALOLAB5555RTS1")
                    else:
                        self._ser.setDTR(1)
                        self._ser.setRTS(1)
                        time.sleep(0.01)
                        self._ser.setRTS(0)
                        time.sleep(0.01)
                        self._ser.setDTR(0)

                    self._rx_thread = threading.Thread(target=self._read_listen)
                    self._rx_thread_running = True
                    self._rx_thread.setDaemon(True)
                    self._rx_thread.start()

                except serial.SerialException:
                    bflb_utils.printf("Open %s Fail" % (dev_com))
                    self._ser = None
                    return False
                except TypeError:
                    if self._ser is not None:
                        self._ser.close()
                        self._ser = None
                    return False
                else:
                    bflb_utils.printf("Open %s Success" % (dev_com))
                    return True
        except Exception as e:
            bflb_utils.printf("Error: %s" % e)

    def close_listen(self):
        try:
            if self._ser is not None:
                port = self._ser.port
                self._ser.close()
                self._ser = None
                self._rx_thread_running = False
                self._rx_thread.join()
                bflb_utils.printf("Close %s Success" % port)
            return True
        except Exception as e:
            bflb_utils.printf("Error: %s" % e)
            return False

    def _read_listen(self):
        try:
            self._ser.timeout = 0.1
            while self._rx_thread_running:
                try:
                    byte_msg = self._ser.read(50000)
                except serial.SerialException:
                    try:
                        self._ser.close()
                    except Exception:
                        pass
                    self._ser = None
                    self._rx_thread_running = False
                except Exception:
                    pass
                else:
                    try:
                        if byte_msg:
                            new_mess = str(bytes.decode(byte_msg))
                            bflb_utils.printf(new_mess)
                            byte_msg = ''
                    except Exception:
                        byte_msg = byte_msg.replace(b'\x00', b' ')
                        bflb_utils.printf(byte_msg.decode("GB18030", 'replace'))
                        byte_msg = ''
        except Exception as e:
            bflb_utils.printf("Error: %s" % e)
