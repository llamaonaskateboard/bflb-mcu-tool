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
import time
import binascii
import subprocess
import threading
import telnetlib
import serial

try:
    import bflb_path
except ImportError:
    from libs import bflb_path
from libs import bflb_utils
from libs.bflb_utils import app_path

openocd_path = os.path.join(app_path, "utils/openocd", "openocd.exe")


class ThreadOpenocdServer(threading.Thread):

    def __init__(self, chiptype="bl602", device="rv_dbg_plus", serial=None):
        threading.Thread.__init__(self)
        self.timeToQuit = threading.Event()
        self.timeToQuit.clear()
        self._chiptype = chiptype
        self._device = device
        self._serial = serial
        bflb_utils.printf("SN is " + str(self._serial))

    def stop(self):
        self.timeToQuit.set()

    def run(self):
        cmd = ""
        if self._serial:
            cmd_ftdi_serial = " -c \"ftdi_serial \\\"" + self._serial + "\\\"\""
        else:
            cmd_ftdi_serial = ""
        if self._device == "rv_dbg_plus":
            if self._chiptype == "bl602":
                cmd = openocd_path + " -f " + \
                      app_path + "/utils/openocd/if_rv_dbg_plus.cfg " + cmd_ftdi_serial +\
                      " -f " + app_path + "/utils/openocd/tgt_602.cfg"
            else:
                cmd = openocd_path + " -f " + \
                      app_path + "/utils/openocd/if_rv_dbg_plus.cfg" + cmd_ftdi_serial +\
                      " -f " + app_path + "/utils/openocd/tgt_702.cfg"
        elif self._device == "ft2232hl":
            if self._chiptype == "bl602":
                cmd = openocd_path + " -f " + \
                      app_path + "/utils/openocd/if_bflb_dbg.cfg" + cmd_ftdi_serial +\
                      " -f " + app_path + "/utils/openocd/tgt_602.cfg"
            else:
                cmd = openocd_path + " -f " + \
                      app_path + "/utils/openocd/if_bflb_dbg.cfg" + cmd_ftdi_serial +\
                      " -f " + app_path + "/utils/openocd/tgt_702.cfg"
        else:
            cmd = openocd_path + " -f " + \
                  app_path + "/utils/openocd/openocd-usb-sipeed.cfg " + cmd_ftdi_serial
        bflb_utils.printf(cmd)
        p = subprocess.Popen(cmd,
                             shell=True,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        out, err = p.communicate()
        bflb_utils.printf(out)


class BflbOpenocdPort(object):

    def __init__(self):
        self._speed = 5000
        self._rx_timeout = 10000
        self._openocd_shake_hand_addr = "20000000"
        self._openocd_data_addr = "20000004"
        self._inited = False
        self._chiptype = "bl60x"
        self._chipname = "bl60x"
        self._openocd_run_addr = "22010000"
        self.tn = telnetlib.Telnet()

    def if_init(self, device, sn, rate, chiptype="bl60x", chipname="bl60x"):
        if self._inited is False:
            sub_module = __import__("libs." + chiptype, fromlist=[chiptype])
            self._openocd_shake_hand_addr = sub_module.openocd_load_cfg.openocd_shake_hand_addr
            self._openocd_data_addr = sub_module.openocd_load_cfg.openocd_data_addr
            # tif_set = sub_module.openocd_load_cfg.openocd_set_tif
            self._openocd_run_addr = sub_module.openocd_load_cfg.openocd_run_addr
            self._speed = rate
            self._inited = True
            self._chiptype = chiptype
            self._chipname = chipname
            if sn:
                serial = 'FactoryAIOT Prog ' + str(sn)
            else:
                serial = None
            self._openocd_th = None
            self._openocd_th = ThreadOpenocdServer(chiptype, device, serial)
            self._openocd_th.setDaemon(True)
            self._openocd_th.start()
            # time.sleep(0.1)
            try:
                self.tn.open("127.0.0.1", port=4444, timeout=10)
                # time.sleep(0.1)
                # self.tn.write("set architecture riscv:rv32\r\n".encode('ascii'))
                self.tn.write(("adapter speed " + str(rate)).encode('ascii') + b"\n")
                self.tn.write("WaitCmd\n".encode('ascii'))
                self.tn.read_until("\"WaitCmd\"".encode('ascii'), timeout=10)
            except Exception:
                bflb_utils.printf('Failed to connect openocd server')
                bflb_utils.set_error_code("0009")
                self.if_close()
            return False

    def if_clear_buf(self):
        pass

    def if_set_rx_timeout(self, val):
        self._rx_timeout = val * 1000

    def if_get_rate(self):
        return self._speed

    def halt_cpu(self):
        self.tn.write("halt".encode('ascii') + b"\n")
        return True

    def reset_cpu(self, ms=0, halt=True):
        if halt:
            self.halt_cpu()
        self.tn.write("reset".encode('ascii') + b"\n")

    def set_pc_msp(self, pc, msp):
        self.halt_cpu()
        if self._chiptype == "bl602" \
        or self._chiptype == "bl702" \
        or self._chiptype == "bl702l":
            self.tn.write(("reg pc 0x" + self._openocd_run_addr).encode('ascii') + b"\n")
            self.tn.write("resume".encode('ascii') + b"\n")

    def if_raw_write(self, addr, data_send):
        addr_int = int(addr, 16)
        if len(data_send) > 32:
            fp = open("openocd_load_data.bin", "wb+")
            fp.write(data_send)
            fp.close()
            self.tn.write(("load_image openocd_load_data.bin " + hex(addr_int)).encode('ascii') +
                          b"\n")
        else:
            for data in data_send:
                self.tn.write(("mwb " + hex(addr_int) + " " + hex(data)).encode('ascii') + b"\n")
                addr_int += 1

    def if_write(self, data_send):
        self.if_raw_write(self._openocd_data_addr, data_send)
        # write flag
        self.if_raw_write(self._openocd_shake_hand_addr, bytearray.fromhex("48524459"))

    def read_data_parse(self, buff, aligned):
        strdata = buff.decode().strip()
        data = bytearray(0)
        index = strdata.find(": ")
        if aligned is True:
            lstr = strdata[index + 2:strdata.find("WaitCmd") - 6].split("0x")
            for l in lstr:
                ldata = []
                if l.find(": ") != -1:
                    ldata = l[9:].split(" ")
                else:
                    ldata = l.split(" ")
                for d in ldata:
                    if len(d) != 8:
                        continue
                    hexstr = d[6:8] + d[4:6] + d[2:4] + d[0:2]
                    data += bflb_utils.hexstr_to_bytearray(hexstr)
        else:
            data += bflb_utils.hexstr_to_bytearray(strdata[index + 2:strdata.find("WaitCmd") -
                                                           6].replace(" ", ""))
        return data

    def if_addr_unaligned_read(self, addr, data_len):
        addr_int = int(addr, 16)
        data = bytearray(0)
        dummy = self.tn.read_very_eager().decode('utf-8')
        self.tn.write(("mdb " + hex(addr_int) + " " + hex(data_len) + "\n").encode('ascii'))
        # self.tn.write("reg pc\n".encode('ascii'))
        # ret = self.tn.read_until("pc (/32)".encode('ascii'), timeout=10)
        self.tn.write("WaitCmd\n".encode('ascii'))
        ret = self.tn.read_until("\"WaitCmd\"".encode('ascii'), timeout=10)
        # bflb_utils.printf(ret)
        data += self.read_data_parse(ret, False)
        # bflb_utils.printf(binascii.hexlify(data))
        return data

    def if_addr_aligned_read(self, addr, data_len):
        addr_int = int(addr, 16)
        leftlen = data_len
        data = bytearray(0)
        dummy = self.tn.read_very_eager().decode('utf-8')
        self.tn.write(("mdw " + hex(addr_int) + " " + hex(data_len // 4) + "\n").encode('ascii'))
        # self.tn.write("reg pc\r\n".encode('ascii'))
        # ret = self.tn.read_until("pc (/32)".encode('ascii'), timeout=10)
        self.tn.write("WaitCmd\n".encode('ascii'))
        ret = self.tn.read_until("\"WaitCmd\"".encode('ascii'), timeout=10)
        # bflb_utils.printf(ret)
        data += self.read_data_parse(ret, True)
        addr_int = addr_int + data_len // 4 * 4
        leftlen = data_len - data_len // 4 * 4
        if leftlen != 0:
            data += self.if_addr_unaligned_read(hex(addr_int)[2:], leftlen)
        # bflb_utils.printf(binascii.hexlify(data))
        return data

    def if_raw_read(self, addr, data_len):
        data = bytearray(0)
        if data_len <= 4:
            return self.if_addr_unaligned_read(addr, data_len)
        else:
            addr_int = int(addr, 16)
            pre_read_len = 4 - (addr_int % 4)
            if pre_read_len != 0:
                data += self.if_addr_unaligned_read(addr, pre_read_len)
            data += self.if_addr_aligned_read(hex(addr_int + pre_read_len),
                                              data_len - pre_read_len)
            return data[:data_len]

    def if_read(self, data_len):
        start_time = (time.time() * 1000)
        while True:
            ready = self.if_raw_read(self._openocd_shake_hand_addr, 16)
            # bflb_utils.printf("receiving",ready)
            if ready[0:4] == bytearray([0x53, 0x41, 0x43, 0x4B]):
                break
            elapsed = (time.time() * 1000) - start_time
            # time out judgment
            if elapsed >= self._rx_timeout:
                return 0, "waiting response time out".encode("utf-8")
            time.sleep(0.001)

        data = self.if_raw_read(self._openocd_data_addr, data_len)

        if len(data) != data_len:
            return 0, data
        return 1, data

    def if_clear_buff(self):
        self.tn.write("WaitCmd\n".encode('ascii'))
        self.tn.read_until("\"WaitCmd\"".encode('ascii'), timeout=10)

    def if_shakehand(self,
                     do_reset=False,
                     reset_hold_time=100,
                     shake_hand_delay=100,
                     reset_revert=True,
                     cutoff_time=0,
                     shake_hand_retry=2,
                     isp_timeout=0,
                     boot_load=False):
        self.if_clear_buff()
        self.if_write(bytearray(1))
        success, ack = self.if_read(2)
        bflb_utils.printf(binascii.hexlify(ack))
        if ack.find(b'\x4F') != -1 or ack.find(b'\x4B') != -1:
            time.sleep(0.03)
            return "OK"
        return "FL"

    def if_close(self):
        if self.tn.get_socket():
            self.tn.write("shutdown\n".encode('ascii'))
            time.sleep(0.05)
        self.tn.close()
        if self._openocd_th:
            self._openocd_th.stop()
            self._inited = False

    def if_deal_ack(self):
        success, ack = self.if_read(2)
        if success == 0:
            bflb_utils.printf("ack:" + str(binascii.hexlify(ack)))
            return ack.decode("utf-8")
        if ack.find(b'\x4F') != -1 or ack.find(b'\x4B') != -1:
            return "OK"
        elif ack.find(b'\x50') != -1 or ack.find(b'\x44') != -1:
            return "PD"
        success, err_code = self.if_read(4)
        if success == 0:
            bflb_utils.printf("err_code:" + str(binascii.hexlify(err_code)))
            return "FL"
        err_code_str = str(binascii.hexlify(err_code[3:4] + err_code[2:3]).decode('utf-8'))
        ack = "FL"
        try:
            ret = ack + err_code_str + "(" + bflb_utils.get_bflb_error_code(err_code_str) + ")"
        except Exception:
            ret = ack + err_code_str + " unknown"
        bflb_utils.printf(ret)
        return ret

    def if_deal_response(self):
        ack = self.if_deal_ack()
        if ack == "OK":
            success, len_bytes = self.if_read(4)
            if success == 0:
                bflb_utils.printf("Get length error")
                bflb_utils.printf(binascii.hexlify(len_bytes))
                return "Get length error", len_bytes
            # byte 2 and 3 is length
            tmp = bflb_utils.bytearray_reverse(len_bytes[2:4])
            data_len = bflb_utils.bytearray_to_int(tmp)
            success, data_bytes = self.if_read(data_len + 4)
            if success == 0:
                bflb_utils.printf("Read data error")
                return "Read data error", data_bytes
            # remove thr first 4 bytes
            data_bytes = data_bytes[4:]
            if len(data_bytes) != data_len:
                bflb_utils.printf("Not get excepted length")
                return "Not get excepted length", data_bytes
            return ack, data_bytes
        bflb_utils.printf("Not ack OK")
        bflb_utils.printf(ack)
        return ack, None


if __name__ == '__main__':
    eflash_loader_t = BflbOpenocdPort()
    eflash_loader_t.if_init("", 100, "bl60x")
    bflb_utils.printf("read test")
    bflb_utils.printf(eflash_loader_t.if_raw_read("21000000", 2))
    bflb_utils.printf(eflash_loader_t.if_raw_read("21000000", 4))
    bflb_utils.printf(eflash_loader_t.if_raw_read("21000000", 10))
    bflb_utils.printf(eflash_loader_t.if_raw_read("21000000", 16))
    bflb_utils.printf(eflash_loader_t.if_raw_read("21000001", 2))
    bflb_utils.printf(eflash_loader_t.if_raw_read("21000001", 4))
    bflb_utils.printf(eflash_loader_t.if_raw_read("21000001", 10))
    bflb_utils.printf(eflash_loader_t.if_raw_read("21000001", 16))
    bflb_utils.printf(eflash_loader_t.if_raw_read("21000002", 2))
    bflb_utils.printf(eflash_loader_t.if_raw_read("21000002", 4))
    bflb_utils.printf(eflash_loader_t.if_raw_read("21000002", 10))
    bflb_utils.printf(eflash_loader_t.if_raw_read("21000002", 16))
    bflb_utils.printf("write test")
    # data = bytearray([5, 6, 7, 8, 5, 6, 7, 8, 5, 6, 7, 8, 5, 6, 7, 8])
    data = bytearray([
        1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 3, 4, 1, 2,
        3, 4, 1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 3, 4
    ])
    eflash_loader_t.if_raw_write("42020000", data)
    bflb_utils.printf(eflash_loader_t.if_raw_read("42020000", 62))
