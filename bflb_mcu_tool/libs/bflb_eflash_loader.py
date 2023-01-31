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
import re
import time
import hashlib
import binascii
import subprocess
import traceback
import shutil
import lzma
import csv
import zipfile
from importlib import reload

import portalocker
import ecdsa
from Crypto.Cipher import AES

try:
    import bflb_path
except ImportError:
    from libs import bflb_path

import config as gol
from libs import bflb_version
from libs import bflb_interface_uart
from libs import bflb_interface_sdio
from libs import bflb_interface_jlink
from libs import bflb_interface_cklink
from libs import bflb_interface_openocd
from libs import bflb_efuse_boothd_create
from libs import bflb_img_loader
from libs import bflb_flash_select
from libs import bflb_utils
from libs import bflb_ecdh
from libs.bflb_utils import app_path, chip_path, open_file, eflash_loader_parser_init, convert_path
from libs.bflb_configobj import BFConfigParser

try:
    import changeconf as cgc
    conf_sign = True
except ImportError:
    conf_sign = False

try:
    from config import mutex
    th_sign = True
except ImportError:
    th_sign = False

try:
    from PySide2 import QtCore
    qt_sign = True
except ImportError:
    qt_sign = False

FLASH_LOAD_SHAKE_HAND = "Flash load shake hand"
FLASH_ERASE_SHAKE_HAND = "Flash erase shake hand"

try:
    from config import NUM_ERR
except ImportError:
    NUM_ERR = 5


class BflbEflashLoader(object):

    def __init__(self, chipname="bl60x", chiptype="bl60x"):
        self._bflb_auto_download = False
        # img loader class
        self._bflb_com_img_loader = None
        # communicate interface
        self._bflb_com_if = None
        # communicate device name
        self._bflb_com_device = ""
        # bootrom device speed
        self._bflb_boot_speed = 0
        # communicate device speed
        self._bflb_com_speed = 0
        # communicate device speed
        self._bflb_com_tx_size = 0
        # erase timeout
        self._erase_time_out = 10000
        # default rx timeout is 2s
        self._default_time_out = 2.0
        # shake hand
        self._need_shake_hand = True
        # retry limit when checksum error occurred
        self._checksum_err_retry_limit = 2
        self._csv_burn_en = False
        self._task_num = None
        self._cpu_reset = False
        self._retry_delay_after_cpu_reset = 0
        self._input_macaddr = ""
        self._macaddr_check = bytearray(0)
        self._decompress_write = False
        self._chip_type = chiptype
        self._chip_name = chipname
        self._mass_opt = False
        self._efuse_bootheader_file = ""
        self._img_create_file = ""
        self._csv_data = ""
        self._csv_file = ""
        self._skip_addr = 0
        self._skip_len = 0
        self._loader_checksum_err_str = "FL0103"
        self._bootinfo = None
        self._isp_shakehand_timeout = 0
        self._isp_en = False
        self._macaddr_check_status = False
        self._efuse_data = bytearray(0)
        self._efuse_mask_data = bytearray(0)
        self._ecdh_shared_key = None
        self._ecdh_public_key = None
        self._ecdh_private_key = None
        # flash2 cfg
        self._flash2_en = False
        self._flash1_size = 0
        self._flash2_size = 0
        self._flash2_select = False

        self._com_cmds = {
            "change_rate": {
                "cmd_id": "20",
                "data_len": "0008",
                "callback": None
            },
            "reset": {
                "cmd_id": "21",
                "data_len": "0000",
                "callback": None
            },
            "clk_set": {
                "cmd_id": "22",
                "data_len": "0000",
                "callback": None
            },
            "opt_finish": {
                "cmd_id": "23",
                "data_len": "0000",
                "callback": None
            },
            "flash_erase": {
                "cmd_id": "30",
                "data_len": "0000",
                "callback": None
            },
            "flash_write": {
                "cmd_id": "31",
                "data_len": "0100",
                "callback": None
            },
            "flash_read": {
                "cmd_id": "32",
                "data_len": "0100",
                "callback": None
            },
            "flash_boot": {
                "cmd_id": "33",
                "data_len": "0000",
                "callback": None
            },
            "flash_xip_read": {
                "cmd_id": "34",
                "data_len": "0100",
                "callback": None
            },
            "flash_switch_bank": {
                "cmd_id": "35",
                "data_len": "0100",
                "callback": None
            },
            "flash_read_jid": {
                "cmd_id": "36",
                "data_len": "0000",
                "callback": None
            },
            "flash_read_status_reg": {
                "cmd_id": "37",
                "data_len": "0000",
                "callback": None
            },
            "flash_write_status_reg": {
                "cmd_id": "38",
                "data_len": "0000",
                "callback": None
            },
            "flash_write_check": {
                "cmd_id": "3a",
                "data_len": "0000",
                "callback": None
            },
            "flash_set_para": {
                "cmd_id": "3b",
                "data_len": "0000",
                "callback": None
            },
            "flash_chiperase": {
                "cmd_id": "3c",
                "data_len": "0000",
                "callback": None
            },
            "flash_readSha": {
                "cmd_id": "3d",
                "data_len": "0100",
                "callback": None
            },
            "flash_xip_readSha": {
                "cmd_id": "3e",
                "data_len": "0100",
                "callback": None
            },
            "flash_decompress_write": {
                "cmd_id": "3f",
                "data_len": "0100",
                "callback": None
            },
            "efuse_write": {
                "cmd_id": "40",
                "data_len": "0080",
                "callback": None
            },
            "efuse_read": {
                "cmd_id": "41",
                "data_len": "0000",
                "callback": None
            },
            "efuse_read_mac": {
                "cmd_id": "42",
                "data_len": "0000",
                "callback": None
            },
            "efuse_write_mac": {
                "cmd_id": "43",
                "data_len": "0006",
                "callback": None
            },
            "flash_xip_read_start": {
                "cmd_id": "60",
                "data_len": "0080",
                "callback": None
            },
            "flash_xip_read_finish": {
                "cmd_id": "61",
                "data_len": "0000",
                "callback": None
            },
            "log_read": {
                "cmd_id": "71",
                "data_len": "0000",
                "callback": None
            },
            "efuse_security_write": {
                "cmd_id": "80",
                "data_len": "0080",
                "callback": None
            },
            "efuse_security_read": {
                "cmd_id": "81",
                "data_len": "0000",
                "callback": None
            },
            "ecdh_get_pk": {
                "cmd_id": "90",
                "data_len": "0000",
                "callback": None
            },
            "ecdh_chanllenge": {
                "cmd_id": "91",
                "data_len": "0000",
                "callback": None
            },
        }
        self._resp_cmds = [
            "flash_read", "flash_xip_read", "efuse_read", "efuse_read_mac", "flash_readSha",
            "flash_xip_readSha", "flash_read_jid", "flash_read_status_reg", "log_read",
            "ecdh_get_pk", "ecdh_chanllenge", "efuse_security_read"
        ]

    def object_status_clear(self):
        self._bootinfo = None
        self._macaddr_check = bytearray(0)
        self._macaddr_check_status = False

    def set_config_file(self, bootheaderFile, imgCreateFile):
        self._efuse_bootheader_file = bootheaderFile
        self._img_create_file = imgCreateFile

    def set_mass_opt_flag(self, flag):
        self._mass_opt = flag

    # command common process
    def com_process_one_cmd(self, section, cmd_id, data_send):
        data_read = bytearray(0)
        data_len = bflb_utils.int_to_2bytearray_l(len(data_send))
        checksum = 0
        checksum += bflb_utils.bytearray_to_int(data_len[0:1]) + bflb_utils.bytearray_to_int(
            data_len[1:2])
        for char in data_send:
            checksum += char
        data = cmd_id + bflb_utils.int_to_2bytearray_l(checksum & 0xff)[0:1] + data_len + data_send
        self._bflb_com_if.if_write(data)
        if section in self._resp_cmds:
            res, data_read = self._bflb_com_if.if_deal_response()
        else:
            res = self._bflb_com_if.if_deal_ack()
        return res, data_read

    # change interface rate
    def com_inf_change_rate(self, section, newrate):
        cmd_id = bflb_utils.hexstr_to_bytearray(self._com_cmds.get(section)["cmd_id"])
        cmd_len = bflb_utils.hexstr_to_bytearray(self._com_cmds.get(section)["data_len"])
        bflb_utils.printf("Process ", section, ", cmd=",
                          binascii.hexlify(cmd_id).decode('utf-8'), ",data len=",
                          binascii.hexlify(cmd_len).decode('utf-8'))
        baudrate = self._bflb_com_if.if_get_rate()
        oldv = bflb_utils.int_to_4bytearray_l(baudrate)
        newv = bflb_utils.int_to_4bytearray_l(newrate)
        tmp = bytearray(3)
        tmp[1] = cmd_len[1]
        tmp[2] = cmd_len[0]
        data = cmd_id + tmp + oldv + newv
        self._bflb_com_if.if_write(data)
        # wait for data send done
        stime = (11 * 10) / float(baudrate) * 2
        if stime < 0.003:
            stime = 0.003
        time.sleep(stime)
        self._bflb_com_speed = newrate
        self._bflb_com_if.if_init(self._bflb_com_device, self._bflb_com_speed, self._chip_type,
                                  self._chip_name)
        return self._bflb_com_if.if_deal_ack()

    # main process
    def load_helper_bin(self,
                        interface,
                        helper_file,
                        do_reset=False,
                        reset_hold_time=100,
                        shake_hand_delay=100,
                        reset_revert=True,
                        cutoff_time=0,
                        shake_hand_retry=2,
                        isp_timeout=0):
        bflb_utils.printf("========= load eflash_loader.bin =========")
        bootinfo = None
        if interface == "jlink":
            bflb_utils.printf("Load eflash_loader.bin via jlink")
            self._bflb_com_if.if_init(self._bflb_com_device, self._bflb_com_speed, self._chip_type,
                                      self._chip_name)
            self._bflb_com_if.reset_cpu()
            imge_fp = open_file(helper_file, 'rb')
            # eflash_loader.bin has 192 bytes bootheader and seg header
            fw_data = bytearray(imge_fp.read())[192:] + bytearray(0)
            imge_fp.close()
            sub_module = __import__("libs." + self._chip_type, fromlist=[self._chip_type])
            load_addr = sub_module.jlink_load_cfg.jlink_load_addr
            self._bflb_com_if.if_raw_write(load_addr, fw_data)
            pc = fw_data[4:8]
            pc = bytes([pc[3], pc[2], pc[1], pc[0]])
            # c.reverse()
            msp = fw_data[0:4]
            msp = bytes([msp[3], msp[2], msp[1], msp[0]])
            # msp.reverse()
            self._bflb_com_if.set_pc_msp(binascii.hexlify(pc),
                                         binascii.hexlify(msp).decode('utf-8'))
            time.sleep(0.01)
            self._bflb_com_if.if_close()
            return True, bootinfo, ""
        elif interface == "openocd":
            bflb_utils.printf("Load eflash_loader.bin via openocd")
            self._bflb_com_if.if_init(self._bflb_com_device, self._bflb_sn_device,
                                      self._bflb_com_speed, self._chip_type, self._chip_name)
            self._bflb_com_if.halt_cpu()
            imge_fp = open_file(helper_file, 'rb')
            # eflash_loader.bin has 192 bytes bootheader and seg header
            fw_data = bytearray(imge_fp.read())[192:] + bytearray(0)
            imge_fp.close()
            sub_module = __import__("libs." + self._chip_type, fromlist=[self._chip_type])
            load_addr = sub_module.openocd_load_cfg.openocd_load_addr
            self._bflb_com_if.if_raw_write(load_addr, fw_data)
            pc = fw_data[4:8]
            pc = bytes([pc[3], pc[2], pc[1], pc[0]])
            # c.reverse()
            msp = fw_data[0:4]
            msp = bytes([msp[3], msp[2], msp[1], msp[0]])
            # msp.reverse()
            self._bflb_com_if.set_pc_msp(binascii.hexlify(pc),
                                         binascii.hexlify(msp).decode('utf-8'))
            return True, bootinfo, ""
        elif interface == "cklink":
            bflb_utils.printf("Load eflash_loader.bin via cklink")
            self._bflb_com_if.if_init(self._bflb_com_device, self._bflb_sn_device,
                                      self._bflb_com_speed, self._chip_type, self._chip_name)
            #self._bflb_com_if.reset_cpu()
            self._bflb_com_if.halt_cpu()
            imge_fp = open_file(helper_file, 'rb')
            # eflash_loader.bin has 192 bytes bootheader and seg header
            fw_data = bytearray(imge_fp.read())[192:] + bytearray(0)
            imge_fp.close()
            sub_module = __import__("libs." + self._chip_type, fromlist=[self._chip_type])
            load_addr = sub_module.openocd_load_cfg.openocd_load_addr
            self._bflb_com_if.if_raw_write(load_addr, fw_data)
            pc = fw_data[4:8]
            pc = bytes([pc[3], pc[2], pc[1], pc[0]])
            # c.reverse()
            msp = fw_data[0:4]
            msp = bytes([msp[3], msp[2], msp[1], msp[0]])
            # msp.reverse()
            self._bflb_com_if.set_pc_msp(binascii.hexlify(pc),
                                         binascii.hexlify(msp).decode('utf-8'))
            self._bflb_com_if.resume_cpu()
            return True, bootinfo, ""
        elif interface == "uart" or interface == "sdio":
            ret = True
            bflb_utils.printf("Load eflash_loader.bin via %s" % interface)
            start_time = (time.time() * 1000)
            ret, bootinfo, res = self._bflb_com_img_loader.img_load_process(
                self._bflb_com_device, self._bflb_boot_speed, self._bflb_boot_speed, helper_file,
                "", None, do_reset, reset_hold_time, shake_hand_delay, reset_revert, cutoff_time,
                shake_hand_retry, isp_timeout, True, self._bootinfo)
            bflb_utils.printf("Load helper bin time cost(ms): ", (time.time() * 1000) - start_time)
            return ret, bootinfo, res

    def load_shake_hand(self,
                        interface,
                        do_reset=False,
                        reset_hold_time=100,
                        shake_hand_delay=100,
                        reset_revert=True,
                        cutoff_time=0,
                        shake_hand_retry=2,
                        isp_timeout=0):
        bflb_utils.printf("========= shakehand with bootrom =========")
        if interface == "jlink":
            bflb_utils.printf("shakehand via jlink")
            self._bflb_com_if.if_init(self._bflb_com_device, self._bflb_com_speed, self._chip_type,
                                      self._chip_name)
            return "OK", None
        elif interface == "openocd":
            bflb_utils.printf("shakehand via openocd")
            self._bflb_com_if.if_init(self._bflb_com_device, self._bflb_sn_device,
                                      self._bflb_com_speed, self._chip_type, self._chip_name)
            return "OK", None
        elif interface == "cklink":
            bflb_utils.printf("shakehand via cklink")
            self._bflb_com_if.if_init(self._bflb_com_device, self._bflb_sn_device,
                                      self._bflb_com_speed, self._chip_type, self._chip_name)
            return "OK", None
        elif interface == "uart":
            ret = True
            bflb_utils.printf("shakehand via uart")
            ret = self._bflb_com_img_loader.img_load_shake_hand(self._bflb_com_device,
                                                                self._bflb_boot_speed,
                                                                self._bflb_boot_speed, do_reset,
                                                                reset_hold_time, shake_hand_delay,
                                                                reset_revert, cutoff_time,
                                                                shake_hand_retry, isp_timeout)
            return ret, None

    def get_boot_info(self,
                      interface,
                      helper_file,
                      do_reset=False,
                      reset_hold_time=100,
                      shake_hand_delay=100,
                      reset_revert=True,
                      cutoff_time=0,
                      shake_hand_retry=2,
                      isp_timeout=0):
        bflb_utils.printf("========= get_boot_info =========")
        bootinfo = ""
        if interface == "uart":
            ret = True
            start_time = (time.time() * 1000)
            ret, bootinfo = self._bflb_com_img_loader.img_get_bootinfo(
                self._bflb_com_device, self._bflb_boot_speed, self._bflb_boot_speed, helper_file,
                "", None, do_reset, reset_hold_time, shake_hand_delay, reset_revert, cutoff_time,
                shake_hand_retry, isp_timeout)
            chipid = None
            if ret is True:
                bootinfo = bootinfo.decode("utf-8")
                if self._chip_type == "bl702" or self._chip_type == "bl702l":
                    chipid = bootinfo[32:34] + bootinfo[34:36] + bootinfo[36:38] + \
                        bootinfo[38:40] + bootinfo[40:42] + bootinfo[42:44] + bootinfo[44:46] + bootinfo[46:48]
                else:
                    chipid = bootinfo[34:36] + bootinfo[32:34] + bootinfo[30:32] + \
                        bootinfo[28:30] + bootinfo[26:28] + bootinfo[24:26]
                bflb_utils.printf("========= ChipID: ", chipid, " =========")
                bflb_utils.printf("Get bootinfo time cost(ms): ",
                                  (time.time() * 1000) - start_time)
            if qt_sign and th_sign and QtCore.QThread.currentThread().objectName():
                with mutex:
                    num = str(QtCore.QThread.currentThread().objectName())
                    gol.list_chipid[int(num) - 1] = chipid
                    if chipid is not None:
                        gol.list_chipid_check[int(num) - 1] = chipid
                    for i, j in gol.list_download_check_last:
                        if (chipid is not None) and (chipid == i) and (j is True):
                            return True, bootinfo, "repeat_burn"
                    if chipid is not None:
                        return True, bootinfo, "OK"
                    else:
                        return False, bootinfo, "chipid_is_none"
            return ret, bootinfo, "OK"
        else:
            bflb_utils.printf("interface not fit")
            return False, bootinfo, ""

    def error_code_print(self, code):
        bflb_utils.set_error_code(code, self._task_num)
        #         bflb_utils.printf("{\"ErrorCode\": \"" + code + "\",\"ErrorMsg\":\"" +
        #                           bflb_utils.eflash_loader_error_code[code] + "\"}")
        bflb_utils.printf("ErrorCode: " + code + ", ErrorMsg: " +
                          bflb_utils.eflash_loader_error_code[code])

    def img_load_shake_hand(self):
        isp_sh_time = 0
        if self._chip_type == "bl702" or self._chip_type == "bl702l":
            isp_sh_time = self._isp_shakehand_timeout
        #print(self._bflb_com_device, self._bflb_com_speed, self._chip_type)
        self._bflb_com_if.if_init(self._bflb_com_device, self._bflb_com_speed, self._chip_type,
                                  self._chip_name)
        if self._bflb_com_if.if_shakehand(do_reset=False,
                                          reset_hold_time=100,
                                          shake_hand_delay=100,
                                          reset_revert=True,
                                          cutoff_time=0,
                                          shake_hand_retry=2,
                                          isp_timeout=isp_sh_time,
                                          boot_load=False) != "OK":
            self.error_code_print("0001")
            return False
        self._need_shake_hand = False
        return True

    def operate_finish(self, shakehand=0):
        bflb_utils.printf("Boot from flash")
        # shake hand
        if shakehand != 0:
            bflb_utils.printf(FLASH_ERASE_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return False
        else:
            if self._bflb_com_if is not None:
                self._bflb_com_if.if_close()
            self._bflb_com_if.if_init(self._bflb_com_device, self._bflb_com_speed, self._chip_type,
                                      self._chip_name)
        # send command
        cmd_id = bflb_utils.hexstr_to_bytearray(self._com_cmds.get("opt_finish")["cmd_id"])
        ret, dmy = self.com_process_one_cmd("opt_finish", cmd_id, bytearray(0))
        if ret.startswith("OK"):
            return True
        else:
            self.error_code_print("000D")
            return False

    def boot_from_flash(self, shakehand=0):
        bflb_utils.printf("Boot from flash")
        # shake hand
        if shakehand != 0:
            bflb_utils.printf(FLASH_ERASE_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return False
        else:
            if self._bflb_com_if is not None:
                self._bflb_com_if.if_close()
            self._bflb_com_if.if_init(self._bflb_com_device, self._bflb_com_speed, self._chip_type,
                                      self._chip_name)
        # send command
        cmd_id = bflb_utils.hexstr_to_bytearray(self._com_cmds.get("flash_boot")["cmd_id"])
        ret, dmy = self.com_process_one_cmd("flash_boot", cmd_id, bytearray(0))
        if ret.startswith("OK"):
            return True
        else:
            self.error_code_print("003F")
            return False

    def clear_boot_status(self, shakehand=0):
        bflb_utils.printf("Clear boot status at hbn rsvd register")
        # shake hand
        if shakehand != 0:
            bflb_utils.printf(FLASH_ERASE_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return False

        # write memory, 0x2000F108=0x00000000
        data = bytearray(12)
        data[0] = 0x50
        data[1] = 0x00
        data[2] = 0x08
        data[3] = 0x00
        data[4] = 0x08
        data[5] = 0xF1
        data[6] = 0x00
        data[7] = 0x20
        data[8] = 0x00
        data[9] = 0x00
        data[10] = 0x00
        data[11] = 0x00
        self._bflb_com_if.if_write(data)
        self._bflb_com_if.if_deal_ack(dmy_data=False)
        return True

    def reset_cpu(self, shakehand=0):
        bflb_utils.printf("CPU Reset")
        # shake hand
        if shakehand != 0:
            bflb_utils.printf(FLASH_ERASE_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return False
        # send command
        cmd_id = bflb_utils.hexstr_to_bytearray(self._com_cmds.get("reset")["cmd_id"])
        ret, dmy = self.com_process_one_cmd("reset", cmd_id, bytearray(0))
        if ret.startswith("OK"):
            return True
        else:
            self.error_code_print("0004")
            return False

    def clock_pll_set(self, shakehand, irq_en, speed, clk_para):
        bflb_utils.printf("Clock PLL set")
        # shake hand
        if shakehand != 0:
            bflb_utils.printf("clock set shake hand")
            if self.img_load_shake_hand() is False:
                return False
        start_time = (time.time() * 1000)
        # send command
        cmd_id = bflb_utils.hexstr_to_bytearray(self._com_cmds.get("clk_set")["cmd_id"])
        irq_enable = bytearray(4)
        load_speed = bytearray(4)
        if irq_en:
            irq_enable = b'\x01\x00\x00\x00'
        load_speed = bflb_utils.int_to_4bytearray_l(int(speed))
        data_send = irq_enable + load_speed + clk_para
        if len(clk_para) > 0:
            bflb_utils.printf("clock para:")
            bflb_utils.printf(binascii.hexlify(clk_para).decode('utf-8'))
        try_cnt = 0
        while True:
            ret, dmy = self.com_process_one_cmd("clk_set", cmd_id, data_send)
            if ret.startswith("OK"):
                break
            if try_cnt < self._checksum_err_retry_limit:
                bflb_utils.printf("Retry")
                try_cnt += 1
            else:
                self.error_code_print("000C")
                return False
        bflb_utils.printf("Set clock time cost(ms): ", (time.time() * 1000) - start_time)
        self._bflb_com_if.if_init(self._bflb_com_device, speed, self._chip_type, self._chip_name)
        self._bflb_com_if.if_clear_buf()
        time.sleep(0.01)
        return True

    def close_port(self, shakehand=0):
        if self._bflb_com_if is not None:
            self._bflb_com_if.if_close()

    def efuse_compare(self, read_data, maskdata, write_data):
        i = 0
        for i in range(len(read_data)):
            compare_data = read_data[i] & maskdata[i]
            if (compare_data & write_data[i]) != write_data[i]:
                bflb_utils.printf("compare fail: ", i)
                bflb_utils.printf(read_data[i], write_data[i])
                return False
        return True

    def get_ecdh_shared_key(self, shakehand=0):
        bflb_utils.printf("========= get ecdh shared key =========")
        publickey_file = "utils/pem/publickey_uecc.pem"
        if shakehand != 0:
            bflb_utils.printf("Shake hand")
            ret = self.img_load_shake_hand()
            if ret is False:
                return
        tmp_ecdh = bflb_ecdh.BflbEcdh()
        self._ecdh_public_key = tmp_ecdh.create_public_key()
        self._ecdh_private_key = binascii.hexlify(
            tmp_ecdh.ecdh.private_key.to_string()).decode("utf-8")
        bflb_utils.printf("ecdh public key")
        bflb_utils.printf(self._ecdh_public_key)
        bflb_utils.printf("ecdh private key")
        bflb_utils.printf(self._ecdh_private_key)
        cmd_id = bflb_utils.hexstr_to_bytearray(self._com_cmds.get("ecdh_get_pk")["cmd_id"])
        data_send = bytearray.fromhex(self._ecdh_public_key)
        ret, data_read = self.com_process_one_cmd("ecdh_get_pk", cmd_id, data_send)
        if ret.startswith("OK") is True:
            self._ecdh_peer_public_key = binascii.hexlify(data_read).decode("utf-8")
            bflb_utils.printf("ecdh peer key")
            bflb_utils.printf(self._ecdh_peer_public_key)
            self._ecdh_shared_key = tmp_ecdh.create_shared_key(self._ecdh_peer_public_key[0:128])
            bflb_utils.printf("ecdh shared key")
            bflb_utils.printf(self._ecdh_shared_key)
            # challenge
            cmd_id = bflb_utils.hexstr_to_bytearray(
                self._com_cmds.get("ecdh_chanllenge")["cmd_id"])
            data_send = bytearray(0)
            ret, data_read = self.com_process_one_cmd("ecdh_chanllenge", cmd_id, data_send)
            if ret.startswith("OK") is True:
                bflb_utils.printf("challenge data")
                bflb_utils.printf(binascii.hexlify(data_read).decode("utf-8"))
                encrypted_data = data_read[0:32]
                signature = data_read[32:96]
                signature_r = data_read[32:64]
                signature_s = data_read[64:96]
                vk = ecdsa.VerifyingKey.from_pem(
                    open_file(r"utils\pem\room_root_publickey_ecc.pem").read())
                try:
                    ret = vk.verify(signature,
                                    self.ecdh_decrypt_data(encrypted_data),
                                    hashfunc=hashlib.sha256,
                                    sigdecode=ecdsa.util.sigdecode_string)
                except Exception as err:
                    bflb_utils.printf(err)
                if ret is True:
                    return True
                else:
                    bflb_utils.printf("Challenge verify fail")
                    return False
            else:
                bflb_utils.printf("Challenge ack fail")
                return False
        else:
            bflb_utils.printf("Get shared key fail")
            return False

    def ecdh_encrypt_data(self, data):
        cryptor = AES.new(bytearray.fromhex(self._ecdh_shared_key[0:32]), AES.MODE_CBC,
                          bytearray(16))
        ciphertext = cryptor.encrypt(data)
        return ciphertext

    def ecdh_decrypt_data(self, data):
        cryptor = AES.new(bytearray.fromhex(self._ecdh_shared_key[0:32]), AES.MODE_CBC,
                          bytearray(16))
        plaintext = cryptor.decrypt(data)
        return plaintext

    def efuse_read_mac_addr_process(self, shakehand=1, callback=None):
        readdata = bytearray(0)
        macLen = 6
        if self._chip_type == "bl702" or self._chip_type == "bl702l":
            macLen = 8
        # shake hand
        if shakehand != 0:
            bflb_utils.printf(FLASH_LOAD_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return False, None
        cmd_id = bflb_utils.hexstr_to_bytearray(self._com_cmds.get("efuse_read_mac")["cmd_id"])
        bflb_utils.printf("Read mac addr ")
        ret, data_read = self.com_process_one_cmd("efuse_read_mac", cmd_id, bytearray(0))
        if ret.startswith("OK") is False:
            self.error_code_print("0023")
            return False, None
        #bflb_utils.printf(binascii.hexlify(data_read))
        readdata += data_read
        crcarray = bflb_utils.get_crc32_bytearray(readdata[:macLen])
        if crcarray != readdata[macLen:macLen + 4]:
            bflb_utils.printf(binascii.hexlify(crcarray))
            bflb_utils.printf(binascii.hexlify(readdata[macLen:macLen + 4]))
            self.error_code_print("0025")
            return False, None
        return True, readdata[:macLen]

    def efuse_write_mac_addr_process(self, macaddr, shakehand=1, callback=None):
        # shake hand
        if shakehand != 0:
            bflb_utils.printf(FLASH_LOAD_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return False, None
        cmd_id = bflb_utils.hexstr_to_bytearray(self._com_cmds.get("efuse_write_mac")["cmd_id"])
        ret, data_read = self.com_process_one_cmd("efuse_write_mac", cmd_id, macaddr)
        bflb_utils.printf("Write mac addr ")
        if ret.startswith("OK") is False:
            self.error_code_print("0024")
            return False, None
        return True, None

    def efuse_read_main_process(self,
                                start_addr,
                                data_len,
                                shakehand=0,
                                file=None,
                                security_read=False):
        readdata = bytearray(0)
        # shake hand
        if shakehand != 0:
            bflb_utils.printf(FLASH_LOAD_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return False, None
        if security_read:
            cmd_name = "efuse_security_read"
        else:
            cmd_name = "efuse_read"
        cmd_id = bflb_utils.hexstr_to_bytearray(self._com_cmds.get(cmd_name)["cmd_id"])
        data_send = bflb_utils.int_to_4bytearray_l(start_addr) + bflb_utils.int_to_4bytearray_l(
            data_len)
        ret, data_read = self.com_process_one_cmd(cmd_name, cmd_id, data_send)
        bflb_utils.printf("Read efuse ")
        if ret.startswith("OK") is False:
            self.error_code_print("0020")
            return False, None
        readdata += data_read
        if security_read:
            readdata = self.ecdh_decrypt_data(readdata)
        bflb_utils.printf("Finished")
        if file is not None:
            fp = open_file(file, 'wb+')
            fp.write(readdata)
            fp.close()
        return True, readdata

    def efuse_load_main_process(self,
                                file,
                                maskfile,
                                efusedata,
                                efusedatamask,
                                verify=0,
                                security_write=False):
        if efusedata != bytearray(0):
            bflb_utils.printf("Load data")
            efuse_data = efusedata
            mask_data = efusedatamask
        elif file is not None:
            bflb_utils.printf("Load file: ", file)
            fp = open_file(file, 'rb')
            efuse_data = bytearray(fp.read()) + bytearray(0)
            fp.close()
            fp = open_file(maskfile, 'rb')
            mask_data = bytearray(fp.read()) + bytearray(0)
            fp.close()
            if len(efuse_data) > 4096:
                bflb_utils.printf("Decrypt efuse data")
                efuse_data = efuse_data[4096:]
                security_key, security_iv = bflb_utils.get_security_key()
                efuse_data = bflb_utils.aes_decrypt_data(efuse_data, \
                             security_key, security_iv, 0)
        else:
            efuse_data = self._efuse_data
            mask_data = self._efuse_mask_data
        if security_write and (self.get_ecdh_shared_key() is not True):
            return False
        bflb_utils.printf("Load efuse 0")
        # load normal data
        if security_write:
            cmd_name = "efuse_security_write"
        else:
            cmd_name = "efuse_write"
        cmd_id = bflb_utils.hexstr_to_bytearray(self._com_cmds.get(cmd_name)["cmd_id"])
        data_send = efuse_data[0:124] + bytearray(4)
        if security_write:
            data_send = self.ecdh_encrypt_data(data_send)
        data_send = bflb_utils.int_to_4bytearray_l(0) + data_send
        ret, dmy = self.com_process_one_cmd(cmd_name, cmd_id, data_send)
        if ret.startswith("OK") is False:
            bflb_utils.printf("Write Fail")
            self.error_code_print("0021")
            return False
        # verify
        if verify >= 1:
            ret, read_data = self.efuse_read_main_process(0,
                                                          128,
                                                          shakehand=0,
                                                          file=None,
                                                          security_read=security_write)
            if ret is True and self.efuse_compare(read_data, mask_data[0:124] + bytearray(4),
                                                  efuse_data[0:124] + bytearray(4)):
                bflb_utils.printf("Verify success")
            else:
                bflb_utils.printf("Read: ")
                bflb_utils.printf(binascii.hexlify(read_data[0:124]).decode('utf-8'))
                bflb_utils.printf("Expected: ")
                bflb_utils.printf(binascii.hexlify(efuse_data[0:124]).decode('utf-8'))
                bflb_utils.printf("Verify fail")
                self.error_code_print("0022")
                return False
        # load read write protect data
        data_send = bytearray(12) + efuse_data[124:128]
        if security_write:
            data_send = self.ecdh_encrypt_data(data_send)
        data_send = bflb_utils.int_to_4bytearray_l(124 - 12) + data_send
        ret, dmy = self.com_process_one_cmd(cmd_name, cmd_id, data_send)
        if ret.startswith("OK") is False:
            bflb_utils.printf("Write Fail")
            self.error_code_print("0021")
            return False
        # verify
        if verify >= 1:
            ret, read_data = self.efuse_read_main_process(124 - 12,
                                                          16,
                                                          shakehand=0,
                                                          file=None,
                                                          security_read=security_write)
            if ret is True and self.efuse_compare(read_data,
                                                  bytearray(12) + mask_data[124:128],
                                                  bytearray(12) + efuse_data[124:128]):
                bflb_utils.printf("Verify success")
            else:
                bflb_utils.printf("Read: ")
                bflb_utils.printf(binascii.hexlify(read_data[12:16]))
                bflb_utils.printf("Expected: ")
                bflb_utils.printf(binascii.hexlify(efuse_data[124:128]))
                bflb_utils.printf("Verify fail")
                self.error_code_print("0022")
                return False
        if len(efuse_data) > 128:
            bflb_utils.printf("Load efuse 1")
            # load normal data
            if security_write:
                cmd_name = "efuse_security_write"
            else:
                cmd_name = "efuse_write"
            cmd_id = bflb_utils.hexstr_to_bytearray(self._com_cmds.get(cmd_name)["cmd_id"])
            data_send = efuse_data[128:252] + bytearray(4)
            if security_write:
                data_send = self.ecdh_encrypt_data(data_send)
            data_send = bflb_utils.int_to_4bytearray_l(128) + data_send
            ret, dmy = self.com_process_one_cmd(cmd_name, cmd_id, data_send)
            if ret.startswith("OK") is False:
                bflb_utils.printf("Write Fail")
                self.error_code_print("0021")
                return False
            # verify
            if verify >= 1:
                ret, read_data = self.efuse_read_main_process(128,
                                                              128,
                                                              shakehand=0,
                                                              file=None,
                                                              security_read=security_write)
                if ret is True and self.efuse_compare(read_data, mask_data[128:252] + bytearray(4),
                                                      efuse_data[128:252] + bytearray(4)):
                    bflb_utils.printf("Verify success")
                else:
                    bflb_utils.printf("Verify fail")
                    self.error_code_print("0022")
                    return False
            # load read write protect data
            data_send = bytearray(12) + efuse_data[252:256]
            if security_write:
                data_send = self.ecdh_encrypt_data(data_send)
            data_send = bflb_utils.int_to_4bytearray_l(252 - 12) + data_send
            ret, dmy = self.com_process_one_cmd(cmd_name, cmd_id, data_send)
            if ret.startswith("OK") is False:
                bflb_utils.printf("Write Fail")
                self.error_code_print("0021")
                return False
            # verify
            if verify >= 1:
                ret, read_data = self.efuse_read_main_process(252 - 12,
                                                              16,
                                                              shakehand=0,
                                                              file=None,
                                                              security_read=security_write)
                if ret is True and self.efuse_compare(read_data,
                                                      bytearray(12) + mask_data[252:256],
                                                      bytearray(12) + efuse_data[252:256]):
                    bflb_utils.printf("Verify success")
                else:
                    bflb_utils.printf("Verify fail")
                    self.error_code_print("0022")
        bflb_utils.printf("Finished")
        return True

    def efuse_load_specified(self,
                             file,
                             maskfile,
                             efusedata,
                             efusedatamask,
                             verify=0,
                             shakehand=0,
                             security_write=False):
        bflb_utils.printf("========= efuse load =========")
        if shakehand != 0:
            bflb_utils.printf("Efuse load shake hand")
            ret = self.img_load_shake_hand()
            if ret is False:
                return False
        ret = self.efuse_load_main_process(file, maskfile, efusedata, efusedatamask, verify,
                                           security_write)
        return ret

    def efuse_load_macaddr(self, macaddr, verify=0, shakehand=0, security_write=False):
        bflb_utils.printf("========= efuse macaddr load =========")
        cnt = 0
        mac = macaddr[:12]

        if security_write and (self.get_ecdh_shared_key() is not True):
            return False

        for i in range(0, 12):
            temp = int(mac[i:i + 1], 16)
            for j in range(0, 4):
                if temp & (1 << j) == 0:
                    cnt += 1
        bflb_utils.printf("mac check cnt: 0x%02X" % (cnt))
        data_efuse = mac[10:12] + mac[8:10] + mac[6:8] + mac[4:6] + mac[2:4] + mac[
            0:2] + "%02X" % (cnt)
        efusedatastr = data_efuse
        efusemaskdata = bytearray(128)
        zeromac = bytearray(6)
        ret, efusedata = self.efuse_read_main_process(0,
                                                      128,
                                                      shakehand,
                                                      file=None,
                                                      security_read=security_write)
        if ret is False:
            return False
        efusedata = bytearray(efusedata)
        sub_module = __import__("libs." + self._chip_type, fromlist=[self._chip_type])
        slot0_addr = sub_module.efuse_cfg_keys.efuse_mac_slot_offset["slot0"]
        slot1_addr = sub_module.efuse_cfg_keys.efuse_mac_slot_offset["slot1"]
        slot2_addr = sub_module.efuse_cfg_keys.efuse_mac_slot_offset["slot2"]
        if efusedata[int(slot0_addr, 10):int(slot0_addr, 10) + 6] == zeromac:
            bflb_utils.printf("Efuse load mac slot 0")
            efuseaddrstr = slot0_addr
        elif efusedata[int(slot1_addr, 10):int(slot1_addr, 10) + 6] == zeromac:
            bflb_utils.printf("Efuse load mac slot 1")
            efuseaddrstr = slot1_addr
        elif efusedata[int(slot2_addr, 10):int(slot2_addr, 10) + 6] == zeromac:
            bflb_utils.printf("Efuse load mac slot 2")
            efuseaddrstr = slot2_addr
        else:
            bflb_utils.printf("Efuse mac slot 0/1/2 all not empty")
            return False
        for num in range(int(efuseaddrstr), int(efuseaddrstr) + int((len(efusedatastr) / 2))):
            efusedata[num] |= bytearray.fromhex(efusedatastr)[num - int(efuseaddrstr)]
            efusemaskdata[num] |= 0xff
        for num in range(0, 128):
            if efusedata[num] != 0:
                efusemaskdata[num] |= 0xff
        ret = self.efuse_load_specified(None, None, efusedata, efusemaskdata, verify, 0,
                                        security_write)
        if ret is False:
            return False
        return ret

    def efuse_load_702_macaddr(self, macaddr, verify=0, shakehand=0, security_write=False):
        bflb_utils.printf("========= efuse 702 macaddr load =========")
        cnt = 0
        mac = macaddr[:16]

        if security_write and (self.get_ecdh_shared_key() is not True):
            return False

        for i in range(0, 16):
            temp = int(mac[i:i + 1], 16)
            for j in range(0, 4):
                if temp & (1 << j) == 0:
                    cnt += 1
        bflb_utils.printf("mac check cnt: 0x%02X" % (cnt))
        # data_efuse = mac[10:12] + mac[8:10] + mac[6:8] + mac[4:6] + mac[2:4] + mac[0:2]
        efusedatastr = mac
        efusemaskdata = bytearray(128)
        zeromac = bytearray(8)
        ret, efusedata = self.efuse_read_main_process(0,
                                                      128,
                                                      shakehand,
                                                      file=None,
                                                      security_read=security_write)
        if ret is False:
            return False
        efusedata = bytearray(efusedata)
        sub_module = __import__("libs." + self._chip_type, fromlist=[self._chip_type])
        slot0_addr = sub_module.efuse_cfg_keys.efuse_mac_slot_offset["slot0"]
        slot1_addr = sub_module.efuse_cfg_keys.efuse_mac_slot_offset["slot1"]
        slot2_addr = sub_module.efuse_cfg_keys.efuse_mac_slot_offset["slot2"]
        if efusedata[int(slot0_addr, 10):int(slot0_addr, 10) + 8] == zeromac:
            bflb_utils.printf("Efuse load mac slot 0")
            efuseaddrstr = slot0_addr
            data_cnt = (cnt)
        elif efusedata[int(slot1_addr, 10):int(slot1_addr, 10) + 8] == zeromac:
            bflb_utils.printf("Efuse load mac slot 1")
            efuseaddrstr = slot1_addr
            data_cnt = (cnt << 6)
        elif efusedata[int(slot2_addr, 10):int(slot2_addr, 10) + 8] == zeromac:
            bflb_utils.printf("Efuse load mac slot 2")
            efuseaddrstr = slot2_addr
            data_cnt = (cnt << 12)
        else:
            bflb_utils.printf("Efuse mac slot 0/1/2 all not empty")
            return False
        efusedata[116:120] = bflb_utils.int_to_4bytearray_l(data_cnt)
        for num in range(int(efuseaddrstr), int(efuseaddrstr) + int((len(efusedatastr) / 2))):
            efusedata[num] |= bytearray.fromhex(efusedatastr)[num - int(efuseaddrstr)]
            efusemaskdata[num] |= 0xff
        for num in range(0, 128):
            if efusedata[num] != 0:
                efusemaskdata[num] |= 0xff

        # bflb_utils.printf(binascii.hexlify(efusedata))
        # bflb_utils.printf(binascii.hexlify(efusemaskdata))
        ret = self.efuse_load_specified(None, None, efusedata, efusemaskdata, verify, 0,
                                        security_write)
        if ret is False:
            return False
        return ret

    def efuse_load_aes_key(self, type, value, verify=0, shakehand=0, security_write=False):
        # value is like ["000102030405060708090A0B0C0D0E0F","110102030405060708090A0B0C0D0E0F"] or ["000102030405060708090A0B0C0D0E0F"]
        bflb_utils.printf("========= efuse key load =========")
        sub_module = __import__("libs." + self._chip_type, fromlist=[self._chip_type])
        efusedata, efusemaskdata = sub_module.efuse_data_create.efuse_data_create(type, value)
        if shakehand != 0:
            bflb_utils.printf("Efuse load shake hand")
            ret = self.img_load_shake_hand()
            if ret is False:
                return False
        ret = self.efuse_load_main_process(None, None, efusedata, efusemaskdata, verify,
                                           security_write)
        return ret

    def efuse_load_data_process(self,
                                data,
                                addr,
                                func=0,
                                verify=0,
                                shakehand=0,
                                security_write=False):
        bflb_utils.printf("========= efuse data load =========")
        # shake hand
        if shakehand is not False:
            bflb_utils.printf(FLASH_LOAD_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return False, None

        if security_write and (self.get_ecdh_shared_key() is not True):
            return False

        bflb_utils.printf("Load efuse data")
        try:
            # load normal data
            if security_write:
                cmd_name = "efuse_security_write"
            else:
                cmd_name = "efuse_write"
            cmd_id = bflb_utils.hexstr_to_bytearray(self._com_cmds.get(cmd_name)["cmd_id"])
            start_addr = int(addr) - int(addr) % 16
            efuse_data = bytearray(int(addr) % 16) + bytearray.fromhex(data) + \
                         bytearray(16 - (int(addr) + int(len(data) / 2)) % 16)
            bflb_utils.printf("efuse_data: ", start_addr)
            bflb_utils.printf(binascii.hexlify(efuse_data))
            mask_data = bytearray(len(efuse_data))

            if func > 0:
                bflb_utils.printf("Read and check efuse data")
                ret, read_data = self.efuse_read_main_process(start_addr,
                                                              len(efuse_data),
                                                              0,
                                                              file=None,
                                                              security_read=security_write)
                i = int(addr) - start_addr
                for i in range(
                        int(addr) - start_addr,
                        int(addr) - start_addr + int(len(data) / 2)):
                    compare_data = read_data[i] & efuse_data[i]
                    if compare_data != read_data[i]:
                        bflb_utils.printf("The efuse data to be written can't overwrite the efuse area at ",\
                                           i + start_addr)
                        bflb_utils.printf(read_data[i])
                        bflb_utils.printf(efuse_data[i])
                        return False

            if security_write:
                efuse_data = self.ecdh_encrypt_data(efuse_data)
            data_send = bflb_utils.int_to_4bytearray_l(start_addr) + efuse_data
            ret, dmy = self.com_process_one_cmd(cmd_name, cmd_id, data_send)
            if ret.startswith("OK") is False:
                bflb_utils.printf("Write Fail")
                self.error_code_print("0021")
                return False
            # verify
            for num in range(0, len(efuse_data)):
                if efuse_data[num] != 0:
                    mask_data[num] |= 0xff
        except Exception as e:
            bflb_utils.printf(e)
            return False
        if verify >= 1:
            ret, read_data = self.efuse_read_main_process(start_addr,
                                                          len(efuse_data),
                                                          0,
                                                          file=None,
                                                          security_read=security_write)
            if ret is True and self.efuse_compare(read_data, mask_data, efuse_data):
                bflb_utils.printf("Verify success")
            else:
                bflb_utils.printf("Read: ")
                bflb_utils.printf(binascii.hexlify(read_data))
                bflb_utils.printf("Expected: ")
                bflb_utils.printf(binascii.hexlify(efuse_data))
                bflb_utils.printf("Verify fail")
                bflb_utils.printf(binascii.hexlify(mask_data))
                self.error_code_print("0022")
                return False

    def flash_read_jedec_id_process(self, callback=None):
        bflb_utils.printf("========= flash read jedec ID =========")
        readdata = bytearray(0)
        # shake hand
        if self._need_shake_hand is not False:
            bflb_utils.printf(FLASH_LOAD_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return False, None
        cmd_id = bflb_utils.hexstr_to_bytearray(self._com_cmds.get("flash_read_jid")["cmd_id"])
        ret, data_read = self.com_process_one_cmd("flash_read_jid", cmd_id, bytearray(0))
        bflb_utils.printf("Read flash jedec ID ")
        if ret.startswith("OK") is False:
            self.error_code_print("0030")
            return False, None
        readdata += data_read
        bflb_utils.printf("readdata: ")
        bflb_utils.printf(binascii.hexlify(readdata))
        bflb_utils.printf("Finished")
        return True, readdata[:4]

    def flash_read_status_reg_process(self, cmd, len, callback=None):
        bflb_utils.printf("========= flash read status register =========")
        readdata = bytearray(0)
        # shake hand
        if self._need_shake_hand is not False:
            bflb_utils.printf(FLASH_LOAD_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return False, None

        cmd_id = bflb_utils.hexstr_to_bytearray(
            self._com_cmds.get("flash_read_status_reg")["cmd_id"])
        data_send = bflb_utils.int_to_4bytearray_l(int(cmd,
                                                       16)) + bflb_utils.int_to_4bytearray_l(len)
        ret, data_read = self.com_process_one_cmd("flash_read_status_reg", cmd_id, data_send)
        bflb_utils.printf("Read flash status register ")
        if ret.startswith("OK") is False:
            self.error_code_print("0031")
            return False, None
        readdata += data_read
        bflb_utils.printf("readdata: ")
        bflb_utils.printf(binascii.hexlify(readdata))
        bflb_utils.printf("Finished")
        return True, readdata

    def flash_write_status_reg_process(self, cmd, len, write_data, callback=None):
        bflb_utils.printf("========= flash write status register =========")
        # shake hand
        if self._need_shake_hand is not False:
            bflb_utils.printf(FLASH_LOAD_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return False, "Flash load shake hand fail"

        bflb_utils.printf("write_data ", write_data)
        cmd_id = bflb_utils.hexstr_to_bytearray(
            self._com_cmds.get("flash_write_status_reg")["cmd_id"])
        data_send = bflb_utils.int_to_4bytearray_l(int(
            cmd, 16)) + bflb_utils.int_to_4bytearray_l(len) + bflb_utils.int_to_4bytearray_l(
                int(write_data, 16))
        ret, data_read = self.com_process_one_cmd("flash_write_status_reg", cmd_id, data_send)
        bflb_utils.printf("Write flash status register ")
        if ret.startswith("OK") is False:
            self.error_code_print("0032")
            return False, "Write fail"
        bflb_utils.printf("Finished")
        return True, None

    def flash_erase_main_process(self, start_addr, end_addr, shakehand=0):
        bflb_utils.printf("========= flash erase =========")
        bflb_utils.printf("Erase flash from ", hex(start_addr), " to ", hex(end_addr))
        # shake hand
        if shakehand != 0:
            bflb_utils.printf(FLASH_ERASE_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                bflb_utils.printf("Shake hand fail")
                return False
        start_time = (time.time() * 1000)
        # send command
        if self._chip_type == "bl602" \
        or self._chip_type == "bl702" \
        or self._chip_type == "bl702l":
            self._bflb_com_if.if_set_rx_timeout(self._default_time_out)
        else:
            self._bflb_com_if.if_set_rx_timeout(self._erase_time_out / 1000)
        cmd_id = bflb_utils.hexstr_to_bytearray(self._com_cmds.get("flash_erase")["cmd_id"])
        data_send = bflb_utils.int_to_4bytearray_l(start_addr) + \
                    bflb_utils.int_to_4bytearray_l(end_addr)
        try_cnt = 0
        while True:
            ret, dmy = self.com_process_one_cmd("flash_erase", cmd_id, data_send)
            if ret.startswith("OK"):
                break
            elif ret.startswith("PD"):
                bflb_utils.printf("erase pending")
                while True:
                    ret = self._bflb_com_if.if_deal_ack()
                    if ret.startswith("PD"):
                        bflb_utils.printf("erase pending")
                    else:
                        # clear uart fifo 'PD' data
                        self._bflb_com_if.if_set_rx_timeout(0.02)
                        self._bflb_com_if.if_read(1000)
                        break
                    if (time.time() * 1000) - start_time > self._erase_time_out:
                        bflb_utils.printf("erase timeout")
                        break
            if ret.startswith("OK"):
                break

            if try_cnt < self._checksum_err_retry_limit:
                bflb_utils.printf("Retry")
                try_cnt += 1
            else:
                bflb_utils.printf("Erase Fail")
                self._bflb_com_if.if_set_rx_timeout(self._default_time_out)
                self.error_code_print("0034")
                return False

        bflb_utils.printf("Erase time cost(ms): ", (time.time() * 1000) - start_time)
        self._bflb_com_if.if_set_rx_timeout(self._default_time_out)
        return True

    def flash_chiperase_main_process(self, shakehand=0):
        bflb_utils.printf("Flash Chip Erase All")
        # shake hand
        if shakehand != 0:
            bflb_utils.printf(FLASH_ERASE_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                bflb_utils.printf("Shake hand fail")
                return False
        start_time = (time.time() * 1000)
        # send command
        if self._chip_type == "bl602" \
        or self._chip_type == "bl702" \
        or self._chip_type == "bl702l":
            self._bflb_com_if.if_set_rx_timeout(self._default_time_out)
        else:
            self._bflb_com_if.if_set_rx_timeout(self._erase_time_out / 1000)
        cmd_id = bflb_utils.hexstr_to_bytearray(self._com_cmds.get("flash_chiperase")["cmd_id"])
        try_cnt = 0
        while True:
            ret, dmy = self.com_process_one_cmd("flash_chiperase", cmd_id, bytearray(0))
            if ret.startswith("OK"):
                break
            elif ret.startswith("PD"):
                bflb_utils.printf("erase pending")
                while True:
                    ret = self._bflb_com_if.if_deal_ack()
                    if ret.startswith("PD"):
                        bflb_utils.printf("erase pending")
                    else:
                        # clear uart fifo 'PD' data
                        self._bflb_com_if.if_set_rx_timeout(0.02)
                        self._bflb_com_if.if_read(1000)
                        break
                    if (time.time() * 1000) - start_time > self._erase_time_out:
                        bflb_utils.printf("erase timeout")
                        break
            if ret.startswith("OK"):
                break

            if try_cnt < self._checksum_err_retry_limit:
                bflb_utils.printf("Retry")
                try_cnt += 1
            else:
                bflb_utils.printf("Erase Fail")
                self._bflb_com_if.if_set_rx_timeout(self._default_time_out)
                self.error_code_print("0033")
                return False
        bflb_utils.printf("Chip erase time cost(ms): ", (time.time() * 1000) - start_time)
        self._bflb_com_if.if_set_rx_timeout(self._default_time_out)
        return True

    def flash_loader_cut_flash_bin(self, file, addr, flash1_size):
        flash1_bin = "flash1.bin"
        flash2_bin = "flash2.bin"

        fp = open_file(file, 'rb')
        flash_data = bytearray(fp.read())
        fp.close()
        flash_data_len = len(flash_data)
        if flash1_size < addr + flash_data_len and flash1_size > addr:
            flash1_data = flash_data[0:flash1_size - addr]
            flash2_data = flash_data[flash1_size - addr:flash_data_len]
            fp = open_file(flash1_bin, 'wb+')
            fp.write(flash1_data)
            fp.close()
            fp = open_file(flash2_bin, 'wb+')
            fp.write(flash2_data)
            fp.close()
            return flash1_bin, len(flash1_data), flash2_bin, len(flash2_data)
        return "", 0, "", 0

    def flash_switch_bank_process(self, bank, shakehand=0):
        bflb_utils.printf("Flash Switch Bank")
        # shake hand
        if shakehand != 0:
            bflb_utils.printf("Flash switch bank shake hand")
            if self.img_load_shake_hand() is False:
                bflb_utils.printf("Shake hand fail")
                return False
        start_time = (time.time() * 1000)
        # send command
        self._bflb_com_if.if_set_rx_timeout(self._erase_time_out / 1000)
        cmd_id = bflb_utils.hexstr_to_bytearray(self._com_cmds.get("flash_switch_bank")["cmd_id"])
        data_send = bflb_utils.int_to_4bytearray_l(bank)
        ret, dmy = self.com_process_one_cmd("flash_switch_bank", cmd_id, data_send)
        if ret.startswith("OK") is False:
            bflb_utils.printf("Switch Fail")
            self._bflb_com_if.if_set_rx_timeout(self._default_time_out)
            self.error_code_print("0042")
            return False
        bflb_utils.printf("Switch bank time cost(ms): ", (time.time() * 1000) - start_time)
        self._bflb_com_if.if_set_rx_timeout(self._default_time_out)
        if bank == 0:
            self._flash2_select = False
        else:
            self._flash2_select = True
        return True

    def flash_set_para_main_process(self, flash_pin, flash_para, shakehand=0):
        bflb_utils.printf("Set flash config ")
        if flash_para != bytearray(0):
            if flash_para[13:14] == b'\xff':
                bflb_utils.printf("Skip set flash para due to flash id is 0xFF")
                # manufacturer id is 0xff, do not need set flash para
                return True
        # shake hand
        if shakehand != 0:
            bflb_utils.printf("Flash set para shake hand")
            if self.img_load_shake_hand() is False:
                return False
        start_time = (time.time() * 1000)
        # send command
        cmd_id = bflb_utils.hexstr_to_bytearray(self._com_cmds.get("flash_set_para")["cmd_id"])
        data_send = bflb_utils.int_to_4bytearray_l(flash_pin) + flash_para
        try_cnt = 0
        while True:
            ret, dmy = self.com_process_one_cmd("flash_set_para", cmd_id, data_send)
            if ret.startswith("OK"):
                break
            if try_cnt < self._checksum_err_retry_limit:
                bflb_utils.printf("Retry")
                try_cnt += 1
            else:
                self.error_code_print("003B")
                return False
        bflb_utils.printf("Set para time cost(ms): ", (time.time() * 1000) - start_time)
        return True

    def flash_read_main_process(self,
                                start_addr,
                                flash_data_len,
                                shakehand=0,
                                file=None,
                                callback=None):
        bflb_utils.printf("========= flash read =========")
        i = 0
        cur_len = 0
        readdata = bytearray(0)
        # shake hand
        if shakehand != 0:
            bflb_utils.printf(FLASH_LOAD_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return False, None
        start_time = (time.time() * 1000)
        log = ""
        while i < flash_data_len:
            cur_len = flash_data_len - i
            if cur_len > self._bflb_com_tx_size - 8:
                cur_len = self._bflb_com_tx_size - 8
            cmd_id = bflb_utils.hexstr_to_bytearray(self._com_cmds.get("flash_read")["cmd_id"])
            data_send = bflb_utils.int_to_4bytearray_l(
                i + start_addr) + bflb_utils.int_to_4bytearray_l(cur_len)
            try_cnt = 0
            while True:
                ret, data_read = self.com_process_one_cmd("flash_read", cmd_id, data_send)
                if ret.startswith("OK"):
                    break
                if try_cnt < self._checksum_err_retry_limit:
                    bflb_utils.printf("Retry")
                    try_cnt += 1
                else:
                    self.error_code_print("0035")
                    return False, None
            i += cur_len
            log += ("Read " + str(i) + "/" + str(flash_data_len))
            if len(log) > 50:
                bflb_utils.printf(log)
                log = ""
            else:
                log += "\n"
            if callback is not None:
                callback(i, flash_data_len, "APP_VR")
            readdata += data_read
        bflb_utils.printf(log)
        bflb_utils.printf("Flash read time cost(ms): ", (time.time() * 1000) - start_time)
        bflb_utils.printf("Finished")
        if file is not None:
            fp = open_file(file, 'wb+')
            fp.write(readdata)
            fp.close()
        return True, readdata

    def flash_xip_read_main_process(self,
                                    start_addr,
                                    flash_data_len,
                                    shakehand=0,
                                    file=None,
                                    callback=None):
        bflb_utils.printf("========= flash read =========")
        i = 0
        cur_len = 0
        readdata = bytearray(0)
        # shake hand
        if shakehand != 0:
            bflb_utils.printf(FLASH_LOAD_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return False, None
        start_time = (time.time() * 1000)
        log = ""
        cmd_id = bflb_utils.hexstr_to_bytearray(
            self._com_cmds.get("flash_xip_read_start")["cmd_id"])
        ret, dmy = self.com_process_one_cmd("flash_xip_read_start", cmd_id, bytearray(0))
        if ret.startswith("OK") is False:
            self.error_code_print("0039")
            return False, None
        while i < flash_data_len:
            cur_len = flash_data_len - i
            if cur_len > self._bflb_com_tx_size - 8:
                cur_len = self._bflb_com_tx_size - 8
            cmd_id = bflb_utils.hexstr_to_bytearray(self._com_cmds.get("flash_xip_read")["cmd_id"])
            data_send = bflb_utils.int_to_4bytearray_l(
                i + start_addr) + bflb_utils.int_to_4bytearray_l(cur_len)
            try_cnt = 0
            while True:
                ret, data_read = self.com_process_one_cmd("flash_xip_read", cmd_id, data_send)
                if ret.startswith("OK"):
                    break
                if try_cnt < self._checksum_err_retry_limit:
                    bflb_utils.printf("Retry")
                    try_cnt += 1
                else:
                    self.error_code_print("0035")
                    return False, None
            i += cur_len
            log += ("Read " + str(i) + "/" + str(flash_data_len))
            if len(log) > 50:
                bflb_utils.printf(log)
                log = ""
            else:
                log += "\n"
            if callback is not None:
                callback(i, flash_data_len, "APP_VR")
            readdata += data_read
        cmd_id = bflb_utils.hexstr_to_bytearray(
            self._com_cmds.get("flash_xip_read_finish")["cmd_id"])
        ret, dmy = self.com_process_one_cmd("flash_xip_read_finish", cmd_id, bytearray(0))
        if ret.startswith("OK") is False:
            self.error_code_print("0039")
            return False, None
        bflb_utils.printf(log)
        bflb_utils.printf("Flash read time cost(ms): ", (time.time() * 1000) - start_time)
        bflb_utils.printf("Finished")
        if file is not None:
            fp = open_file(file, 'wb+')
            fp.write(readdata)
            fp.close()
        return True, readdata

    def flash_read_sha_main_process(self,
                                    start_addr,
                                    flash_data_len,
                                    shakehand=0,
                                    file=None,
                                    callback=None):
        readdata = bytearray(0)
        # shake hand
        if shakehand != 0:
            bflb_utils.printf(FLASH_LOAD_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return False, None
        start_time = (time.time() * 1000)
        log = ""
        cmd_id = bflb_utils.hexstr_to_bytearray(self._com_cmds.get("flash_readSha")["cmd_id"])
        data_send = bflb_utils.int_to_4bytearray_l(start_addr) + bflb_utils.int_to_4bytearray_l(
            flash_data_len)
        try_cnt = 0
        while True:
            ret, data_read = self.com_process_one_cmd("flash_readSha", cmd_id, data_send)
            if ret.startswith("OK"):
                break
            if try_cnt < self._checksum_err_retry_limit:
                bflb_utils.printf("Retry")
                try_cnt += 1
            else:
                self.error_code_print("0038")
                return False, None
        log += ("Read " + "Sha256" + "/" + str(flash_data_len))
        if callback is not None:
            callback(flash_data_len, flash_data_len, "APP_VR")
        readdata += data_read
        bflb_utils.printf(log)
        bflb_utils.printf("Flash readsha time cost(ms): ", (time.time() * 1000) - start_time)
        bflb_utils.printf("Finished")
        if file is not None:
            fp = open_file(file, 'wb+')
            fp.write(readdata)
            fp.close()
        return True, readdata

    def flash_xip_read_sha_main_process(self,
                                        start_addr,
                                        flash_data_len,
                                        shakehand=0,
                                        file=None,
                                        callback=None):
        readdata = bytearray(0)
        # shake hand
        if shakehand != 0:
            bflb_utils.printf(FLASH_LOAD_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return False, None
        cmd_id = bflb_utils.hexstr_to_bytearray(
            self._com_cmds.get("flash_xip_read_start")["cmd_id"])
        ret, dmy = self.com_process_one_cmd("flash_xip_read_start", cmd_id, bytearray(0))
        if ret.startswith("OK") is False:
            self.error_code_print("0039")
            return False, None
        start_time = (time.time() * 1000)
        log = ""
        cmd_id = bflb_utils.hexstr_to_bytearray(self._com_cmds.get("flash_xip_readSha")["cmd_id"])
        data_send = bflb_utils.int_to_4bytearray_l(start_addr) + bflb_utils.int_to_4bytearray_l(
            flash_data_len)
        try_cnt = 0
        while True:
            ret, data_read = self.com_process_one_cmd("flash_xip_readSha", cmd_id, data_send)
            if ret.startswith("OK"):
                break
            if try_cnt < self._checksum_err_retry_limit:
                bflb_utils.printf("Retry")
                try_cnt += 1
            else:
                bflb_utils.printf("Read Fail")
                # exit xip mode
                cmd_id = bflb_utils.hexstr_to_bytearray(
                    self._com_cmds.get("flash_xip_read_finish")["cmd_id"])
                ret, dmy = self.com_process_one_cmd("flash_xip_read_finish", cmd_id, bytearray(0))
                if ret.startswith("OK") is False:
                    self.error_code_print("0039")
                    return False, None
                return False, None
        log += ("Read " + "Sha256" + "/" + str(flash_data_len))
        if callback is not None:
            callback(flash_data_len, flash_data_len, "APP_VR")
        readdata += data_read
        bflb_utils.printf(log)
        bflb_utils.printf("Flash xip readsha time cost(ms): ", (time.time() * 1000) - start_time)
        bflb_utils.printf("Finished")
        if file is not None:
            fp = open_file(file, 'wb+')
            fp.write(readdata)
            fp.close()
        # exit xip mode
        cmd_id = bflb_utils.hexstr_to_bytearray(
            self._com_cmds.get("flash_xip_read_finish")["cmd_id"])
        ret, dmy = self.com_process_one_cmd("flash_xip_read_finish", cmd_id, bytearray(0))
        if ret.startswith("OK") is False:
            self.error_code_print("0039")
            return False, None
        return True, readdata

    def flash_write_check_main_process(self, shakehand=0):
        bflb_utils.printf("Write check")
        # shake hand
        if shakehand != 0:
            bflb_utils.printf(FLASH_LOAD_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return False
        # send command
        cmd_id = bflb_utils.hexstr_to_bytearray(self._com_cmds.get("flash_write_check")["cmd_id"])
        try_cnt = 0
        while True:
            retry = 0
            if self._decompress_write:
                retry = 10
            ret, dmy = self.com_process_one_cmd("flash_write_check", cmd_id, bytearray(0))
            if ret.startswith("OK"):
                break
            if try_cnt < self._checksum_err_retry_limit + retry:
                bflb_utils.printf("Retry")
                try_cnt += 1
            else:
                self.error_code_print("0037")
                return False
        return True

    def flash_load_xz_compress(self, file):
        try:
            xz_filters = [
                {
                    "id": lzma.FILTER_LZMA2,
                    "dict_size": 32768
                },
            ]
            fp = open_file(file, 'rb')
            data = bytearray(fp.read())
            fp.close()
            flash_data = lzma.compress(data, check=lzma.CHECK_CRC32, filters=xz_filters)
            flash_data_len = len(flash_data)
        except Exception as e:
            bflb_utils.printf(e)
            return False, None, None
        return True, flash_data, flash_data_len

    def flash_load_main_process(self, file, start_addr, erase=1, callback=None):
        fp = open_file(file, 'rb')
        flash_data = bytearray(fp.read())
        fp.close()
        flash_data_len = len(flash_data)
        i = 0
        cur_len = 0
        if erase == 1:
            ret = self.flash_erase_main_process(start_addr, start_addr + flash_data_len - 1)
            if ret is False:
                return False
        start_time = (time.time() * 1000)
        log = ""
        if self._decompress_write and flash_data_len > 4 * 1024:
            # set rx timeout to 9s to avoid chip decompress data cause timeout
            self._bflb_com_if.if_set_rx_timeout(30.0)
            start_addr |= 0x80000000
            cmd_name = "flash_decompress_write"
            ret, flash_data, flash_data_len = self.flash_load_xz_compress(file)
            if ret is False:
                bflb_utils.printf("Flash write data xz fail")
                self._bflb_com_if.if_set_rx_timeout(self._default_time_out)
                return False
            # if compress take time > 2.2s, chip timeout, reshakehand
            if (time.time() * 1000) - start_time > 2200:
                bflb_utils.printf(FLASH_LOAD_SHAKE_HAND)
                if self.img_load_shake_hand() is False:
                    return False
            # if compress take time > 1.8s, delay 0.5s make sure chip timeout, and reshakehand
            # if compress take time <= 1.8s, no need reshakehand
            elif (time.time() * 1000) - start_time > 1800:
                time.sleep(0.5)
                bflb_utils.printf(FLASH_LOAD_SHAKE_HAND)
                if self.img_load_shake_hand() is False:
                    return False
            bflb_utils.printf("decompress flash load ", flash_data_len)
        else:
            cmd_name = "flash_write"
        while i < flash_data_len:
            cur_len = flash_data_len - i
            if cur_len > self._bflb_com_tx_size - 8:
                cur_len = self._bflb_com_tx_size - 8
            cmd_id = bflb_utils.hexstr_to_bytearray(self._com_cmds.get(cmd_name)["cmd_id"])
            data_send = bflb_utils.int_to_4bytearray_l(i + start_addr) + flash_data[i:i + cur_len]
            start_addr &= 0x7FFFFFFF
            try_cnt = 0
            while True:
                ret, dmy = self.com_process_one_cmd(cmd_name, cmd_id, data_send)
                if ret.startswith("OK"):
                    break
                if try_cnt < self._checksum_err_retry_limit:
                    bflb_utils.printf("Retry")
                    try_cnt += 1
                else:
                    self.error_code_print("0036")
                    self._bflb_com_if.if_set_rx_timeout(self._default_time_out)
                    return False
            i += cur_len
            log = ("Load " + str(i) + "/" + str(flash_data_len) + " {\"progress\":" + str(
                (i * 100) // flash_data_len) + "}")
            bflb_utils.printf(log)
            if callback is not None and flash_data_len > 200:
                callback(i, flash_data_len, "APP_WR")
        bflb_utils.printf(log)
        if self.flash_write_check_main_process() is False:
            bflb_utils.printf("Flash write check fail")
            self._bflb_com_if.if_set_rx_timeout(self._default_time_out)
            return False
        self._bflb_com_if.if_set_rx_timeout(self._default_time_out)
        bflb_utils.printf("Flash load time cost(ms): ", (time.time() * 1000) - start_time)
        bflb_utils.printf("Finished")
        return True

    def setOpenFile_zip(self, packet_file):
        bflb_utils.printf("Unpack file")
        filename = packet_file
        try:
            if filename:
                efuse_burn = "false"
                eflash_loader_file = ""
                zip_file = zipfile.ZipFile(filename)
                zip_list = zip_file.namelist()
                for f in zip_list:
                    if f.find("efusedata.bin") != -1:
                        efuse_burn = "true"
                    if f.find("eflash_loader_cfg") != -1:
                        eflash_loader_file = os.path.join(app_path, 'chips', f)
                    zip_file.extract(f, os.path.join(app_path, 'chips'))
                zip_file.close()
                cfg = BFConfigParser()
                cfg.read(eflash_loader_file)
                if cfg.has_option("EFUSE_CFG", "burn_en"):
                    cfg.set("EFUSE_CFG", "burn_en", efuse_burn)
                    cfg.write(eflash_loader_file, 'w')
                # os.remove(latest_zip_file)
                bflb_utils.printf("Unpack Success")
        except Exception as err:
            error = str(err)
            bflb_utils.printf("Unpack fail: " + error)
            self.error_code_print("000E")


    def flash_cfg_option(self, read_flash_id, flash_para_file, flash_set, id_valid_flag, binfile, \
                               cfgfile, cfg, create_img_callback=None, create_simple_callback=None):
        ret = bflb_flash_select.flash_bootheader_config_check(self._chip_name, self._chip_type,
                                                              read_flash_id, convert_path(binfile),
                                                              flash_para_file)
        if ret is False:
            bflb_utils.printf("flashcfg not match first")
            # recreate bootinfo.bin
            if self.is_conf_exist(read_flash_id) is True:
                bflb_utils.update_cfg(cfg, "FLASH_CFG", "flash_id", read_flash_id)
                if isinstance(cfgfile, BFConfigParser) == False:
                    cfg.write(cfgfile, "w+")
                if create_img_callback is not None:
                    create_img_callback()
                elif create_simple_callback is not None:
                    create_simple_callback()
            else:
                self.error_code_print("003D")
                return False
            ret = bflb_flash_select.flash_bootheader_config_check(self._chip_name, self._chip_type,
                                                                  read_flash_id,
                                                                  convert_path(binfile),
                                                                  flash_para_file)
            if ret is False:
                bflb_utils.printf("flashcfg not match again")
                self.error_code_print("0040")
                return False
        # set flash config
        if flash_para_file and id_valid_flag != '80':
            bflb_utils.printf("flash para file: ", flash_para_file)
            fp = open_file(flash_para_file, 'rb')
            flash_para = bytearray(fp.read())
            fp.close()
            ret = self.flash_set_para_main_process(flash_set, flash_para, self._need_shake_hand)
            self._need_shake_hand = False
            if ret is False:
                return False

    def flash_load_tips(self):
        bflb_utils.printf(
            "########################################################################")
        bflb_utils.printf("请按照以下描述排查问题：")
        bflb_utils.printf("是否降低烧录波特率到500K测试过")
        bflb_utils.printf("烧写文件的大小是否超过Flash所能存储的最大空间")
        bflb_utils.printf("Flash是否被写保护")
        bflb_utils.printf(
            "########################################################################")

    def flash_load_opt(self, file, start_addr, erase=1, verify=0, shakehand=0, callback=None):
        bflb_utils.printf("========= flash load =========")
        if shakehand != 0:
            bflb_utils.printf(FLASH_LOAD_SHAKE_HAND)
            if self.img_load_shake_hand() is False:
                return False
        if self._flash2_select is True:
            start_addr -= self._flash1_size
        if self._chip_type == "bl808" or self._chip_type == "bl616" or \
           self._chip_type == "wb03" or self._chip_type == "bl628":
            if self._mass_opt is False:
                fp = open_file(file, 'rb')
                flash_data = bytearray(fp.read())
                fp.close()
                flash_data_len = len(flash_data)
                end_addr = start_addr + flash_data_len - 1
                if start_addr <= 0x1000 and end_addr > 0x1000:
                    ret, flash_read_data = self.flash_read_main_process(
                        0x1000, 0x1000, 0, None, callback)
                    if flash_read_data[0:4] == bflb_utils.int_to_4bytearray_b(0x424C5246):
                        bflb_utils.printf(
                            "RF para already write at flash 0x1000 addr, replace it.")
                        flash_data[0x1000:0x2000] = flash_read_data[0x0:0x1000]
                        fp = open_file(file, 'wb')
                        fp.write(flash_data)
                        fp.close()
        ret = self.flash_load_main_process(file, start_addr, erase, callback)
        if ret is False:
            bflb_utils.printf("Flash load fail")
            return ret
        # temp var to store imgage sha-256
        fw_sha256 = ''
        fp = open_file(file, 'rb')
        flash_data = fp.read()
        fp.close()
        flash_data_len = len(flash_data)
        if flash_data_len > (2 * 1024 * 1024):
            # if program file size is greater than 2*1024*1024, xip read sha will use more time
            self._bflb_com_if.if_set_rx_timeout(2.0 * (flash_data_len / (2 * 1024 * 1024) + 1))
        sh = hashlib.sha256()
        sh.update(flash_data)
        fw_sha256 = sh.hexdigest()
        fw_sha256 = bflb_utils.hexstr_to_bytearray(fw_sha256)
        bflb_utils.printf("Sha caled by host: ", binascii.hexlify(fw_sha256).decode('utf-8'))
        del sh
        # xip mode verify
        bflb_utils.printf("xip mode Verify")
        ret, read_data = self.flash_xip_read_sha_main_process(start_addr, flash_data_len, 0, None,
                                                              callback)
        bflb_utils.printf("Sha caled by dev: ", binascii.hexlify(read_data).decode('utf-8'))
        if ret is True and read_data == fw_sha256:
            bflb_utils.printf("Verify success")
        else:
            bflb_utils.printf("Verify fail")
            self.flash_load_tips()
            self.error_code_print("003E")
            ret = False
        if verify > 0:
            fp = open_file(file, 'rb')
            flash_data = bytearray(fp.read())
            fp.close()
            flash_data_len = len(flash_data)
            ret, read_data = self.flash_read_main_process(start_addr, flash_data_len, 0, None,
                                                          callback)
            if ret is True and read_data == flash_data:
                bflb_utils.printf("Verify success")
            else:
                bflb_utils.printf("Verify fail")
                self.flash_load_tips()
                self.error_code_print("003E")
                ret = False
            # sbus mode verify
            bflb_utils.printf("sbus mode Verify")
            ret, read_data = self.flash_read_sha_main_process(start_addr, flash_data_len, 0, None,
                                                              callback)
            bflb_utils.printf("Sha caled by dev: ", binascii.hexlify(read_data).decode('utf-8'))
            if ret is True and read_data == fw_sha256:
                bflb_utils.printf("Verify success")
            else:
                bflb_utils.printf("Verify fail")
                self.flash_load_tips()
                self.error_code_print("003E")
                ret = False
        self._bflb_com_if.if_set_rx_timeout(self._default_time_out)
        return ret

    def flash_load_specified(self,
                             file,
                             start_addr,
                             erase=1,
                             verify=0,
                             shakehand=0,
                             callback=None):
        ret = False
        if self._skip_len > 0:
            bflb_utils.printf("skip flash file, skip addr 0x%08X, skip len 0x%08X"\
                               % (self._skip_addr, self._skip_len))
            fp = open_file(file, 'rb')
            flash_data = fp.read()
            fp.close()
            flash_data_len = len(flash_data)
            if self._skip_addr <= start_addr and \
               self._skip_addr + self._skip_len > start_addr and \
               self._skip_addr + self._skip_len < start_addr + flash_data_len:
                addr = self._skip_addr + self._skip_len
                data = flash_data[self._skip_addr + self._skip_len - start_addr:]
                filename, ext = os.path.splitext(file)
                file_temp = os.path.join(app_path, filename + '_skip' + ext)
                fp = open(file_temp, 'wb')
                fp.write(data)
                fp.close()
                ret = self.flash_load_opt(file_temp, addr, erase, verify, shakehand, callback)
            elif self._skip_addr > start_addr and \
                 self._skip_addr + self._skip_len < start_addr + flash_data_len:
                addr = start_addr
                data = flash_data[:self._skip_addr - start_addr]
                filename, ext = os.path.splitext(file)
                file_temp = os.path.join(app_path, filename + '_skip1' + ext)
                fp = open(file_temp, 'wb')
                fp.write(data)
                fp.close()
                ret = self.flash_load_opt(file_temp, addr, erase, verify, shakehand, callback)
                addr = self._skip_addr + self._skip_len
                data = flash_data[self._skip_addr + self._skip_len - start_addr:]
                filename, ext = os.path.splitext(file)
                file_temp = os.path.join(app_path, filename + '_skip2' + ext)
                fp = open(file_temp, 'wb')
                fp.write(data)
                fp.close()
                ret = self.flash_load_opt(file_temp, addr, erase, verify, shakehand, callback)
            elif self._skip_addr > start_addr and \
                 self._skip_addr < start_addr + flash_data_len and \
                 self._skip_addr + self._skip_len >= start_addr + flash_data_len:
                addr = start_addr
                data = flash_data[:self._skip_addr - start_addr]
                filename, ext = os.path.splitext(file)
                file_temp = os.path.join(app_path, filename + '_skip' + ext)
                fp = open(file_temp, 'wb')
                fp.write(data)
                fp.close()
                ret = self.flash_load_opt(file_temp, addr, erase, verify, shakehand, callback)
            elif self._skip_addr <= start_addr and \
                 self._skip_addr + self._skip_len >= start_addr + flash_data_len:
                return True
            else:
                ret = self.flash_load_opt(file, start_addr, erase, verify, shakehand, callback)
        else:
            ret = self.flash_load_opt(file, start_addr, erase, verify, shakehand, callback)
        return ret

    def log_read_process(self, shakehand=1, callback=None):
        readdata = bytearray(0)
        try:
            # shake hand
            if shakehand != 0:
                bflb_utils.printf(FLASH_LOAD_SHAKE_HAND)
                if self.img_load_shake_hand() is False:
                    bflb_utils.printf("Shake hand redo")
            cmd_id = bflb_utils.hexstr_to_bytearray(self._com_cmds.get("log_read")["cmd_id"])
            ret, data_read = self.com_process_one_cmd("log_read", cmd_id, bytearray(0))
            bflb_utils.printf("Read log ")
            if ret.startswith("OK") is False:
                bflb_utils.printf("Read Fail")
                return False, None
            readdata += data_read
            bflb_utils.printf("log: ")
            bflb_utils.printf("========================================================")
            bflb_utils.printf(readdata.decode('utf-8'))
            bflb_utils.printf("========================================================")
            bflb_utils.printf("Finished")
        except Exception as e:
            bflb_utils.printf(e)
            self.error_code_print("0006")
            traceback.print_exc(limit=NUM_ERR, file=sys.stdout)
            return False, None
        return True, readdata

    def get_active_fwbin_addr(self, ptaddr1, ptaddr2, entry_name, shakehand=1, callback=None):
        fwaddr = 0
        maxlen = 0
        ptdata = bytearray(0)
        table_count = 0
        try:
            # shake hand
            if shakehand != 0:
                bflb_utils.printf(FLASH_LOAD_SHAKE_HAND)
                if self.img_load_shake_hand() is False:
                    return False, 0
            bflb_utils.printf("read partition 1 0x", ptaddr1)
            ret, ptdata1 = self.flash_read_main_process(int(ptaddr1, 16), 0x300, 0, None, callback)
            if ret is False:
                bflb_utils.printf("read pt 1 data fail")
            bflb_utils.printf("read partition 2 0x", ptaddr2)
            ret, ptdata2 = self.flash_read_main_process(int(ptaddr2, 16), 0x300, 0, None, callback)
            if ret is False:
                bflb_utils.printf("read pt 2 data fail")
            sub_module = __import__("libs." + self._chip_type, fromlist=[self._chip_type])
            ret1, table_count1, age1 = sub_module.partition_cfg_do.check_pt_data(ptdata1)
            if ret1 is False:
                bflb_utils.printf("pt table 1 check fail")
            ret2, table_count2, age2 = sub_module.partition_cfg_do.check_pt_data(ptdata2)
            if ret2 is False:
                bflb_utils.printf("pt table 2 check fail")
            if ret1 is not False and ret2 is not False:
                if age1 >= age2:
                    ptdata = ptdata1[16:]
                    table_count = table_count1
                else:
                    ptdata = ptdata2[16:]
                    table_count = table_count2
            elif ret1 is not False:
                ptdata = ptdata1[16:]
                table_count = table_count1
            elif ret2 is not False:
                ptdata = ptdata2[16:]
                table_count = table_count2
            else:
                bflb_utils.printf("pt table all check fail")
                return False, 0, 0
            for i in range(table_count):
                if entry_name == ptdata[i * 36 + 3:i * 36 + 3 +
                                        len(entry_name)].decode(encoding="utf-8"):
                    addr_start = 0
                    if bflb_utils.bytearray_to_int(ptdata[i * 36 + 2:i * 36 + 3]) != 0:
                        addr_start = i * 36 + 16
                    else:
                        addr_start = i * 36 + 12
                    fwaddr = bflb_utils.bytearray_to_int(ptdata[addr_start + 0:addr_start + 1]) + \
                            (bflb_utils.bytearray_to_int(ptdata[addr_start + 1:addr_start + 2]) << 8) + \
                            (bflb_utils.bytearray_to_int(ptdata[addr_start + 2:addr_start + 3]) << 16) + \
                            (bflb_utils.bytearray_to_int(ptdata[addr_start + 3:addr_start + 4]) << 24)
                    maxlen = bflb_utils.bytearray_to_int(ptdata[addr_start + 0 + 8:addr_start + 1 + 8]) + \
                            (bflb_utils.bytearray_to_int(ptdata[addr_start + 1 + 8:addr_start + 2 + 8]) << 8) + \
                            (bflb_utils.bytearray_to_int(ptdata[addr_start + 2 + 8:addr_start + 3 + 8]) << 16) + \
                            (bflb_utils.bytearray_to_int(ptdata[addr_start + 3 + 8:addr_start + 4 + 8]) << 24)
        except Exception as e:
            bflb_utils.printf(e)
            traceback.print_exc(limit=NUM_ERR, file=sys.stdout)
            return False, 0, 0
        return True, fwaddr, maxlen

    def load_romfs_data(self, data, addr, verify, shakehand=1, callback=None):
        romfs_path = os.path.join(chip_path, self._chip_name, "romfs")
        dst_img_name = os.path.join(chip_path, self._chip_name, "img_create_iot/media.bin")
        if not os.path.exists(romfs_path):
            os.makedirs(romfs_path)
        private_key_file = os.path.join(romfs_path, "private_key")
        f = open(private_key_file, 'w+')
        f.write(data)
        f.close()
        exe = None
        if os.name == 'nt':
            exe = os.path.join(app_path, 'utils/genromfs', 'genromfs.exe')
        elif os.name == 'posix':
            machine = os.uname().machine
            if machine == 'x86_64':
                exe = os.path.join(app_path, 'utils/genromfs', 'genromfs_amd64')
            elif machine == 'armv7l':
                exe = os.path.join(app_path, 'utils/genromfs', 'genromfs_armel')
        if exe is None:
            bflb_utils.printf('NO supported genromfs exe for your platform!')
            return -1
        dir = os.path.abspath(romfs_path)
        dst = os.path.abspath(dst_img_name)
        # bflb_utils.printf('Generating romfs image %s using directory %s ... ' % (dst, dir))
        CREATE_NO_WINDOW = 0x08000000
        subprocess.call([exe, '-d', dir, '-f', dst], creationflags=CREATE_NO_WINDOW)
        bflb_utils.printf("========= programming romfs ", dst_img_name, " to ", hex(addr))
        ret = self.flash_load_specified(dst_img_name, addr, 1, verify, 0, callback)
        return ret

    def load_firmware_bin(self, file, verify, shakehand=1, callback=None):
        entry_name = ""
        sub_module = __import__("libs." + self._chip_type, fromlist=[self._chip_type])
        pt_addr1 = sub_module.partition_cfg_do.partition1_addr
        pt_addr2 = sub_module.partition_cfg_do.partition2_addr
        entry_name = sub_module.partition_cfg_do.fireware_name
        ret, fwaddr, max_len = self.get_active_fwbin_addr(pt_addr1, pt_addr2, entry_name,
                                                          shakehand, callback)
        if ret is False:
            bflb_utils.printf("get active fwbin addr fail")
            return False
        if os.path.getsize(file) > max_len:
            bflb_utils.printf("fwbin size > max len ", os.path.getsize(file))
            return False
        bflb_utils.printf("========= programming firmare ", file, " to ", hex(fwaddr))
        ret = self.flash_load_specified(file, fwaddr, 1, verify, 0, callback)
        return ret

    def get_suitable_conf_name(self, cfg_dir, flash_id):
        conf_files = []
        for home, dirs, files in os.walk(cfg_dir):
            for filename in files:
                if filename.split('_')[-1] == flash_id + '.conf':
                    conf_files.append(filename)
        if len(conf_files) > 1:
            bflb_utils.printf("Flash id duplicate and alternative is:")
            for i in range(len(conf_files)):
                tmp = conf_files[i].split('.')[0]
                bflb_utils.printf("%d:%s" % (i + 1, tmp))
            return conf_files[i]
        elif len(conf_files) == 1:
            return conf_files[0]
        else:
            return ""

    def get_factory_config_info(self, file, output_file):
        version = 'ver0.0.1'
        csv_mac = ''
        info_dict = {
            'ProductKey': '',
            'DeviceName': '',
            'DeviceSecret': '',
            'ProductSecret': '',
            'ProductID': ''
        }
        lock_file = open("lock.txt", 'w+')
        portalocker.lock(lock_file, portalocker.LOCK_EX)
        try:
            with open(file, 'r') as csvfile:
                reader = csv.DictReader(csvfile)
                list_csv = []
                list_product_secret = []
                list_product_id = []
                for row in reader:
                    list_product_secret.append(info_dict['ProductSecret'])
                    list_product_id.append(info_dict['ProductID'])
                    if 'Burned' not in row:
                        if csv_mac == '':
                            burnkey = {'Burned': 'P'}
                            row.update(burnkey)
                        list_csv.append(row)
                    elif row.get('Burned', "") != "Y" and row.get('Burned', "") != "P":
                        if csv_mac == '':
                            row['Burned'] = 'P'
                        list_csv.append(row)
                    else:
                        list_csv.append(row)
                        continue
                    if csv_mac == '':
                        info_dict['ProductKey'] = row.get('ProductKey', "")
                        csv_mac = info_dict['DeviceName'] = row.get('DeviceName', "")
                        info_dict['DeviceSecret'] = row.get('DeviceSecret', "")
                        info_dict['ProductSecret'] = row.get('ProductSecret', "")
                        info_dict['ProductID'] = row.get('ProductID', "")
                        if len(set(list_product_secret)) > 1:
                            print("Error: ProductSecret is not same")
                            return False, csv_mac
                        if len(set(list_product_id)) > 1:
                            print("Error: ProductID is not same")
                            return False, csv_mac
                        if re.match(r"^([0-9a-fA-F]{2,2}){6,6}$", csv_mac) is None:
                            print("Error: " + csv_mac + ' is not a valid MAC address')
                            return False, csv_mac
                        self._csv_data = csv_mac
                        self._csv_file = file
                if csv_mac == '':
                    bflb_utils.printf("All facotry info used up!")
                    lock_file.close()
                    os.remove("lock.txt")
                    return False, csv_mac
                else:
                    ret, efusedata = self.efuse_read_main_process(0,
                                                                  128,
                                                                  self._need_shake_hand,
                                                                  file=None,
                                                                  security_read=False)
                    if ret is False:
                        return False, csv_mac
                    efusedata = bytearray(efusedata)
                    data_efuse = csv_mac[10:12] + csv_mac[8:10] + csv_mac[6:8] + csv_mac[
                        4:6] + csv_mac[2:4] + csv_mac[0:2]
                    mac_bytearray = bflb_utils.hexstr_to_bytearray(data_efuse)
                    sub_module = __import__("libs." + self._chip_type, fromlist=[self._chip_type])
                    slot0_addr = sub_module.efuse_cfg_keys.efuse_mac_slot_offset["slot0"]
                    slot1_addr = sub_module.efuse_cfg_keys.efuse_mac_slot_offset["slot1"]
                    slot2_addr = sub_module.efuse_cfg_keys.efuse_mac_slot_offset["slot2"]
                    bflb_utils.printf(mac_bytearray)
                    bflb_utils.printf(efusedata[int(slot0_addr, 10):int(slot0_addr, 10) + 6])
                    bflb_utils.printf(efusedata[int(slot1_addr, 10):int(slot1_addr, 10) + 6])
                    bflb_utils.printf(efusedata[int(slot2_addr, 10):int(slot2_addr, 10) + 6])
                    if efusedata[int(slot2_addr, 10):int(slot2_addr, 10) + 6] == mac_bytearray:
                        bflb_utils.printf("DeviceName was already write at efuse mac slot 2")
                        return False, csv_mac
                    elif efusedata[int(slot1_addr, 10):int(slot1_addr, 10) + 6] == mac_bytearray:
                        bflb_utils.printf("DeviceName was already write at efuse mac slot 1")
                        return False, csv_mac
                    elif efusedata[int(slot0_addr, 10):int(slot0_addr, 10) + 6] == mac_bytearray:
                        bflb_utils.printf("DeviceName was already write at efuse mac slot 0")
                        return False, csv_mac
            with open(file, 'w', newline='') as f:
                headers = [
                    'ProductKey', 'DeviceName', 'DeviceSecret', 'ProductSecret', 'ProductID',
                    'Burned'
                ]
                f_csv = csv.DictWriter(f, headers)
                f_csv.writeheader()
                f_csv.writerows(list_csv)
            lock_file.close()
            os.remove("lock.txt")
        except Exception as e:
            bflb_utils.printf(e)
            lock_file.close()
            os.remove("lock.txt")
            return False, csv_mac
        try:
            data_value = bytearray()
            data_len = 0
            temp = bflb_utils.int_to_4bytearray_l(0x01)
            for b in temp:
                data_value.append(b)
            temp = bflb_utils.int_to_4bytearray_l(len(version) + 1)
            for b in temp:
                data_value.append(b)
            ver = bflb_utils.string_to_bytearray(version)
            for b in ver:
                data_value.append(b)
            data_value.append(0x00)
            data_len += 4 + 4 + len(version) + 1
            for key, value in info_dict.items():
                if value != '':
                    temp = bflb_utils.int_to_4bytearray_l(0x0101)
                    for b in temp:
                        data_value.append(b)
                    temp = bflb_utils.int_to_4bytearray_l(len(key) + 1)
                    for b in temp:
                        data_value.append(b)
                    temp = bflb_utils.string_to_bytearray(key)
                    for b in temp:
                        data_value.append(b)
                    data_value.append(0x00)
                    data_len += 4 + 4 + len(key) + 1
                    temp = bflb_utils.int_to_4bytearray_l(0x0102)
                    for b in temp:
                        data_value.append(b)
                    temp = bflb_utils.int_to_4bytearray_l(len(value) + 1)
                    for b in temp:
                        data_value.append(b)
                    temp = bflb_utils.string_to_bytearray(value)
                    for b in temp:
                        data_value.append(b)
                    data_value.append(0x00)
                    data_len += 4 + 4 + len(value) + 1
            info = bytearray()
            info.append(0xA5)
            info.append(0xA5)
            info.append(0xA5)
            info.append(0xA5)
            temp = bflb_utils.int_to_4bytearray_l(data_len)
            for b in temp:
                info.append(b)
            for _ in range(40):
                info.append(0xFF)
            sh = hashlib.sha256()
            sh.update(data_value)
            data_sha256 = sh.hexdigest()
            data_sha256 = bflb_utils.hexstr_to_bytearray(data_sha256)
            temp = data_sha256[-16:]
            for b in temp:
                info.append(b)
            for b in data_value:
                info.append(b)
            with open(output_file, mode="wb") as f:
                f.write(info)
        except Exception as e:
            bflb_utils.printf(e)
            return False, csv_mac
        return True, csv_mac

    def is_conf_exist(self, flash_id):
        if conf_sign:
            cfg_dir = app_path + "/utils/flash/" + cgc.lower_name + '/'
        else:
            cfg_dir = app_path + "/utils/flash/" + self._chip_type + '/'
        conf_name = self.get_suitable_conf_name(cfg_dir, flash_id)
        if os.path.isfile(cfg_dir + conf_name) is False:
            return False
        else:
            return True

    def clock_para_update(self, file):
        if os.path.isfile(file) is False:
            efuse_bootheader_path = os.path.join(chip_path, self._chip_name, "efuse_bootheader")
            efuse_bh_cfg = efuse_bootheader_path + "/efuse_bootheader_cfg.conf"
            sub_module = __import__("libs." + self._chip_type, fromlist=[self._chip_type])
            section = "BOOTHEADER_GROUP0_CFG"
            fp = open(efuse_bh_cfg, 'r')
            data = fp.read()
            fp.close()
            if "BOOTHEADER_CFG" in data:
                section = "BOOTHEADER_CFG"
            elif "BOOTHEADER_CPU0_CFG" in data:
                section = "BOOTHEADER_CPU0_CFG"
            elif "BOOTHEADER_GROUP0_CFG" in data:
                section = "BOOTHEADER_GROUP0_CFG"
            bh_data, tmp = bflb_efuse_boothd_create.update_data_from_cfg(
                sub_module.bootheader_cfg_keys.bootheader_cfg_keys, efuse_bh_cfg, section)
            bh_data = bflb_efuse_boothd_create.bootheader_update_flash_pll_crc(
                bh_data, self._chip_type)
            fp = open(file, 'wb+')
            if self._chip_type == "bl808":
                if section == "BOOTHEADER_GROUP0_CFG":
                    fp.write(bh_data[100:100 + 28])
            elif self._chip_type == "bl628":
                if section == "BOOTHEADER_GROUP0_CFG":
                    fp.write(bh_data[100:100 + 24])
            elif self._chip_type == "bl616":
                if section == "BOOTHEADER_GROUP0_CFG":
                    fp.write(bh_data[100:100 + 20])
            elif self._chip_type == "wb03":
                if section == "BOOTHEADER_GROUP0_CFG":
                    fp.write(bh_data[208 + 100:208 + 100 + 20])
            elif self._chip_type == "bl702l":
                if section == "BOOTHEADER_CFG":
                    fp.write(bh_data[100:100 + 16])
            fp.close()
            # os.remove(efuse_bh_cfg)

        fp = open_file(file, 'rb')
        clock_para = bytearray(fp.read())
        fp.close()
        return clock_para

    def flash_para_update(self, file, jedec_id):
        flash_para = bytearray(0)
        if self.is_conf_exist(jedec_id) is True:
            sub_module = __import__("libs." + self._chip_type, fromlist=[self._chip_type])
            if conf_sign:
                cfg_dir = app_path + "/utils/flash/" + self._chip_name + '/'
            else:
                cfg_dir = app_path + "/utils/flash/" + self._chip_type + '/'
            conf_name = sub_module.flash_select_do.get_suitable_file_name(cfg_dir, jedec_id)
            offset, flashCfgLen, flash_para, flashCrcOffset, crcOffset = \
                bflb_flash_select.update_flash_para_from_cfg\
                (sub_module.bootheader_cfg_keys.bootheader_cfg_keys, cfg_dir+conf_name)
            fp = open(os.path.join(app_path, file), 'wb+')
            fp.write(flash_para)
            fp.close()
        return flash_para

    def efuse_flash_loader(self,
                           args,
                           eflash_loader_cfg,
                           eflash_loader_bin,
                           callback=None,
                           create_simple_callback=None,
                           create_img_callback=None,
                           macaddr_callback=None,
                           task_num=None):
        ret = None
        if task_num == None:
            bflb_utils.local_log_enable(True)
        bflb_utils.printf("Version: ", bflb_version.eflash_loader_version_text)
        start_time = (time.time() * 1000)
        try:
            retry = -1
            update_cutoff_time = True
            if task_num != None:
                if task_num > 256:
                    self._csv_burn_en = False
                    self._task_num = task_num - 256
                else:
                    self._csv_burn_en = True
                    self._task_num = task_num
            else:
                self._csv_burn_en = False
                self._task_num = None
            while True:
                if self._bflb_com_if is not None:
                    self._bflb_com_if.if_close()
                bflb_utils.printf("Program Start")
                ret, flash_burn_retry = self.efuse_flash_loader_do(
                    args, eflash_loader_cfg, eflash_loader_bin, callback, update_cutoff_time,
                    create_simple_callback, create_img_callback, macaddr_callback, task_num)
                self._skip_len = 0
                if ret == "repeat_burn":
                    if self._bflb_com_if is not None:
                        self._bflb_com_if.if_close()
                    return "repeat_burn"
                if self._cpu_reset is True:
                    bflb_utils.printf("Reset cpu")
                    self.reset_cpu()
                if self._retry_delay_after_cpu_reset > 0:
                    bflb_utils.printf("delay for uart timeout: ",
                                      self._retry_delay_after_cpu_reset)
                    time.sleep(self._retry_delay_after_cpu_reset)
                if retry == -1:
                    retry = flash_burn_retry
                if ret is True:
                    if not args.none:
                        bflb_utils.printf("All time cost(ms): ", (time.time() * 1000) - start_time)
                        time.sleep(0.1)
                        if self._bflb_com_if is not None:
                            self._bflb_com_if.if_close()
                            bflb_utils.printf("close interface")
                        if self._csv_data and self._csv_file:
                            lock_file = open("lock.txt", 'w+')
                            portalocker.lock(lock_file, portalocker.LOCK_EX)
                            with open(self._csv_file, 'r') as csvf:
                                reader = csv.DictReader(csvf)
                                list_csv = []
                                for row in reader:
                                    if row.get('DeviceName', "") == self._csv_data:
                                        if row.get('Burned', "") == 'P':
                                            row['Burned'] = 'Y'
                                        else:
                                            bflb_utils.printf(self._csv_data +
                                                              " status not programing")
                                    list_csv.append(row)
                                with open(self._csv_file, 'w', newline='') as f:
                                    headers = [
                                        'ProductKey', 'DeviceName', 'DeviceSecret',
                                        'ProductSecret', 'ProductID', 'Burned'
                                    ]
                                    f_csv = csv.DictWriter(f, headers)
                                    f_csv.writeheader()
                                    f_csv.writerows(list_csv)
                            lock_file.close()
                            os.remove("lock.txt")
                        bflb_utils.printf("[All Success]")
                        bflb_utils.local_log_save("log", self._input_macaddr)
                    return True
                else:
                    retry -= 1
                    bflb_utils.printf("Burn Retry")
                    bflb_utils.printf(retry)
                    if retry <= 0:
                        break
            bflb_utils.printf("Burn return with retry fail")
            if self._csv_data and self._csv_file:
                lock_file = open("lock.txt", 'w+')
                portalocker.lock(lock_file, portalocker.LOCK_EX)
                with open(self._csv_file, 'r') as csvf:
                    reader = csv.DictReader(csvf)
                    list_csv = []
                    for row in reader:
                        if row.get('DeviceName', "") == self._csv_data:
                            if row.get('Burned', "") == 'P':
                                row['Burned'] = ''
                            else:
                                bflb_utils.printf(self._csv_data + " status not programing")
                        list_csv.append(row)
                    with open(self._csv_file, 'w', newline='') as f:
                        headers = [
                            'ProductKey', 'DeviceName', 'DeviceSecret', 'ProductSecret',
                            'ProductID', 'Burned'
                        ]
                        f_csv = csv.DictWriter(f, headers)
                        f_csv.writeheader()
                        f_csv.writerows(list_csv)
                lock_file.close()
                os.remove("lock.txt")
            bflb_utils.local_log_save("log", self._input_macaddr)
            if self._bflb_com_if is not None:
                self._bflb_com_if.if_close()
            return bflb_utils.errorcode_msg(self._task_num)
        except Exception as e:
            bflb_utils.printf("efuse_flash_loader fail")
            #bflb_utils.printf(e)
            #traceback.print_exc(limit=NUM_ERR, file=sys.stdout)
            if self._csv_data and self._csv_file:
                lock_file = open("lock.txt", 'w+')
                portalocker.lock(lock_file, portalocker.LOCK_EX)
                with open(self._csv_file, 'r') as csvf:
                    reader = csv.DictReader(csvf)
                    list_csv = []
                    for row in reader:
                        if row.get('DeviceName', "") == self._csv_data:
                            if row.get('Burned', "") == 'P':
                                row['Burned'] = ''
                            else:
                                bflb_utils.printf(self._csv_data + " status not programing")
                        list_csv.append(row)
                    with open(self._csv_file, 'w', newline='') as f:
                        headers = [
                            'ProductKey', 'DeviceName', 'DeviceSecret', 'ProductSecret',
                            'ProductID', 'Burned'
                        ]
                        f_csv = csv.DictWriter(f, headers)
                        f_csv.writeheader()
                        f_csv.writerows(list_csv)
                lock_file.close()
                os.remove("lock.txt")
            bflb_utils.local_log_save("log", self._input_macaddr)
            if self._bflb_com_if is not None:
                self._bflb_com_if.if_close()
            return bflb_utils.errorcode_msg(self._task_num)

    def efuse_flash_loader2(self,
                            options,
                            eflash_loader_cfg,
                            eflash_loader_bin,
                            callback=None,
                            port=""):
        if port is not None and port:
            import socket
            bflb_utils.printf("Listen on Port: ", port)
            ip_port = ('127.0.0.1', int(port))
            server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            server.bind(ip_port)
            while True:
                data, client_addr = server.recvfrom(1024)
            server.close()
        else:
            self.efuse_flash_loader(options, eflash_loader_cfg, eflash_loader_bin, callback)

    def efuse_flash_loader_do(self,
                              args,
                              eflash_loader_cfg,
                              eflash_loader_bin,
                              callback=None,
                              update_cutoff_time=True,
                              create_simple_callback=None,
                              create_img_callback=None,
                              macaddr_callback=None,
                              task_num=None):
        bflb_utils.printf("========= eflash loader cmd arguments =========")
        bflb_utils.printf(eflash_loader_cfg)
        #         for key, value in args.__dict__.items():
        #             print(str(key) + ':' + str(value))
        config_file = None
        eflash_loader_file = None
        bootinfo = None
        try:
            start = ""
            end = ""
            packet_file = ""
            file = ""
            efusefile = ""
            massbin = ""
            fwbin = ""
            address = ""
            load_str = ""
            load_data = ""
            interface = ""
            port = ""
            load_speed = ""
            aeskey = ""
            chip_type = ""
            xtal_type = ""
            load_file = ""
            macaddr = ""
            romfs_data = ""
            csvfile = ""
            csvaddr = ""
            efuse_para = ""
            create_cfg = ""
            flash_set = 0
            read_flash_id = 0
            id_valid_flag = '80'
            read_flash2_id = 0
            id2_valid_flag = '80'
            efuse_load_func = 0
            if args.config and config_file is None:
                config_file = args.config
            if args.interface:
                interface = args.interface
            if args.port:
                port = args.port
            if args.baudrate:
                load_speed = args.baudrate
            if args.mass:
                massbin = args.mass
            if args.userarea:
                fwbin = args.userarea
            if args.start:
                start = args.start
            if args.end:
                end = args.end
            if args.packet:
                packet_file = args.packet
            if args.file:
                file = args.file
            if args.efusefile:
                efusefile = args.efusefile
            if args.efusecheck:
                efuse_load_func = 1
            else:
                efuse_load_func = 0
            if args.data:
                load_data = args.data
            if args.addr:
                address = args.addr
            if args.skip:
                skip_str = args.skip
                skip_para = skip_str.split(",")
                if skip_para[0][0:2] == "0x":
                    self._skip_addr = int(skip_para[0][2:], 16)
                else:
                    self._skip_addr = int(skip_para[0], 10)
                if skip_para[1][0:2] == "0x":
                    self._skip_len = int(skip_para[1][2:], 16)
                else:
                    self._skip_len = int(skip_para[1], 10)
            if args.key:
                aeskey = args.key
            if args.createcfg:
                create_cfg = args.createcfg
            if args.chipname:
                chip_type = gol.dict_chip_cmd[args.chipname]
            if args.xtal:
                xtal_type = args.xtal.replace('m', 'M').replace('rc', 'RC').replace('none', 'None')
            if args.loadstr:
                load_str = args.loadstr
            if args.loadfile:
                load_file = args.loadfile
            if args.mac:
                macaddr = args.mac
            if args.isp:
                self._isp_en = True
            else:
                self._isp_en = False
            if args.romfs:
                romfs_data = args.romfs
            if args.csvfile:
                csvfile = args.csvfile
            if args.csvaddr:
                csvaddr = args.csvaddr
            if args.auto:
                bflb_utils.printf("auto burn")
                self._bflb_auto_download = True
            else:
                self._bflb_auto_download = False
            if args.para:
                efuse_para = args.para
        except Exception as e:
            bflb_utils.printf(e)
            self.error_code_print("0002")
            return False, 0

        if packet_file != "":
            self.setOpenFile_zip(packet_file)
            return True, 0
        if chip_type:
            self._chip_type = chip_type
        if config_file is None:
            if self._chip_name:
                config_file = os.path.join(app_path, "chips", self._chip_name.lower(),
                                           "eflash_loader", "eflash_loader_cfg.ini")
            else:
                config_file = "eflash_loader_cfg.ini"
        if args.usage:
            self.usage()
        if args.version:
            if not conf_sign:
                bflb_utils.printf("Version: ", bflb_version.eflash_loader_version_text)
            return True, 0
        load_str = load_str.replace("*", "\n").replace("%", " ")
        # get interface
        if config_file is None and load_str is None and eflash_loader_cfg is None:
            return False, 0
        if not load_str:
            if eflash_loader_cfg is not None:
                config_file = eflash_loader_cfg
            else:
                config_file = os.path.abspath(config_file)
            if isinstance(config_file, BFConfigParser):
                cfg = config_file
            else:
                bflb_utils.printf("Config file: ", config_file)
                if os.path.exists(config_file):
                    cfg = BFConfigParser()
                    cfg.read(config_file)
                else:
                    bflb_utils.printf("Config file not found")
                    self.error_code_print("000B")
                    return False, 0
        else:
            cfg = BFConfigParser()
            bflb_utils.printf("Config str: ", load_str)
        if cfg.has_option("LOAD_CFG", "local_log"):
            if cfg.get("LOAD_CFG", "local_log") == "true":
                bflb_utils.printf("local log enable")
                bflb_utils.local_log_enable(True)
                self._input_macaddr = macaddr
            else:
                bflb_utils.local_log_enable(False)
                self._input_macaddr = ""
        # get interface and device
        if not interface:
            interface = cfg.get("LOAD_CFG", "interface")
        if not port:
            if interface == "openocd":
                self._bflb_com_device = cfg.get("LOAD_CFG", "openocd_config")
                self._bflb_sn_device = cfg.get("LOAD_CFG", "device")
            elif interface == "cklink":
                self._bflb_com_device = cfg.get("LOAD_CFG", "cklink_vidpid")
                self._bflb_sn_device = cfg.get("LOAD_CFG", "cklink_type") + " " + cfg.get(
                    "LOAD_CFG", "device")
            else:
                self._bflb_com_device = cfg.get("LOAD_CFG", "device")
        else:
            self._bflb_com_device = port
        bflb_utils.printf("serial port is ", self._bflb_com_device)
        verify = int(cfg.get("LOAD_CFG", "verify"))
        erase = int(cfg.get("LOAD_CFG", "erase"))
        if interface == "cklink":
            self._bflb_com_tx_size = 14344
        else:
            self._bflb_com_tx_size = int(cfg.get("LOAD_CFG", "tx_size"))
        do_reset = False
        reset_hold_time = 100
        shake_hand_delay = 100
        reset_revert = True
        cutoff_time = 0
        shake_hand_retry = 2
        flash_burn_retry = 1
        if cfg.has_option("LOAD_CFG", "erase_time_out"):
            self._erase_time_out = int(cfg.get("LOAD_CFG", "erase_time_out"))
        if cfg.has_option("LOAD_CFG", "shake_hand_retry"):
            shake_hand_retry = int(cfg.get("LOAD_CFG", "shake_hand_retry"))
        if cfg.has_option("LOAD_CFG", "flash_burn_retry"):
            flash_burn_retry = int(cfg.get("LOAD_CFG", "flash_burn_retry"))
        if cfg.has_option("LOAD_CFG", "checksum_err_retry"):
            self._checksum_err_retry_limit = int(cfg.get("LOAD_CFG", "checksum_err_retry"))
        if cfg.has_option("LOAD_CFG", "chiptype"):
            self._chip_type = cfg.get("LOAD_CFG", "chiptype")
        if cfg.has_option("LOAD_CFG", "cpu_reset_after_load"):
            self._cpu_reset = (cfg.get("LOAD_CFG", "cpu_reset_after_load") == "true")
        if cfg.has_option("LOAD_CFG", "retry_delay_after_cpu_reset"):
            self._retry_delay_after_cpu_reset = int(
                cfg.get("LOAD_CFG", "retry_delay_after_cpu_reset"))
            bflb_utils.printf("retry delay: ", self._retry_delay_after_cpu_reset)
        if cfg.has_option("LOAD_CFG", "eflash_loader_file") and eflash_loader_file is None:
            eflash_loader_file = cfg.get("LOAD_CFG", "eflash_loader_file")
        if cfg.has_option("LOAD_CFG", "skip_mode") and self._skip_len == 0:
            skip_para = cfg.get("LOAD_CFG", "skip_mode")
            if skip_para[0][0:2] == "0x":
                self._skip_addr = int(skip_para[0][2:], 16)
            else:
                self._skip_addr = int(skip_para[0], 10)
            if skip_para[1][0:2] == "0x":
                self._skip_len = int(skip_para[1][2:], 16)
            else:
                self._skip_len = int(skip_para[1], 10)
            if self._skip_len > 0:
                if erase == 2:
                    bflb_utils.printf("error: skip mode can not set flash chiperase!")
                    self.error_code_print("0044")
                    return False, 0
        if self._bflb_auto_download is False and cfg.has_option("LOAD_CFG", "auto_burn"):
            if "true" == cfg.get("LOAD_CFG", "auto_burn"):
                self._bflb_auto_download = True
            else:
                self._bflb_auto_download = False
        bflb_utils.printf("cpu_reset=", self._cpu_reset)
        if xtal_type != "":
            eflash_loader_file = "chips/" + self._chip_name.lower(
            ) + "/eflash_loader/eflash_loader_" + xtal_type.replace('.', 'p').lower() + ".bin"
        if load_file and not eflash_loader_file:
            eflash_loader_file = load_file
        if eflash_loader_bin is not None:
            eflash_loader_file = eflash_loader_bin
        elif eflash_loader_file is not None:
            eflash_loader_file = os.path.join(app_path, eflash_loader_file)
        bflb_utils.printf("chiptype: ", self._chip_type)
        if interface == "uart" or interface == "sdio":
            bflb_utils.printf("========= Interface is %s =========" % interface)
            self._bflb_com_img_loader = bflb_img_loader.BflbImgLoader(
                self._chip_type, self._chip_name, interface, create_cfg)
            self._bflb_com_if = self._bflb_com_img_loader.bflb_boot_if
            if load_speed:
                self._bflb_com_speed = load_speed
            else:
                self._bflb_com_speed = int(cfg.get("LOAD_CFG", "speed_uart_load"))
            bflb_utils.printf("com speed: ", self._bflb_com_speed)
            self._bflb_boot_speed = int(cfg.get("LOAD_CFG", "speed_uart_boot"))
            if self._isp_en is True and self._chip_type == "bl602":
                self._bflb_boot_speed = self._bflb_com_speed
            if cfg.has_option("LOAD_CFG", "reset_hold_time"):
                reset_hold_time = int(cfg.get("LOAD_CFG", "reset_hold_time"))
            if cfg.has_option("LOAD_CFG", "shake_hand_delay"):
                shake_hand_delay = int(cfg.get("LOAD_CFG", "shake_hand_delay"))
            if cfg.has_option("LOAD_CFG", "do_reset"):
                do_reset = (cfg.get("LOAD_CFG", "do_reset") == "true")
            if cfg.has_option("LOAD_CFG", "reset_revert"):
                reset_revert = (cfg.get("LOAD_CFG", "reset_revert") == "true")
            if update_cutoff_time and cfg.has_option("LOAD_CFG", "cutoff_time"):
                cutoff_time = int(cfg.get("LOAD_CFG", "cutoff_time"))
            if cfg.has_option("LOAD_CFG", "isp_mode_speed") and self._isp_en is True:
                isp_mode_speed = int(cfg.get("LOAD_CFG", "isp_mode_speed"))
                self._bflb_com_if.if_set_isp_baudrate(isp_mode_speed)
        elif interface == "jlink":
            bflb_utils.printf("========= Interface is JLink =========")
            self._bflb_com_if = bflb_interface_jlink.BflbJLinkPort()
            if load_speed:
                self._bflb_com_speed = load_speed // 1000
                bflb_utils.printf("com speed: %dk" % (self._bflb_com_speed))
            else:
                self._bflb_com_speed = int(cfg.get("LOAD_CFG", "speed_jlink"))
            self._bflb_boot_speed = self._bflb_com_speed
        elif interface == "openocd":
            bflb_utils.printf("========= Interface is Openocd =========")
            self._bflb_com_if = bflb_interface_openocd.BflbOpenocdPort()
            if load_speed:
                self._bflb_com_speed = load_speed // 1000
                bflb_utils.printf("com speed: %dk" % (self._bflb_com_speed))
            else:
                self._bflb_com_speed = int(cfg.get("LOAD_CFG", "speed_jlink"))
            self._bflb_boot_speed = self._bflb_com_speed
        elif interface == "cklink":
            bflb_utils.printf("========= Interface is CKLink =========")
            self._bflb_com_if = bflb_interface_cklink.BflbCKLinkPort()
            if load_speed:
                self._bflb_com_speed = load_speed // 1000
                bflb_utils.printf("com speed: %dk" % (self._bflb_com_speed))
            else:
                self._bflb_com_speed = int(cfg.get("LOAD_CFG", "speed_jlink"))
            self._bflb_boot_speed = self._bflb_com_speed
        else:
            bflb_utils.printf(interface + " is not supported ")
            return False, flash_burn_retry
        self._need_shake_hand = True
        ram_load = False
        load_function = 1
        if args.ram and args.file:
            ram_load = True
            eflash_loader_file = file

        try:
            if args.chipid:
                ret, bootinfo, res = self.get_boot_info(interface, eflash_loader_file, do_reset,
                                                        reset_hold_time, shake_hand_delay,
                                                        reset_revert, cutoff_time,
                                                        shake_hand_retry)
                if ret is False:
                    self.error_code_print("0003")
                    return False, flash_burn_retry
                else:
                    return True, flash_burn_retry

            if cfg.has_option("LOAD_CFG", "load_function"):
                load_function = int(cfg.get("LOAD_CFG", "load_function"))
            if cfg.has_option("LOAD_CFG", "isp_shakehand_timeout"):
                self._isp_shakehand_timeout = int(cfg.get("LOAD_CFG", "isp_shakehand_timeout"))
            if self._isp_en is True:
                if self._isp_shakehand_timeout == 0:
                    self._isp_shakehand_timeout = 5
                if self._chip_type == "bl702":
                    load_function = 0
                elif self._chip_type == "bl602":
                    load_function = 1
                else:
                    load_function = 2
            if ram_load:
                load_function = 1
            if load_function == 0:
                bflb_utils.printf("No need load eflash_loader.bin")
            elif load_function == 1:
                load_bin_pass = False
                bflb_utils.printf("Eflash load helper file: ", eflash_loader_file)
                ret, bootinfo, res = self.load_helper_bin(interface, eflash_loader_file, do_reset,
                                                          reset_hold_time, shake_hand_delay,
                                                          reset_revert, cutoff_time,
                                                          shake_hand_retry,
                                                          self._isp_shakehand_timeout)
                if res == "shake hand fail":
                    self.error_code_print("0050")
                if res.startswith("repeat_burn") is True:
                    #self.error_code_print("000A")
                    return "repeat_burn", flash_burn_retry
                if res.startswith("error_shakehand") is True:
                    if self._cpu_reset is True:
                        self.error_code_print("0003")
                        return False, flash_burn_retry
                    else:
                        load_bin_pass = True
                        time.sleep(4.5)
                if ret is False and load_bin_pass == False:
                    self.error_code_print("0003")
                    return False, flash_burn_retry
                if ram_load:
                    return True, flash_burn_retry
            elif load_function == 2:
                load_bin_pass = False
                bflb_utils.printf("Bootrom load")
                ret, bootinfo, res = self.get_boot_info(interface, eflash_loader_file, do_reset,
                                                        reset_hold_time, shake_hand_delay,
                                                        reset_revert, cutoff_time,
                                                        shake_hand_retry,
                                                        self._isp_shakehand_timeout)
                if res == "shake hand fail":
                    self.error_code_print("0050")
                if res.startswith("repeat_burn") is True:
                    #self.error_code_print("000A")
                    return "repeat_burn", flash_burn_retry
                if res.startswith("error_shakehand") is True:
                    if self._cpu_reset is True:
                        self.error_code_print("0003")
                        return False, flash_burn_retry
                    else:
                        load_bin_pass = True
                        time.sleep(4.5)
                if ret is False and load_bin_pass == False:
                    self.error_code_print("0050")
                    return False, flash_burn_retry
                self._need_shake_hand = False
                clock_para = bytearray(0)
                if cfg.has_option("LOAD_CFG", "clock_para"):
                    clock_para_str = cfg.get("LOAD_CFG", "clock_para")
                    if clock_para_str != "":
                        clock_para_file = os.path.join(app_path, clock_para_str)
                        bflb_utils.printf("clock para file: ", clock_para_file)
                        clock_para = self.clock_para_update(os.path.join(
                            app_path, clock_para_file))
                bflb_utils.printf("change bdrate: ", self._bflb_com_speed)
                ret = self.clock_pll_set(self._need_shake_hand, True, self._bflb_com_speed,
                                         clock_para)
                if ret is False:
                    bflb_utils.printf("pll set fail!!")
                    return False, flash_burn_retry
        except Exception as e:
            bflb_utils.printf(e)
            self.error_code_print("0003")
            return False, flash_burn_retry
        time.sleep(0.1)

        if self._isp_en is True and self._cpu_reset is True:
            if self._chip_type == "bl808" or \
               self._chip_type == "bl628" or \
               self._chip_type == "bl616" or \
               self._chip_type == "wb03":
                # clear boot status for boot from media after isp mode
                self.clear_boot_status(self._need_shake_hand)

        macaddr_check = False
        mac_addr = bytearray(0)
        if cfg.has_option("LOAD_CFG", "check_mac"):
            macaddr_check = (cfg.get("LOAD_CFG", "check_mac") == "true")
        if macaddr_check and self._isp_en is False:
            # check mac addr
            ret, mac_addr = self.efuse_read_mac_addr_process(self._need_shake_hand)
            if ret is False:
                bflb_utils.printf("read mac addr fail!!")
                return False, flash_burn_retry
            if mac_addr == self._macaddr_check:
                self.error_code_print("000A")
                return False, flash_burn_retry
            self._need_shake_hand = False
            self._macaddr_check_status = True

        # for mass_production tool
        if macaddr_callback is not None:
            ret, self._efuse_data, self._efuse_mask_data, macaddr = macaddr_callback(
                binascii.hexlify(mac_addr).decode('utf-8'))
            if ret is False:
                return False, flash_burn_retry
            if (self._efuse_data != bytearray(0) and
                    self._efuse_mask_data != bytearray(0)) or macaddr != "":
                args.efuse = True
        if callback:
            callback(0, 100, "进行", "blue")

        if args.flash:
            # set flash parameter
            flash_pin = 0
            flash_clock_cfg = 0
            flash_io_mode = 0
            flash_clk_delay = 0
            if cfg.has_option("FLASH_CFG", "decompress_write"):
                self._decompress_write = (cfg.get("FLASH_CFG", "decompress_write") == "true")
            if self._chip_type == "bl60x" or self._chip_type == "bl702":
                self._decompress_write = False
            bflb_utils.printf("flash set para")
            if cfg.get("FLASH_CFG", "flash_pin"):
                flash_pin_cfg = cfg.get("FLASH_CFG", "flash_pin")
                if flash_pin_cfg.startswith("0x"):
                    flash_pin = int(flash_pin_cfg, 16)
                else:
                    flash_pin = int(flash_pin_cfg, 10)
            else:
                if self._chip_type == "bl602" or self._chip_type == "bl702":
                    flash_pin = 0xff
            if self._chip_type != "bl60x":
                if cfg.has_option("FLASH_CFG", "flash_clock_cfg"):
                    clock_div_cfg = cfg.get("FLASH_CFG", "flash_clock_cfg")
                    if clock_div_cfg.startswith("0x"):
                        flash_clock_cfg = int(clock_div_cfg, 16)
                    else:
                        flash_clock_cfg = int(clock_div_cfg, 10)
                if cfg.has_option("FLASH_CFG", "flash_io_mode"):
                    io_mode_cfg = cfg.get("FLASH_CFG", "flash_io_mode")
                    if io_mode_cfg.startswith("0x"):
                        flash_io_mode = int(io_mode_cfg, 16)
                    else:
                        flash_io_mode = int(io_mode_cfg, 10)
                if cfg.has_option("FLASH_CFG", "flash_clock_delay"):
                    clk_delay_cfg = cfg.get("FLASH_CFG", "flash_clock_delay")
                    if clk_delay_cfg.startswith("0x"):
                        flash_clk_delay = int(clk_delay_cfg, 16)
                    else:
                        flash_clk_delay = int(clk_delay_cfg, 10)
            # 0x0101ff is default set: flash_io_mode=1, flash_clock_cfg=1, flash_pin=0xff
            flash_set = (flash_pin << 0) +\
                        (flash_clock_cfg << 8) +\
                        (flash_io_mode << 16) +\
                        (flash_clk_delay << 24)
            if (flash_set != 0x0101ff and self._chip_type != "bl60x")\
                or (flash_pin != 0 and self._chip_type == "bl60x")\
                or load_function == 2:
                bflb_utils.printf("set flash cfg: %X" % (flash_set))
                ret = self.flash_set_para_main_process(flash_set, bytearray(0),
                                                       self._need_shake_hand)
                self._need_shake_hand = False
                if ret is False:
                    return False, flash_burn_retry
            # recreate bootinfo.bin
            ret, data = self.flash_read_jedec_id_process(self._need_shake_hand)
            if ret:
                self._need_shake_hand = False
                data = binascii.hexlify(data).decode('utf-8')
                id_valid_flag = data[6:]
                read_id = data[0:6]
                read_flash_id = read_id
                if cfg.has_option("FLASH_CFG", "flash_para"):
                    flash_para_file = os.path.join(app_path, cfg.get("FLASH_CFG", "flash_para"))
                    self.flash_para_update(flash_para_file, read_id)
                if id_valid_flag != '80':
                    if self._chip_type == "bl602" or self._chip_type == "bl702":
                        bflb_utils.printf("eflash loader identify flash fail!")
                        self.error_code_print("0043")
                        return False, flash_burn_retry
                if self.is_conf_exist(read_flash_id) is False:
                    self.error_code_print("003D")
                    return False, flash_burn_retry
            else:
                self.error_code_print("0030")
                return False, flash_burn_retry
            # flash2 init
            if self._chip_type == "bl616" or self._chip_type == "wb03":
                if cfg.has_option("FLASH2_CFG", "flash2_en"):
                    self._flash2_en = (cfg.get("FLASH2_CFG", "flash2_en") == "true")
                    if self._flash2_en is True:
                        self._flash1_size = (int(cfg.get("FLASH2_CFG", "flash1_size")) * 1024 *
                                             1024)
                        self._flash2_size = (int(cfg.get("FLASH2_CFG", "flash2_size")) * 1024 *
                                             1024)
                        bflb_utils.printf("flash2 set para")
                        flash2_pin = 0
                        flash2_clock_cfg = 0
                        flash2_io_mode = 0
                        flash2_clk_delay = 0
                        if cfg.get("FLASH2_CFG", "flash2_pin"):
                            flash_pin_cfg = cfg.get("FLASH2_CFG", "flash2_pin")
                            if flash_pin_cfg.startswith("0x"):
                                flash2_pin = int(flash_pin_cfg, 16)
                            else:
                                flash2_pin = int(flash_pin_cfg, 10)
                        if cfg.has_option("FLASH2_CFG", "flash2_clock_cfg"):
                            clock_div_cfg = cfg.get("FLASH2_CFG", "flash2_clock_cfg")
                            if clock_div_cfg.startswith("0x"):
                                flash2_clock_cfg = int(clock_div_cfg, 16)
                            else:
                                flash2_clock_cfg = int(clock_div_cfg, 10)
                        if cfg.has_option("FLASH2_CFG", "flash2_io_mode"):
                            io_mode_cfg = cfg.get("FLASH2_CFG", "flash2_io_mode")
                            if io_mode_cfg.startswith("0x"):
                                flash2_io_mode = int(io_mode_cfg, 16)
                            else:
                                flash2_io_mode = int(io_mode_cfg, 10)
                        if cfg.has_option("FLASH2_CFG", "flash2_clock_delay"):
                            clk_delay_cfg = cfg.get("FLASH2_CFG", "flash2_clock_delay")
                            if clk_delay_cfg.startswith("0x"):
                                flash2_clk_delay = int(clk_delay_cfg, 16)
                            else:
                                flash2_clk_delay = int(clk_delay_cfg, 10)
                        flash2_set = (flash2_pin << 0) +\
                                     (flash2_clock_cfg << 8) +\
                                     (flash2_io_mode << 16) +\
                                     (flash2_clk_delay << 24)
                        if load_function == 2:
                            bflb_utils.printf("set flash2 cfg: %X" % (flash2_set))
                            ret = self.flash_set_para_main_process(flash2_set, bytearray(0),
                                                                   self._need_shake_hand)
                            self._need_shake_hand = False
                            if ret is False:
                                return False, flash_burn_retry
                        # switch to flash2 ctrl
                        ret = self.flash_switch_bank_process(1, self._need_shake_hand)
                        self._need_shake_hand = False
                        if ret is False:
                            return False, flash_burn_retry
                        # recreate bootinfo.bin
                        ret, data = self.flash_read_jedec_id_process(self._need_shake_hand)
                        if ret:
                            self._need_shake_hand = False
                            data = binascii.hexlify(data).decode('utf-8')
                            id2_valid_flag = data[6:]
                            read_id2 = data[0:6]
                            read_flash2_id = read_id2
                            if cfg.has_option("FLASH2_CFG", "flash2_para"):
                                flash2_para_file = os.path.join(
                                    app_path, cfg.get("FLASH2_CFG", "flash2_para"))
                                self.flash_para_update(flash2_para_file, read_id2)

                                # flash2 set flash para iomode=0x11
                                fp = open_file(flash2_para_file, 'rb')
                                para_data = bytearray(fp.read())
                                fp.close()
                                para_data[0:1] = b'\x11'
                                fp = open_file(flash2_para_file, 'wb+')
                                fp.write(para_data)
                                fp.close()
                        else:
                            self.error_code_print("0030")
                            return False, flash_burn_retry
                        # switch to default flash1 ctrl
                        ret = self.flash_switch_bank_process(0, self._need_shake_hand)
                        self._need_shake_hand = False
                        if ret is False:
                            return False, flash_burn_retry

        # '--none' for eflash loader environment init
        if args.none:
            return True, flash_burn_retry

        # erase
        if args.erase:
            bflb_utils.printf("Erase flash operation")
            if end == "0":
                erase = 0
                ret = self.flash_chiperase_main_process(self._need_shake_hand)
                if ret is False:
                    return False, flash_burn_retry
            else:
                erase = 1
                ret = self.flash_erase_main_process(int(start, 16), int(end, 16),
                                                    self._need_shake_hand)
                if ret is False:
                    return False, flash_burn_retry
            bflb_utils.printf("Erase flash OK")
        # write
        if args.write:
            if not args.flash and not args.efuse:
                bflb_utils.printf("No target select")
                return False, flash_burn_retry
            bflb_utils.printf("Program operation")
            # get program type
            if args.flash:
                flash_para_file = ""
                flash2_para_file = ""
                if cfg.has_option("FLASH_CFG", "flash_para"):
                    flash_para_file = os.path.join(app_path, cfg.get("FLASH_CFG", "flash_para"))
                if cfg.has_option("FLASH2_CFG", "flash2_para"):
                    flash2_para_file = os.path.join(app_path, cfg.get("FLASH2_CFG", "flash2_para"))
                if romfs_data != "":
                    if address == "":
                        bflb_utils.printf("Please set romfs load address")
                        self.error_code_print("0041")
                        return False, flash_burn_retry
                    bflb_utils.printf("load romfs ", romfs_data)
                    ret = self.load_romfs_data(romfs_data, int(address, 16), verify,
                                               self._need_shake_hand, callback)
                    if ret is False:
                        self.error_code_print("0041")
                        return False, flash_burn_retry
                    self._need_shake_hand = False
                    bflb_utils.printf("Program romfs Finished")
                elif fwbin:
                    bflb_utils.printf("load firmware bin ", fwbin)
                    fwbin = os.path.abspath(fwbin)
                    ret = self.flash_cfg_option(read_flash_id, flash_para_file, flash_set, id_valid_flag, fwbin, \
                                                config_file, cfg, create_img_callback, create_simple_callback)
                    if ret is False:
                        return False, flash_burn_retry
                    ret = self.load_firmware_bin(fwbin, verify, self._need_shake_hand, callback)
                    if ret is False:
                        self.error_code_print("003C")
                        return False, flash_burn_retry
                    self._need_shake_hand = False
                    bflb_utils.printf("Program fwbin Finished")
                elif massbin:
                    bflb_utils.printf("load mass bin ", massbin)
                    bflb_utils.printf("========= programming mass ", massbin, " to ", hex(0))
                    massbin = os.path.abspath(massbin)
                    ret = self.flash_cfg_option(read_flash_id, flash_para_file, flash_set, id_valid_flag, massbin, \
                                                config_file, cfg, create_img_callback, create_simple_callback)
                    if ret is False:
                        return False, flash_burn_retry
                    ret = self.flash_load_specified(massbin, 0x0, 1, verify, self._need_shake_hand,
                                                    callback)
                    if ret is False:
                        return False, flash_burn_retry
                    self._need_shake_hand = False
                    bflb_utils.printf("Program massbin Finished")
                else:
                    if file:
                        flash_file = file.split(",")
                        address = address.split(",")
                        erase = 1
                    else:
                        flash_file = re.compile('\s+').split(cfg.get("FLASH_CFG", "file"))
                        address = re.compile('\s+').split(cfg.get("FLASH_CFG", "address"))
                    if csvfile and csvaddr:
                        bflb_utils.printf("factory info burn")
                        csvbin = "chips/" + self._chip_name.lower() + "/img_create_iot/media.bin"
                        ret, csv_mac = self.get_factory_config_info(csvfile, csvbin)
                        if ret is not False:
                            flash_file.append(csvbin)
                            address.append(csvaddr)
                            if csv_mac:
                                macaddr = csv_mac
                                args.efuse = True
                        else:
                            bflb_utils.printf("create media.bin fail")
                            return False, flash_burn_retry
                    # do chip erase first
                    if erase == 2:
                        ret = self.flash_chiperase_main_process(self._need_shake_hand)
                        if ret is False:
                            return False, flash_burn_retry
                        self._need_shake_hand = False
                        erase = 0
                    # program flash
                    if len(flash_file) > 0:
                        size_before = 0
                        size_all = 0
                        i = 0
                        for item in flash_file:
                            if task_num != None and self._csv_burn_en is True:
                                size_all += os.path.getsize(
                                    os.path.join(app_path,
                                                 convert_path("task" + str(task_num) + "/" +
                                                              item)))
                            else:
                                size_all += os.path.getsize(
                                    os.path.join(app_path, convert_path(item)))
                        try:
                            ret = False
                            while i < len(flash_file):
                                if task_num != None and self._csv_burn_en is True:
                                    flash_file[i] = "task" + str(task_num) + "/" + flash_file[i]
                                    size_current = os.path.getsize(
                                        os.path.join(app_path, convert_path(flash_file[i])))
                                else:
                                    size_current = os.path.getsize(
                                        os.path.join(app_path, convert_path(flash_file[i])))
                                if callback:
                                    callback(size_before, size_all, "program1")
                                if callback:
                                    callback(size_current, size_all, "program2")
                                #if task_num != None and self._csv_burn_en is True:
                                #     flash_file[i] = "task" + str(task_num) + "/" + flash_file[i]
                                bflb_utils.printf("Dealing Index ", i)
                                if self._isp_en is True:
                                    bflb_utils.printf("========= programming ",
                                                      convert_path(flash_file[i]))
                                else:
                                    bflb_utils.printf("========= programming ",
                                                      convert_path(flash_file[i]),
                                                      " to 0x%08X" % (int(address[i], 16)))
                                flash1_bin = ""
                                flash1_bin_len = 0
                                flash2_bin = ""
                                flash2_bin_len = 0
                                if self._chip_type == "bl616" or self._chip_type == "wb03":
                                    if self._flash1_size != 0 and self._flash1_size < int(address[i], 16) + size_current and \
                                       self._flash1_size > int(address[i], 16) and self._flash2_select is False:
                                        bflb_utils.printf("%s file is overflow with flash1" %
                                                          flash_file[i])
                                        flash1_bin, flash1_bin_len, flash2_bin, flash2_bin_len = \
                                            self.flash_loader_cut_flash_bin(flash_file[i], int(address[i], 16), self._flash1_size)
                                if flash1_bin != "" and flash2_bin != "":
                                    ret = self.flash_cfg_option(read_flash_id, flash_para_file, flash_set, id_valid_flag, flash1_bin, \
                                                                config_file, cfg, create_img_callback, create_simple_callback)
                                    if ret is False:
                                        return False, flash_burn_retry
                                    bflb_utils.printf("========= programming ",
                                                      convert_path(flash1_bin),
                                                      " to 0x%08X" % (int(address[i], 16)))
                                    ret = self.flash_load_specified(convert_path(flash1_bin),
                                                                    int(address[i], 16), erase,
                                                                    verify, self._need_shake_hand,
                                                                    callback)
                                    if ret is False:
                                        return False, flash_burn_retry
                                    ret = self.flash_switch_bank_process(1, self._need_shake_hand)
                                    self._need_shake_hand = False
                                    if ret is False:
                                        return False, flash_burn_retry
                                    ret = self.flash_cfg_option(read_flash2_id, flash2_para_file, flash2_set, id2_valid_flag, flash_file[i], \
                                                                config_file, cfg, create_img_callback, create_simple_callback)
                                    if ret is False:
                                        return False, flash_burn_retry
                                    bflb_utils.printf(
                                        "========= programming ", convert_path(flash2_bin),
                                        " to 0x%08X" % (int(address[i], 16) + flash1_bin_len))
                                    ret = self.flash_load_specified(
                                        convert_path(flash2_bin),
                                        int(address[i], 16) + flash1_bin_len, erase, verify,
                                        self._need_shake_hand, callback)
                                    if ret is False:
                                        return False, flash_burn_retry
                                else:
                                    if self._flash2_en is False or (
                                            self._flash2_select is False and
                                            int(address[i], 16) < self._flash1_size):
                                        ret = self.flash_cfg_option(read_flash_id, flash_para_file, flash_set, id_valid_flag, flash_file[i], \
                                                                    config_file, cfg, create_img_callback, create_simple_callback)
                                        if ret is False:
                                            return False, flash_burn_retry
                                    else:
                                        if self._flash2_select is False and int(
                                                address[i], 16) >= self._flash1_size:
                                            ret = self.flash_switch_bank_process(
                                                1, self._need_shake_hand)
                                            self._need_shake_hand = False
                                            if ret is False:
                                                return False, flash_burn_retry
                                        ret = self.flash_cfg_option(read_flash2_id, flash2_para_file, flash2_set, id2_valid_flag, flash_file[i], \
                                                                    config_file, cfg, create_img_callback, create_simple_callback)
                                        if ret is False:
                                            return False, flash_burn_retry
                                    ret = self.flash_load_specified(convert_path(flash_file[i]),
                                                                    int(address[i], 16), erase,
                                                                    verify, self._need_shake_hand,
                                                                    callback)
                                    if ret is False:
                                        return False, flash_burn_retry
                                size_before += os.path.getsize(
                                    os.path.join(app_path, convert_path(flash_file[i])))
                                i += 1
                                if callback:
                                    callback(i, len(flash_file), "program")
                                self._need_shake_hand = False
                            if self._flash2_select is True:
                                ret = self.flash_switch_bank_process(0, self._need_shake_hand)
                                self._need_shake_hand = False
                                if ret is False:
                                    return False, flash_burn_retry
                            bflb_utils.printf("Program Finished")
                        except Exception as e:
                            bflb_utils.printf(e)
                            traceback.print_exc(limit=NUM_ERR, file=sys.stdout)
                            return False, flash_burn_retry
                    else:
                        bflb_utils.printf("No input file to program to flash")
            # get program type
            if args.efuse:
                loadflag = True
                if macaddr:
                    # loadflag = False
                    bflb_utils.printf("write efuse macaddr ", macaddr)
                    security_write = (cfg.get("EFUSE_CFG", "security_write") == "true")
                    if self._chip_type == "bl702" or self._chip_type == "bl702l":
                        ret = self.efuse_load_702_macaddr(macaddr,
                                                          verify=1,
                                                          shakehand=self._need_shake_hand,
                                                          security_write=security_write)
                    else:
                        ret = self.efuse_load_macaddr(macaddr,
                                                      verify=1,
                                                      shakehand=self._need_shake_hand,
                                                      security_write=security_write)
                    if ret is False:
                        bflb_utils.printf("load macaddr fail")
                        return False, flash_burn_retry
                    self._need_shake_hand = False
                if aeskey:
                    loadflag = False
                    bflb_utils.printf("write efuse aes key ", aeskey)
                    ret = self.efuse_load_aes_key("flash_aes_key", [aeskey, ""],
                                                  verify=1,
                                                  shakehand=self._need_shake_hand)
                    if ret is False:
                        bflb_utils.printf("load aes key fail")
                        return False, flash_burn_retry
                if load_data and address:
                    loadflag = False
                    bflb_utils.printf("write efuse data ", load_data, " to ", address)
                    security_write = (cfg.get("EFUSE_CFG", "security_write") == "true")
                    ret = self.efuse_load_data_process(load_data, address, efuse_load_func, verify,
                                                       self._need_shake_hand, security_write)
                    if ret is False:
                        bflb_utils.printf("write efuse data fail")
                        return False, flash_burn_retry
                if efuse_para:
                    loadflag = False
                    bflb_utils.printf("write efuse para")
                    cfgfile = "chips/" + self._chip_name.lower(
                    ) + "/img_create_iot/efuse_bootheader_cfg.ini"
                    if os.path.isfile(cfgfile) is False:
                        shutil.copyfile(
                            "chips/" + self._chip_name.lower() +
                            "/efuse_bootheader/efuse_bootheader_cfg.conf", cfgfile)
                    sub_module = __import__("libs." + self._chip_type, fromlist=[self._chip_type])
                    efuse_data, mask = bflb_efuse_boothd_create.update_data_from_cfg(
                        sub_module.efuse_cfg_keys.efuse_cfg_keys, cfgfile, "EFUSE_CFG")
                    efuse_load = True
                    efuse_verify = 1
                    if cfg.has_option("EFUSE_CFG", "burn_en"):
                        efuse_load = (cfg.get("EFUSE_CFG", "burn_en") == "true")
                    if cfg.has_option("EFUSE_CFG", "factory_mode"):
                        if cfg.get("EFUSE_CFG", "factory_mode") != "true":
                            efuse_verify = 0
                    security_write = (cfg.get("EFUSE_CFG", "security_write") == "true")
                    if efuse_load:
                        ret = self.efuse_load_specified(None, None, efuse_data, mask, efuse_verify,
                                                        self._need_shake_hand, security_write)
                        if callback:
                            callback(1, 1, "APP_WR")
                        if ret is False:
                            return False, flash_burn_retry
                    else:
                        bflb_utils.printf("efuse load disalbe")
                if loadflag is True:
                    if efusefile:
                        efuse_file = efusefile
                        mask_file = efuse_file.replace(".bin", "_mask.bin")
                    else:
                        efuse_file = cfg.get("EFUSE_CFG", "file")
                        mask_file = cfg.get("EFUSE_CFG", "maskfile")
                    if task_num != None and self._csv_burn_en is True:
                        efuse_file = "task" + str(task_num) + "/" + efuse_file
                    efuse_load = True
                    efuse_verify = 1
                    if cfg.has_option("EFUSE_CFG", "burn_en"):
                        efuse_load = (cfg.get("EFUSE_CFG", "burn_en") == "true")
                    if cfg.has_option("EFUSE_CFG", "factory_mode"):
                        if cfg.get("EFUSE_CFG", "factory_mode") != "true":
                            efuse_verify = 0
                    security_write = (cfg.get("EFUSE_CFG", "security_write") == "true")
                    if efuse_load and self._isp_en is False:
                        ret = self.efuse_load_specified(efuse_file, mask_file, bytearray(0),
                                                        bytearray(0), efuse_verify,
                                                        self._need_shake_hand, security_write)
                        if callback:
                            callback(1, 1, "APP_WR")
                        if ret is False:
                            return False, flash_burn_retry
                    else:
                        bflb_utils.printf("efuse load disalbe")
                self._need_shake_hand = False
        # read
        if args.read:
            bflb_utils.printf("Read operation")
            if not args.flash and not args.efuse:
                bflb_utils.printf("No target select")
                return False, flash_burn_retry
            if args.flash:
                if not start or not end:
                    self.flash_read_jedec_id_process(callback)
                else:
                    start_addr = int(start, 16)
                    end_addr = int(end, 16)
                    ret, readdata = self.flash_read_main_process(start_addr,
                                                                 end_addr - start_addr + 1,
                                                                 self._need_shake_hand, file,
                                                                 callback)
                    if ret is False:
                        return False, flash_burn_retry
            if args.efuse:
                start_addr = int(start, 16)
                end_addr = int(end, 16)
                if self.efuse_read_main_process(start_addr, end_addr - start_addr + 1,
                                                self._need_shake_hand, file) is False:
                    return False, flash_burn_retry
        if self._isp_en is True and (self._chip_type == "bl702" or self._chip_type == "bl702l"):
            self.reset_cpu()
        if macaddr_check is True:
            self._bootinfo = bootinfo
        self._macaddr_check = mac_addr
        self._macaddr_check_status = False
        return True, flash_burn_retry

    def usage(self):
        bflb_utils.printf("-e --start=00000000 --end=0000FFFF -c config.ini")
        bflb_utils.printf("-w --flash -c config.ini")
        bflb_utils.printf("-w --flash --file=1.bin,2.bin --addr=00000000,00001000 -c config.ini")
        bflb_utils.printf(
            "-r --flash --start=00000000 --end=0000FFFF --file=flash.bin -c config.ini")


def run():
    log_file = os.path.join(app_path, "log")
    if not os.path.exists(log_file):
        os.makedirs(log_file)

    parser = eflash_loader_parser_init()
    args = parser.parse_args()
    # args = parser.parse_args(["--chipname=bl602", "--write", "--flash", "--baudrate=2000000", "--config=eflash_loader_cfg.ini"])
    bflb_utils.printf("Chipname: %s" % args.chipname)
    eflash_loader_obj = BflbEflashLoader(args.chipname, gol.dict_chip_cmd[args.chipname])
    gol.chip_name = args.chipname
    if conf_sign:
        reload(cgc)
    while True:
        try:
            ret = eflash_loader_obj.efuse_flash_loader(args, None, None)
            if ret is not True:
                eflash_loader_obj.error_code_print("0005")
            eflash_loader_obj.close_port()
            time.sleep(2)
        except Exception as e:
            bflb_utils.printf(e)
        time.sleep(0.2)
        if not args.auto:
            break


if __name__ == '__main__':
    run()
