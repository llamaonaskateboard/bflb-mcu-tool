# -*- coding:utf-8 -*-

import re
import os
import sys
import time
import shutil
import argparse
import traceback
from importlib import reload
from os.path import expanduser
import logging
from logging.handlers import TimedRotatingFileHandler

try:
    import bflb_path
except ImportError:
    from libs import bflb_path

import config as gol
from libs import bflb_eflash_loader
from libs import bflb_efuse_boothd_create
from libs import bflb_img_create
from libs import bflb_img_loader
from libs import bflb_flash_select
from libs import bflb_utils
from libs.bflb_utils import verify_hex_num, get_eflash_loader, get_serial_ports, convert_path
from libs.bflb_configobj import BFConfigParser
import libs.bflb_ro_params_device_tree as bl_ro_device_tree

parser_eflash = bflb_utils.eflash_loader_parser_init()
parser_image = bflb_utils.image_create_parser_init()

# Get app path
if getattr(sys, "frozen", False):
    app_path = os.path.dirname(sys.executable)
else:
    app_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(app_path)
chip_path = os.path.join(app_path, "chips")

try:
    import changeconf as cgc
    conf_sign = True
except ImportError:
    conf_sign = False


def parse_rfpa(bin):
    with open(bin, "rb") as fp:
        content = fp.read()
        return content[1024:1032]


def record_log():
    log_file = os.path.join(app_path, "log")
    if not os.path.exists(log_file):
        os.makedirs(log_file)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    # create a handler, write the log info into it
    now_log_file = os.path.join(
        log_file, "{0}_{1}.log".format('flashcube', time.strftime("%Y%m%d", time.localtime())))
    # 用于写入日志文件
    fh = TimedRotatingFileHandler(now_log_file,
                                  when='D',
                                  interval=1,
                                  backupCount=0,
                                  encoding='utf-8',
                                  delay=False,
                                  utc=False)
    # 用于将日志输出到控制台
    ch = logging.StreamHandler()
    fh.setLevel(logging.DEBUG)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    # add handler to logger
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


class RedirectText:

    def __init__(self, logger):
        self.logger = logger

    def write(self, string):
        content = string.strip().splitlines(keepends=True)
        for item in content:
            if item.strip():
                self.logger.info(item.strip())

    def flush(self):
        pass


class BflbMcuTool(object):

    def __init__(self, chipname="bl60x", chiptype="bl60x"):
        self.chiptype = chiptype
        self.chipname = chipname
        self.config = {}
        self.efuse_load_en = False
        self.eflash_loader_cfg = os.path.join(chip_path, chipname,
                                              "eflash_loader/eflash_loader_cfg.conf")
        self.eflash_loader_cfg_tmp = os.path.join(chip_path, chipname,
                                                  "eflash_loader/eflash_loader_cfg.ini")
        self.eflash_loader_bin = os.path.join(chip_path, chipname,
                                              "eflash_loader/eflash_loader_40m.bin")
        self.img_create_path = os.path.join(chip_path, chipname, "img_create_mcu")
        self.efuse_bh_path = os.path.join(chip_path, chipname, "efuse_bootheader")
        self.efuse_bh_default_cfg = os.path.join(chip_path, chipname,
                                                 "efuse_bootheader") + "/efuse_bootheader_cfg.conf"
        self.efuse_bh_default_cfg_dp = os.path.join(
            chip_path, chipname, "efuse_bootheader") + "/efuse_bootheader_cfg_dp.conf"
        self.img_create_cfg_org = os.path.join(chip_path, chipname,
                                               "img_create_mcu") + "/img_create_cfg.conf"
        self.img_create_cfg_dp_org = os.path.join(chip_path, chipname,
                                                  "img_create_mcu") + "/img_create_cfg_dp.conf"
        self.img_create_cfg = os.path.join(chip_path, chipname,
                                           "img_create_mcu") + "/img_create_cfg.ini"
        if not os.path.exists(self.img_create_path):
            os.makedirs(self.img_create_path)
        if os.path.isfile(self.eflash_loader_cfg_tmp) is False:
            shutil.copyfile(self.eflash_loader_cfg, self.eflash_loader_cfg_tmp)
        if os.path.isfile(self.img_create_cfg) is False:
            shutil.copyfile(self.img_create_cfg_org, self.img_create_cfg)

        self.xtal_type = gol.xtal_type[chiptype]
        self.xtal_type_ = gol.xtal_type_[chiptype]
        self.pll_clk = gol.pll_clk[chiptype]
        self.encrypt_type = gol.encrypt_type[chiptype]
        self.key_sel = gol.key_sel[chiptype]
        self.sign_type = gol.sign_type[chiptype]
        self.cache_way_disable = gol.cache_way_disable[chiptype]
        self.flash_clk_type = gol.flash_clk_type[chiptype]
        self.crc_ignore = gol.crc_ignore[chiptype]
        self.hash_ignore = gol.hash_ignore[chiptype]
        self.img_type = gol.img_type[chiptype]
        self.boot_src = gol.boot_src[chiptype]
        self.eflash_loader_t = bflb_eflash_loader.BflbEflashLoader(chipname, chiptype)

    def bl_create_flash_default_data(self, length):
        datas = bytearray(length)
        for i in range(length):
            datas[i] = 0xff
        return datas

    def bl_get_file_data(self, files):
        datas = []
        for file in files:
            with open(os.path.join(app_path, file), 'rb') as fp:
                data = fp.read()
            datas.append(data)
        return datas

    def bflb_set_file_ff(self, file):
        fp = open(file, 'rb')
        data = bytearray(fp.read()) + bytearray(0)
        fp.close()
        length = len(data)
        for i in range(16):
            data[i] = 0xff
        fp = open(file, 'wb+')
        fp.write(data)
        fp.close()

    def img_addr_remap(self, addr):
        remap_list = {
            "C0": "00",
            "c0": "00",
            "C1": "21",
            "c1": "21",
            "c2": "22",
            "C2": "22",
            "D0": "10",
            "d0": "10",
            "D4": "14",
            "d4": "14"
        }
        for key, value in remap_list.items():
            if addr[0:2] == key:
                addr = value + addr[2:]
        return addr

    def bl616_img_addr_remap(self, addr):
        startwith = 0
        remap_list = {"22": "20", "23": "21", "62": "60", "63": "61"}
        if addr[0:2] == "0x":
            addr = addr[2:]
            startwith = 1
        for key, value in remap_list.items():
            if addr[0:2] == key:
                addr = value + addr[2:]
                break
        if startwith:
            addr = "0x" + addr
        return addr

    def eflash_loader_thread(self,
                             args,
                             eflash_loader_bin=None,
                             callback=None,
                             create_img_callback=None):
        ret = None
        try:
            bflb_utils.set_error_code("FFFF")
            ret = self.eflash_loader_t.efuse_flash_loader(args, None, eflash_loader_bin, callback,
                                                          None, create_img_callback)
            self.eflash_loader_t.object_status_clear()
        except Exception as e:
            traceback.print_exc(limit=5, file=sys.stdout)
            ret = str(e)
        finally:
            return ret

    def img_loader_thread(self, comnum, sh_baudrate, wk_baudrate, file1, file2, callback=None):
        ret = None
        try:
            img_load_t = bflb_img_loader.BflbImgLoader(self.chiptype, self.chipname)
            ret, bootinfo, res = img_load_t.img_load_process(comnum, sh_baudrate, wk_baudrate,
                                                             file1, file2, callback, True, 50, 100,
                                                             False, 50, 3)
            img_load_t.close_port()
        except Exception as e:
            traceback.print_exc(limit=5, file=sys.stdout)
            ret = str(e)
        finally:
            return ret

    def read_efuse_thread(self, values, callback=None):
        options = ""
        ret = None
        try:
            # create eflash_loader_tmp.ini
            cfg = BFConfigParser()
            if os.path.isfile(self.eflash_loader_cfg_tmp) is False:
                shutil.copyfile(self.eflash_loader_cfg, self.eflash_loader_cfg_tmp)
            cfg.read(self.eflash_loader_cfg_tmp)
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "interface", values["dl_device"].lower())
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "device", values["dl_comport"])
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "speed_uart_load", values["dl_comspeed"])
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "speed_jlink", values["dl_jlinkspeed"])
            if "dl_verify" in values.keys():
                if values["dl_verify"] == "True":
                    bflb_utils.update_cfg(cfg, "LOAD_CFG", "verify", "1")
                else:
                    bflb_utils.update_cfg(cfg, "LOAD_CFG", "verify", "0")
            cfg.write(self.eflash_loader_cfg_tmp, "w+")
            bflb_utils.printf("Save as efuse.bin")
            options = [
                "--read", "--efuse", "--start=0", "--end=255", "--file=efuse.bin", "-c",
                self.eflash_loader_cfg_tmp
            ]
            if cfg.has_option("LOAD_CFG", "boot2_isp_mode"):
                boot2_isp_mode = cfg.get("LOAD_CFG", "boot2_isp_mode")
                if int(boot2_isp_mode) == 1:
                    options.extend(["--isp"])
            eflash_loader_bin = os.path.join(
                chip_path, self.chipname, "eflash_loader/" + get_eflash_loader(values["dl_xtal"]))
            args = parser_eflash.parse_args(options)
            bh_cfg_file = self.img_create_path + "/efuse_bootheader_cfg.ini"
            self.eflash_loader_t.set_config_file(bh_cfg_file, self.img_create_cfg)
            ret = self.eflash_loader_thread(args, eflash_loader_bin, callback)
        except Exception as e:
            ret = str(e)
        finally:
            return ret

    def read_flash_thread(self, values, callback=None):
        options = ""
        start = ""
        end = ""
        ret = None
        try:
            # create eflash_loader_tmp.ini
            cfg = BFConfigParser()
            if os.path.isfile(self.eflash_loader_cfg_tmp) is False:
                shutil.copyfile(self.eflash_loader_cfg, self.eflash_loader_cfg_tmp)
            cfg.read(self.eflash_loader_cfg_tmp)
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "interface", values["dl_device"].lower())
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "device", values["dl_comport"])
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "speed_uart_load", values["dl_comspeed"])
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "speed_jlink", values["dl_jlinkspeed"])
            if "dl_verify" in values.keys():
                if values["dl_verify"] == "True":
                    bflb_utils.update_cfg(cfg, "LOAD_CFG", "verify", "1")
                else:
                    bflb_utils.update_cfg(cfg, "LOAD_CFG", "verify", "0")
            cfg.write(self.eflash_loader_cfg_tmp, "w+")
            if verify_hex_num(values["start_addr"][2:]) is True:
                if values["start_addr"][0:2] == "0x":
                    start = values["start_addr"][2:]
                else:
                    bflb_utils.printf("Error, start_addr is HEX data, must begin with 0x")
                    ret = "start_addr is HEX data, must begin with 0x"
            else:
                bflb_utils.printf("Error, Please check start_addr hex data")
                ret = "Please check start_addr hex data"
            if verify_hex_num(values["end_addr"][2:]) is True:
                if values["end_addr"][0:2] == "0x":
                    end = values["end_addr"][2:]
                else:
                    bflb_utils.printf("Error, end_addr is HEX data, must begin with 0x")
                    ret = "end_addr is HEX data, must begin with 0x"
            else:
                bflb_utils.printf("Error, Please check end_addr hex data")
                ret = "Please check end_addr hex data"
            if int(start, 16) >= int(end, 16):
                bflb_utils.printf("Error, Start addr must less than end addr")
                ret = "Start addr must less than end addr"
            if ret is not None:
                return ret
            bflb_utils.printf("Save as flash.bin")
            options = [
                "--read", "--flash", "--start=" + start, "--end=" + end, "--file=flash.bin", "-c",
                self.eflash_loader_cfg_tmp
            ]
            if cfg.has_option("LOAD_CFG", "boot2_isp_mode"):
                boot2_isp_mode = cfg.get("LOAD_CFG", "boot2_isp_mode")
                if int(boot2_isp_mode) == 1:
                    options.extend(["--isp"])
            eflash_loader_bin = os.path.join(
                chip_path, self.chipname, "eflash_loader/" + get_eflash_loader(values["dl_xtal"]))
            args = parser_eflash.parse_args(options)
            bh_cfg_file = self.img_create_path + "/efuse_bootheader_cfg.ini"
            self.eflash_loader_t.set_config_file(bh_cfg_file, self.img_create_cfg)
            ret = self.eflash_loader_thread(args, eflash_loader_bin, callback)
        except Exception as e:
            ret = str(e)
        finally:
            return ret

    def erase_flash_thread(self, values, callback=None):
        options = ""
        start = ""
        end = ""
        ret = None
        try:
            # create eflash_loader_tmp.ini
            cfg = BFConfigParser()
            if os.path.isfile(self.eflash_loader_cfg_tmp) is False:
                shutil.copyfile(self.eflash_loader_cfg, self.eflash_loader_cfg_tmp)
            cfg.read(self.eflash_loader_cfg_tmp)
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "interface", values["dl_device"].lower())
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "device", values["dl_comport"])
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "speed_uart_load", values["dl_comspeed"])
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "speed_jlink", values["dl_jlinkspeed"])
            if "dl_verify" in values.keys():
                if values["dl_verify"] == "True":
                    bflb_utils.update_cfg(cfg, "LOAD_CFG", "verify", "1")
                else:
                    bflb_utils.update_cfg(cfg, "LOAD_CFG", "verify", "0")
            cfg.write(self.eflash_loader_cfg_tmp, "w+")
            if verify_hex_num(values["start_addr"][2:]) is True:
                if values["start_addr"][0:2] == "0x":
                    start = values["start_addr"][2:]
                else:
                    bflb_utils.printf("Error, start_addr is HEX data, must begin with 0x")
                    ret = "start_addr is HEX data, must begin with 0x"
            elif values["whole_chip"] is False:
                bflb_utils.printf("Error, Please check start_addr hex data")
                ret = "Please check start_addr hex data"
            if verify_hex_num(values["end_addr"][2:]) is True:
                if values["end_addr"][0:2] == "0x":
                    end = values["end_addr"][2:]
                else:
                    bflb_utils.printf("Error, end_addr is HEX data, must begin with 0x")
                    ret = "end_addr is HEX data, must begin with 0x"
            elif values["whole_chip"] is False:
                bflb_utils.printf("Error, Please check end_addr hex data")
                ret = "Please check end_addr hex data"
            if values["whole_chip"] is False:
                if int(start, 16) >= int(end, 16):
                    bflb_utils.printf("Error, Start addr must less than end addr")
                    ret = "Start addr must less than end addr"
            if ret is not None:
                return ret
            if values["whole_chip"] is True:
                options = ["--erase", "--flash", "--end=0", "-c", self.eflash_loader_cfg_tmp]
            else:
                options = [
                    "--erase", "--flash", "--start=" + start, "--end=" + end, "-c",
                    self.eflash_loader_cfg_tmp
                ]
            if cfg.has_option("LOAD_CFG", "boot2_isp_mode"):
                boot2_isp_mode = cfg.get("LOAD_CFG", "boot2_isp_mode")
                if int(boot2_isp_mode) == 1:
                    options.extend(["--isp"])
            eflash_loader_bin = os.path.join(
                chip_path, self.chipname, "eflash_loader/" + get_eflash_loader(values["dl_xtal"]))
            args = parser_eflash.parse_args(options)
            bh_cfg_file = self.img_create_path + "/efuse_bootheader_cfg.ini"
            self.eflash_loader_t.set_config_file(bh_cfg_file, self.img_create_cfg)
            ret = self.eflash_loader_thread(args, eflash_loader_bin, callback)
        except Exception as e:
            ret = str(e)
        finally:
            return ret

    def bind_img(self, values):
        error = None
        # decide file name
        ret = self.create_img(self.chipname, self.chiptype, values)
        if ret:
            bflb_utils.printf(ret)
        try:
            if self.chiptype != "bl808":
                if values["img_type"] == "SingleCPU":
                    bootinfo_file = self.img_create_path + "/bootinfo.bin"
                    img_file = self.img_create_path + "/img.bin"
                    img_output_file = self.img_create_path + "/whole_img.bin"
                elif values["img_type"] == "BLSP_Boot2":
                    bootinfo_file = self.img_create_path + "/bootinfo_blsp_boot2.bin"
                    img_file = self.img_create_path + "/img_blsp_boot2.bin"
                    img_output_file = self.img_create_path + "/whole_img_blsp_boot2.bin"
                elif values["img_type"] == "CPU0":
                    bootinfo_file = self.img_create_path + "/bootinfo_cpu0.bin"
                    img_file = self.img_create_path + "/img_cpu0.bin"
                    img_output_file = self.img_create_path + "/whole_img_cpu0.bin"
                elif values["img_type"] == "CPU1":
                    bootinfo_file = self.img_create_path + "/bootinfo_cpu1.bin"
                    img_file = self.img_create_path + "/img_cpu1.bin"
                    img_output_file = self.img_create_path + "/whole_img_cpu1.bin"
                if values["img_type"] == "SingleCPU":
                    dummy_data = bytearray(8192)
                else:
                    dummy_data = bytearray(4096)
                for i in range(len(dummy_data)):
                    dummy_data[i] = 0xff
                fp = open(bootinfo_file, 'rb')
                data0 = fp.read() + bytearray(0)
                fp.close()
                fp = open(img_file, 'rb')
                data1 = fp.read() + bytearray(0)
                fp.close()
                fp = open(img_output_file, 'wb+')
                if data0[0:4] == data1[0:4]:
                    fp.write(data1)
                else:
                    fp.write(data0 + dummy_data[0:len(dummy_data) - len(data0)] + data1)
                fp.close()
                bflb_utils.printf("Output:", img_output_file)
            else:
                group0_bootinfo_file = self.img_create_path + "/bootinfo_group0.bin"
                group0_img_output_file = self.img_create_path + "/img_group0.bin"
                group1_bootinfo_file = self.img_create_path + "/bootinfo_group1.bin"
                group1_img_output_file = self.img_create_path + "/img_group1.bin"
                whole_img_output_file = self.img_create_path + "/whole_img.bin"
                read_data = self.bl_get_file_data([group0_bootinfo_file])[0]
                group0_img_offset = bflb_utils.bytearray_to_int(
                    bflb_utils.bytearray_reverse(read_data[132:136]))
                group0_img_len = bflb_utils.bytearray_to_int(
                    bflb_utils.bytearray_reverse(read_data[140:144]))
                read_data = self.bl_get_file_data([group1_bootinfo_file])[0]
                group1_img_offset = bflb_utils.bytearray_to_int(
                    bflb_utils.bytearray_reverse(read_data[132:136]))
                group1_img_len = bflb_utils.bytearray_to_int(
                    bflb_utils.bytearray_reverse(read_data[140:144]))
                whole_img_len = 0
                if group0_img_offset + group0_img_len > group1_img_offset + group1_img_len:
                    whole_img_len = group0_img_offset + group0_img_len
                else:
                    whole_img_len = group1_img_offset + group1_img_len
                whole_img_data = self.bl_create_flash_default_data(whole_img_len)
                group0_bootinfo_filedata = self.bl_get_file_data([group0_bootinfo_file])[0]
                whole_img_data[0:len(group0_bootinfo_filedata)] = group0_bootinfo_filedata

                group1_bootinfo_filedata = self.bl_get_file_data([group1_bootinfo_file])[0]
                whole_img_data[0x1000:len(group1_bootinfo_filedata)] = group1_bootinfo_filedata
                filedata = self.bl_get_file_data([group0_img_output_file])[0]
                if group0_img_len != len(filedata):
                    bflb_utils.printf("group0 img len error, get %d except %d" %
                                      (group0_img_len, len(filedata)))
                if group0_bootinfo_filedata[0:4] == filedata[0:4]:
                    whole_img_data = filedata
                else:
                    whole_img_data[group0_img_offset:group0_img_offset + len(filedata)] = filedata
                filedata = self.bl_get_file_data([group1_img_output_file])[0]
                if group1_img_len != len(filedata):
                    bflb_utils.printf("group1 img len error, get %d except %d" %
                                      (group1_img_len, len(filedata)))
                if group1_bootinfo_filedata[0:4] == filedata[0:4]:
                    whole_img_data = filedata
                else:
                    whole_img_data[group1_img_offset:group1_img_offset + len(filedata)] = filedata
                fp = open(whole_img_output_file, 'wb+')
                fp.write(whole_img_data)
                fp.close()
                bflb_utils.printf("Output:", whole_img_output_file)
        except Exception as e:
            bflb_utils.printf("烧写执行出错:", e)
            error = str(e)
        return error

    def create_default_img(self, chipname, chiptype, values):
        dts_bytearray = None
        security_save_efuse = False
        if values["device_tree"]:
            ro_params_d = values["device_tree"]
            try:
                dts_hex = bl_ro_device_tree.bl_dts2hex(ro_params_d)
                dts_bytearray = bflb_utils.hexstr_to_bytearray(dts_hex)
            except Exception as e:
                pass
            if dts_bytearray:
                tlv_bin = self.img_create_path + "/tlv.bin"
                with open(tlv_bin, "wb") as fp:
                    fp.write(dts_bytearray)
                bflb_utils.printf("tlv bin created success")
        if values["img_file"]:
            img_org = values["img_file"]
            if parse_rfpa(img_org) == b'BLRFPARA' and dts_bytearray:
                length = len(dts_bytearray)
                with open(img_org, "rb") as fp:
                    bin_byte = fp.read()
                    bin_bytearray = bytearray(bin_byte)
                    bin_bytearray[1032:1032 + length] = dts_bytearray
                filedir, ext = os.path.splitext(img_org)
                img_new = filedir + "_rfpa" + ext
                with open(img_new, "wb") as fp:
                    fp.write(bin_bytearray)
                values["img_file"] = img_new
                bflb_utils.printf("tlv bin inserted success")
        else:
            if values["dl_chiperase"] == "True":
                bflb_utils.printf("flash chiperase operation")
                return True
            else:
                error = "Please select image file"
                bflb_utils.printf(error)
                bflb_utils.set_error_code("0061")
                return bflb_utils.errorcode_msg()
        if values["img_addr"] == "" or values["img_addr"] == "0x":
            error = "Please set image address"
            bflb_utils.printf(error)
            bflb_utils.set_error_code("0062")
            return bflb_utils.errorcode_msg()
        if values["bootinfo_addr"] == "" or values["bootinfo_addr"] == "0x":
            error = "Please set boot info address"
            bflb_utils.printf(error)
            bflb_utils.set_error_code("0063")
            return bflb_utils.errorcode_msg()
        if "encrypt_type" in values.keys():
            if "encrypt_key" in values.keys():
                if values["encrypt_type"] != "None" and values["encrypt_key"] == "":
                    error = "Please set AES key"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0064")
                    return bflb_utils.errorcode_msg()
            if "aes_iv" in values.keys():
                if values["encrypt_type"] != "None" and values["aes_iv"] == "":
                    error = "Please set AES IV"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0065")
                    return bflb_utils.errorcode_msg()
        if "sign_type" in values.keys():
            if "public_key_cfg" in values.keys():
                if values["sign_type"] != "None" and values["public_key_cfg"] == "":
                    error = "Please set public key"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0066")
                    return bflb_utils.errorcode_msg()
            if "private_key_cfg" in values.keys():
                if values["sign_type"] != "None" and values["private_key_cfg"] == "":
                    error = "Please set private key"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0067")
                    return bflb_utils.errorcode_msg()
        # create bootheader_boot2.ini
        if values["img_type"] == "SingleCPU":
            section = "BOOTHEADER_CFG"
            bh_cfg_file = self.img_create_path + "/efuse_bootheader_cfg.ini"
            bh_file = self.img_create_path + "/bootheader.bin"
            efuse_file = self.img_create_path + "/efusedata.bin"
            efuse_mask_file = self.img_create_path + "/efusedata_mask.bin"
            bootinfo_file = self.img_create_path + "/bootinfo.bin"
            img_output_file = self.img_create_path + "/img.bin"
            img_create_section = "Img_Cfg"
        elif values["img_type"] == "BLSP_Boot2":
            if chiptype == "bl60x":
                section = "BOOTHEADER_CPU0_CFG"
            else:
                section = "BOOTHEADER_CFG"
            bh_cfg_file = self.img_create_path + "/bootheader_cfg_blsp_boot2.ini"
            bh_file = self.img_create_path + "/bootheader_blsp_boot2.bin"
            efuse_file = self.img_create_path + "/efusedata_blsp_boot2.bin"
            efuse_mask_file = self.img_create_path + "/efusedata_mask_blsp_boot2.bin"
            bootinfo_file = self.img_create_path + "/bootinfo_blsp_boot2.bin"
            img_output_file = self.img_create_path + "/img_blsp_boot2.bin"
            if chiptype == "bl60x":
                img_create_section = "Img_CPU0_Cfg"
            else:
                img_create_section = "Img_Cfg"
        elif values["img_type"] == "CPU0":
            section = "BOOTHEADER_CPU0_CFG"
            bh_cfg_file = self.img_create_path + "/bootheader_cfg_cpu0.ini"
            bh_file = self.img_create_path + "/bootheader_cpu0.bin"
            efuse_file = self.img_create_path + "/efusedata_cpu0.bin"
            efuse_mask_file = self.img_create_path + "/efusedata_mask_cpu0.bin"
            bootinfo_file = self.img_create_path + "/bootinfo_cpu0.bin"
            img_output_file = self.img_create_path + "/img_cpu0.bin"
            img_create_section = "Img_CPU0_Cfg"
        elif values["img_type"] == "CPU1":
            section = "BOOTHEADER_CPU1_CFG"
            bh_cfg_file = self.img_create_path + "/bootheader_cfg_cpu1.ini"
            bh_file = self.img_create_path + "/bootheader_cpu1.bin"
            efuse_file = self.img_create_path + "/efusedata_cpu1.bin"
            efuse_mask_file = self.img_create_path + "/efusedata_mask_cpu1.bin"
            bootinfo_file = self.img_create_path + "/bootinfo_cpu1.bin"
            img_output_file = self.img_create_path + "/img_cpu1.bin"
            img_create_section = "Img_CPU1_Cfg"
        elif values["img_type"] == "RAW":
            bflb_utils.printf("raw data do not need create.")
            bflb_utils.set_error_code("0068")
            return True
        if os.path.isfile(bh_cfg_file) is False:
            bflb_utils.copyfile(self.efuse_bh_default_cfg, bh_cfg_file)
        if values["img_type"] == "CPU0" or values["img_type"] == "CPU1":
            bflb_utils.copyfile(self.img_create_cfg_dp_org, self.img_create_cfg)
        elif values["img_type"] == "BLSP_Boot2":
            if chiptype == "bl60x":
                bflb_utils.copyfile(self.img_create_cfg_dp_org, self.img_create_cfg)
            else:
                bflb_utils.copyfile(self.img_create_cfg_org, self.img_create_cfg)
        else:
            bflb_utils.copyfile(self.img_create_cfg_org, self.img_create_cfg)
        # add flash cfg
        if os.path.exists(self.eflash_loader_cfg_tmp):
            cfg1 = BFConfigParser()
            cfg1.read(self.eflash_loader_cfg_tmp)
            if cfg1.has_option("FLASH_CFG", "flash_id"):
                flash_id = cfg1.get("FLASH_CFG", "flash_id")
                self.eflash_loader_t.set_config_file(bh_cfg_file, self.img_create_cfg)
                if bflb_flash_select.update_flash_cfg(chipname, chiptype, flash_id, bh_cfg_file,
                                                      False, section) is False:
                    error = "flash_id:" + flash_id + " do not support"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0069")
                    return bflb_utils.errorcode_msg()
            else:
                error = "Do not find flash_id in eflash_loader_cfg.ini"
                bflb_utils.printf(error)
                bflb_utils.set_error_code("0070")
                return bflb_utils.errorcode_msg()
            if cfg1.has_option("EFUSE_CFG", "security_save"):
                security_save_efuse = (cfg1.get("EFUSE_CFG", "security_save") == "true")
        else:
            bflb_utils.printf("Config file not found")
            bflb_utils.set_error_code("000B")
            return bflb_utils.errorcode_msg()
        # update config
        cfg = BFConfigParser()
        cfg.read(bh_cfg_file)
        # if section == "BOOTHEADER_CFG":
        #     cfg.update_section_name('BOOTHEADER_CPU0_CFG', section)
        for itrs in cfg.sections():
            bflb_utils.printf(itrs)
            if itrs != section and itrs != "EFUSE_CFG":
                cfg.delete_section(itrs)
        cfg.write(bh_cfg_file, "w+")
        cfg = BFConfigParser()
        cfg.read(bh_cfg_file)

        chip_erase_time = cfg.get(section, 'chip_erase_time')
        if int(chip_erase_time) > 65535:
            bflb_utils.printf("Warning: chip erase time is overflow")

        if chiptype == "bl702" or chiptype == "bl702l":
            bflb_utils.update_cfg(cfg, section, "boot2_enable", "0")
        if "xtal_type" in values.keys():
            if chiptype == "bl60x" \
            or chiptype == "bl602" \
            or chiptype == "bl702" \
            or chiptype == "bl702l":
                bflb_utils.update_cfg(cfg, section, "xtal_type",
                                      self.xtal_type_.index(values["xtal_type"]))
        if "pll_clk" in values.keys():
            if chiptype == "bl602":
                if values["pll_clk"] == "160M":
                    bflb_utils.update_cfg(cfg, section, "pll_clk", "4")
                    bflb_utils.update_cfg(cfg, section, "bclk_div", "1")
            elif chiptype == "bl702" or chiptype == "bl702l":
                if values["pll_clk"] == "144M":
                    bflb_utils.update_cfg(cfg, section, "pll_clk", "4")
                    bflb_utils.update_cfg(cfg, section, "bclk_div", "1")
            elif chiptype == "bl60x":
                if values["pll_clk"] == "160M":
                    bflb_utils.update_cfg(cfg, section, "pll_clk", "2")
                    bflb_utils.update_cfg(cfg, section, "bclk_div", "1")
        if "flash_clk_type" in values.keys():
            if chiptype == "bl602":
                if values["flash_clk_type"] == "XTAL":
                    bflb_utils.update_cfg(cfg, section, "flash_clk_type", "1")
                    bflb_utils.update_cfg(cfg, section, "flash_clk_div", "0")
                    # Set flash clock delay = 1T
                    bflb_utils.update_cfg(cfg, section, "sfctrl_clk_delay", "1")
                    bflb_utils.update_cfg(cfg, section, "sfctrl_clk_invert", "0x01")
            elif chiptype == "bl702" or chiptype == "bl702l":
                if values["flash_clk_type"] == "XCLK":
                    bflb_utils.update_cfg(cfg, section, "flash_clk_type", "1")
                    bflb_utils.update_cfg(cfg, section, "flash_clk_div", "0")
                    # Set flash clock delay = 1T
                    bflb_utils.update_cfg(cfg, section, "sfctrl_clk_delay", "1")
                    bflb_utils.update_cfg(cfg, section, "sfctrl_clk_invert", "0x01")
            elif chiptype == "bl60x":
                if values["flash_clk_type"] == "XTAL":
                    bflb_utils.update_cfg(cfg, section, "flash_clk_type", "4")
                    bflb_utils.update_cfg(cfg, section, "flash_clk_div", "0")
                    # Set flash clock delay = 1T
                    bflb_utils.update_cfg(cfg, section, "sfctrl_clk_delay", "1")
                    bflb_utils.update_cfg(cfg, section, "sfctrl_clk_invert", "0x01")

        if "sign_type" in values.keys():
            bflb_utils.update_cfg(cfg, section, "sign", self.sign_type.index(values["sign_type"]))
        if "encrypt_type" in values.keys():
            tmp = self.encrypt_type.index(values["encrypt_type"])
            bflb_utils.update_cfg(cfg, section, "encrypt_type", tmp)
            if tmp == 1 and len(values["encrypt_key"]) != 32:
                error = "Key length error"
                bflb_utils.printf(error)
                bflb_utils.set_error_code("0071")
                return bflb_utils.errorcode_msg()
            if tmp == 2 and len(values["encrypt_key"]) != 64:
                error = "Key length error"
                bflb_utils.printf(error)
                bflb_utils.set_error_code("0071")
                return bflb_utils.errorcode_msg()
            if tmp == 3 and len(values["encrypt_key"]) != 48:
                error = "Key length error"
                bflb_utils.printf(error)
                bflb_utils.set_error_code("0071")
                return bflb_utils.errorcode_msg()
            if tmp != 0:
                if len(values["aes_iv"]) != 32:
                    error = "AES IV length error"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0072")
                    return bflb_utils.errorcode_msg()
                if values["aes_iv"].endswith("00000000") is False:
                    error = "AES IV should endswith 4 bytes zero"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0073")
                    return bflb_utils.errorcode_msg()
        if "key_sel" in values.keys():
            bflb_utils.update_cfg(cfg, section, "key_sel", self.key_sel.index(values["key_sel"]))
            if self.chiptype == "bl602":
                bflb_utils.update_cfg(cfg, section, "key_sel", "0")
            elif self.chiptype == "bl702" or self.chiptype == "bl702l":
                bflb_utils.update_cfg(cfg, section, "key_sel", "1")
        if "cache_way_disable" in values.keys():
            bflb_utils.update_cfg(
                cfg, section, "cache_way_disable",
                (1 << self.cache_way_disable.index(values["cache_way_disable"])) - 1)
        if "crc_ignore" in values.keys():
            bflb_utils.update_cfg(cfg, section, "crc_ignore",
                                  self.crc_ignore.index(values["crc_ignore"]))
        if "hash_ignore" in values.keys():
            bflb_utils.update_cfg(cfg, section, "hash_ignore",
                                  self.hash_ignore.index(values["hash_ignore"]))
        if values["img_type"] == "CPU0":
            bflb_utils.update_cfg(cfg, section, "halt_cpu1", "0")
        elif chiptype != "bl602":
            bflb_utils.update_cfg(cfg, section, "halt_cpu1", "1")
        # any value except 0 is ok
        bflb_utils.update_cfg(cfg, section, "img_len", "0x100")
        bflb_utils.update_cfg(cfg, section, "img_start", values["img_addr"])
        cfg.write(bh_cfg_file, "w+")
        if values["img_type"] == "CPU1":
            bflb_efuse_boothd_create.bootheader_create_process(
                chipname, chiptype, bh_cfg_file, self.img_create_path + "/bootheader_dummy.bin",
                bh_file)
            bflb_efuse_boothd_create.efuse_create_process(chipname, chiptype, bh_cfg_file,
                                                          efuse_file)
        elif values["boot_src"].upper() == "UART/SDIO" or values["boot_src"].upper() == "UART/USB":
            bflb_efuse_boothd_create.bootheader_create_process(
                chipname, chiptype, bh_cfg_file, bh_file,
                self.img_create_path + "/bootheader_dummy.bin", True)
            bflb_efuse_boothd_create.efuse_create_process(chipname, chiptype, bh_cfg_file,
                                                          efuse_file)
        else:
            bflb_efuse_boothd_create.bootheader_create_process(
                chipname, chiptype, bh_cfg_file, bh_file,
                self.img_create_path + "/bootheader_dummy.bin")
            bflb_efuse_boothd_create.efuse_create_process(chipname, chiptype, bh_cfg_file,
                                                          efuse_file)
        # create img_create_cfg.ini
        cfg = BFConfigParser()
        cfg.read(self.img_create_cfg)
        bflb_utils.update_cfg(cfg, img_create_section, "boot_header_file", bh_file)
        bflb_utils.update_cfg(cfg, img_create_section, "efuse_file", efuse_file)
        bflb_utils.update_cfg(cfg, img_create_section, "efuse_mask_file", efuse_mask_file)
        # create segheader
        segheader = bytearray(12)
        segheader[0:4] = bflb_utils.int_to_4bytearray_l(
            int(values["img_addr"].replace("0x", ""), 16))
        segfp = open(self.img_create_path + "/segheader_tmp.bin", 'wb+')
        segfp.write(segheader)
        segfp.close()
        bflb_utils.update_cfg(cfg, img_create_section, "segheader_file",
                              self.img_create_path + "/segheader_tmp.bin")
        bflb_utils.update_cfg(cfg, img_create_section, "segdata_file", values["img_file"])

        encryptEn = False
        signEn = False
        if "encrypt_key" in values.keys() and "aes_iv" in values.keys():
            if values["encrypt_key"] != "" and values["aes_iv"]:
                encryptEn = True
        if "public_key_cfg" in values.keys() and "private_key_cfg" in values.keys():
            if values["public_key_cfg"] != "" and values["private_key_cfg"]:
                signEn = True
        if "encrypt_key" in values.keys():
            bflb_utils.update_cfg(cfg, img_create_section, "aes_key_org", values["encrypt_key"])
        if "aes_iv" in values.keys():
            bflb_utils.update_cfg(cfg, img_create_section, "aes_iv", values["aes_iv"])
        if "public_key_cfg" in values.keys():
            bflb_utils.update_cfg(cfg, img_create_section, "publickey_file",
                                  values["public_key_cfg"])
        if "private_key_cfg" in values.keys():
            bflb_utils.update_cfg(cfg, img_create_section, "privatekey_file_uecc",
                                  values["private_key_cfg"])

        bflb_utils.update_cfg(cfg, img_create_section, "bootinfo_file", bootinfo_file)
        bflb_utils.update_cfg(cfg, img_create_section, "img_file", img_output_file)
        bflb_utils.update_cfg(cfg, img_create_section, "whole_img_file",
                              img_output_file.replace(".bin", "_if.bin"))
        cfg.write(self.img_create_cfg, "w+")

        # udate efuse data
        if encryptEn or signEn:
            img_cfg = BFConfigParser()
            img_cfg.read(self.img_create_cfg)
            if chiptype == "bl60x":
                efusefile = img_cfg.get("Img_CPU0_Cfg", "efuse_file")
                efusemaskfile = img_cfg.get("Img_CPU0_Cfg", "efuse_mask_file")
            else:
                efusefile = img_cfg.get("Img_Cfg", "efuse_file")
                efusemaskfile = img_cfg.get("Img_Cfg", "efuse_mask_file")
            cfg = BFConfigParser()
            cfg.read(self.eflash_loader_cfg_tmp)
            cfg.set('EFUSE_CFG', 'file', convert_path(os.path.relpath(efusefile, app_path)))
            cfg.set('EFUSE_CFG', 'maskfile', convert_path(os.path.relpath(efusemaskfile,
                                                                          app_path)))
            cfg.write(self.eflash_loader_cfg_tmp, 'w')
            self.efuse_load_en = True
        else:
            self.efuse_load_en = False
        # create img
        if values["boot_src"].upper() == "FLASH":
            if values["img_type"] == "SingleCPU":
                # TODO: double sign
                options = ["--image=media", "--signer=none"]
                if security_save_efuse is True:
                    options.extend(["--security=efuse"])
                args = parser_image.parse_args(options)
                res = bflb_img_create.img_create(args, chipname, chiptype, self.img_create_path,
                                                 self.img_create_cfg)
                if res is not True:
                    bflb_utils.set_error_code("0060")
                    return bflb_utils.errorcode_msg()
            elif values["img_type"] == "BLSP_Boot2":
                if chiptype == "bl60x":
                    options = ["--image=media", "--cpu=cpu0", "--signer=none"]
                    if security_save_efuse is True:
                        options.extend(["--security=efuse"])
                    args = parser_image.parse_args(options)
                    res = bflb_img_create.img_create(args, chipname, chiptype,
                                                     self.img_create_path, self.img_create_cfg)
                    if res is not True:
                        bflb_utils.set_error_code("0060")
                        return bflb_utils.errorcode_msg()
                else:
                    options = ["--image=media", "--signer=none"]
                    if security_save_efuse is True:
                        options.extend(["--security=efuse"])
                    args = parser_image.parse_args(options)
                    res = bflb_img_create.img_create(args, chipname, chiptype,
                                                     self.img_create_path, self.img_create_cfg)
                    if res is not True:
                        bflb_utils.set_error_code("0060")
                        return bflb_utils.errorcode_msg()
            elif values["img_type"] == "CPU0":
                options = ["--image=media", "--cpu=cpu0", "--signer=none"]
                if security_save_efuse is True:
                    options.extend(["--security=efuse"])
                args = parser_image.parse_args(options)
                res = bflb_img_create.img_create(args, chipname, chiptype, self.img_create_path,
                                                 self.img_create_cfg)
                if res is not True:
                    bflb_utils.set_error_code("0060")
                    return bflb_utils.errorcode_msg()
            elif values["img_type"] == "CPU1":
                options = ["--image=media", "--cpu=cpu1", "--signer=none"]
                if security_save_efuse is True:
                    options.extend(["--security=efuse"])
                args = parser_image.parse_args(options)
                res = bflb_img_create.img_create(args, chipname, chiptype, self.img_create_path,
                                                 self.img_create_cfg)
                if res is not True:
                    bflb_utils.set_error_code("0060")
                    return bflb_utils.errorcode_msg()
        else:
            if values["img_type"] == "SingleCPU":
                options = ["--image=if", "--signer=none"]
                if security_save_efuse is True:
                    options.extend(["--security=efuse"])
                args = parser_image.parse_args(options)
                res = bflb_img_create.img_create(args, chipname, chiptype, self.img_create_path,
                                                 self.img_create_cfg)
                if res is not True:
                    bflb_utils.set_error_code("0060")
                    return bflb_utils.errorcode_msg()
            elif values["img_type"] == "CPU0":
                options = ["--image=if", "--cpu=cpu0", "--signer=none"]
                if security_save_efuse is True:
                    options.extend(["--security=efuse"])
                args = parser_image.parse_args(options)
                res = bflb_img_create.img_create(args, chipname, chiptype, self.img_create_path,
                                                 self.img_create_cfg)
                if res is not True:
                    bflb_utils.set_error_code("0060")
                    return bflb_utils.errorcode_msg()
            elif values["img_type"] == "CPU1":
                options = ["--image=if", "--cpu=cpu1", "--signer=none"]
                if security_save_efuse is True:
                    options.extend(["--security=efuse"])
                args = parser_image.parse_args(options)
                res = bflb_img_create.img_create(args, chipname, chiptype, self.img_create_path,
                                                 self.img_create_cfg)
                if res is not True:
                    bflb_utils.set_error_code("0060")
                    return bflb_utils.errorcode_msg()
        os.remove(self.img_create_path + "/segheader_tmp.bin")
        if os.path.exists(self.img_create_path + '/bootheader_dummy.bin'):
            os.remove(self.img_create_path + "/bootheader_dummy.bin")
        return True

    def create_bl808_bl628_img(self, chipname, chiptype, values):
        # basic check
        error = True
        group0_enable = False
        group1_enable = False
        group0_img_start = "0xFFFFFFFF"
        group1_img_start = "0xFFFFFFFF"
        group0_img = ""
        group1_img = ""
        if chiptype == "bl628":
            cpu_num = 2
            cpu_list = ["m0", "m1"]
            img_addr_offset = ["0x0", "0x0", "0x0", "0x0"]
            segheader_file = [
                "/segheader_group0_m0.bin", "/segheader_group0_m1.bin", "/segheader_group1_m0.bin",
                "/segheader_group1_m1.bin"
            ]
        else:
            cpu_num = 3
            cpu_list = ["m0", "d0", "lp"]
            img_addr_offset = ["0x0", "0x0", "0x0", "0x0", "0x0", "0x0"]
            segheader_file = [
                "/segheader_group0_m0.bin", "/segheader_group0_d0.bin", "/segheader_group0_lp.bin",
                "/segheader_group1_m0.bin", "/segheader_group1_d0.bin", "/segheader_group1_lp.bin"
            ]
        security_save_efuse = False
        dts_bytearray = None
        if values["device_tree"]:
            ro_params_d = values["device_tree"]
            try:
                dts_hex = bl_ro_device_tree.bl_dts2hex(ro_params_d)
                dts_bytearray = bflb_utils.hexstr_to_bytearray(dts_hex)
            except Exception as e:
                pass
            if dts_bytearray:
                tlv_bin = self.img_create_path + "/tlv.bin"
                with open(tlv_bin, "wb") as fp:
                    fp.write(dts_bytearray)
                bflb_utils.printf("tlv bin created success")
        if values["img1_file"] and values["img1_group"] != "unused":
            img_org = values["img1_file"]
            if parse_rfpa(img_org) == b'BLRFPARA' and dts_bytearray:
                length = len(dts_bytearray)
                with open(img_org, "rb") as fp:
                    bin_byte = fp.read()
                    bin_bytearray = bytearray(bin_byte)
                    bin_bytearray[1032:1032 + length] = dts_bytearray
                filedir, ext = os.path.splitext(img_org)
                img_new = filedir + "_rfpa" + ext
                with open(img_new, "wb") as fp:
                    fp.write(bin_bytearray)
                values["img1_file"] = img_new
                bflb_utils.printf("tlv bin inserted success")
        for index in range(cpu_num):
            num = str(index + 1)
            if values["img%s_group" % num] != "unused":
                if values["img%s_file" % num] == "":
                    error = "Please select image%s file" % num
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0061")
                    return bflb_utils.errorcode_msg()
                if values["img%s_addr" % num] == "" or values["img%s_addr" % num] == "0x":
                    error = "Please set image%s address" % num
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0062")
                    return bflb_utils.errorcode_msg()
                img_start = int(values["img%s_addr" % num].replace("0x", ""), 16)
                if values["img%s_group" % num] == "group0":
                    group0_enable = True
                    group0_img += values["img%s_file" % num]
                    group1_img += "UNUSED"
                    img_addr_offset[index] = values["img%s_addr" % num]
                    if int(group0_img_start.replace("0x", ""), 16) > img_start:
                        group0_img_start = values["img%s_addr" % num]
                elif values["img%s_group" % num] == "group1":
                    group1_enable = True
                    group0_img += "UNUSED"
                    group1_img += values["img%s_file" % num]
                    img_addr_offset[index + cpu_num] = values["img%s_addr" % num]
                    if int(group1_img_start.replace("0x", ""), 16) > img_start:
                        group1_img_start = values["img%s_addr" % num]
            else:
                group0_img += "UNUSED"
                group1_img += "UNUSED"
            group0_img += "|"
            group1_img += "|"
        group0_img = group0_img.strip()
        group1_img = group1_img.strip()
        if group0_img_start == "0xFFFFFFFF":
            group0_img_start = "0x00000000"
        if group1_img_start == "0xFFFFFFFF":
            group1_img_start = "0x00000000"
        if "encrypt_type-group0" in values.keys():
            if "encrypt_key-group0" in values.keys():
                if values["encrypt_type-group0"] != "None" and values["encrypt_key-group0"] == "":
                    error = "Please set group0 AES key"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0064")
                    return bflb_utils.errorcode_msg()
            if "aes_iv-group0" in values.keys():
                if values["encrypt_type-group0"] != "None" and values["aes_iv-group0"] == "":
                    error = "Please set group0 AES IV"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0065")
                    return bflb_utils.errorcode_msg()
        if "encrypt_type-group1" in values.keys():
            if "encrypt_key-group1" in values.keys():
                if values["encrypt_type-group1"] != "None" and values["encrypt_key-group1"] == "":
                    error = "Please set group1 AES key"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0064")
                    return bflb_utils.errorcode_msg()
            if "aes_iv-group1" in values.keys():
                if values["encrypt_type-group1"] != "None" and values["aes_iv-group1"] == "":
                    error = "Please set group1 AES IV"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0065")
                    return bflb_utils.errorcode_msg()
        if "sign_type-group0" in values.keys():
            if "public_key_cfg-group0" in values.keys():
                if values["sign_type-group0"] != "None" and values["public_key_cfg-group0"] == "":
                    error = "Please set group0 public key"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0066")
                    return bflb_utils.errorcode_msg()
            if "private_key_cfg-group0" in values.keys():
                if values["sign_type-group0"] != "None" and values["private_key_cfg-group0"] == "":
                    error = "Please set group0 private key"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0067")
                    return bflb_utils.errorcode_msg()
        if "sign_type-group1" in values.keys():
            if "public_key_cfg-group1" in values.keys():
                if values["sign_type-group1"] != "None" and values["public_key_cfg-group1"] == "":
                    error = "Please set group1 public key"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0066")
                    return bflb_utils.errorcode_msg()
            if "private_key_cfg-group1" in values.keys():
                if values["sign_type-group1"] != "None" and values["private_key_cfg-group1"] == "":
                    error = "Please set group1 private key"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0067")
                    return bflb_utils.errorcode_msg()
        group0_section = "BOOTHEADER_GROUP0_CFG"
        group1_section = "BOOTHEADER_GROUP1_CFG"
        bh_cfg_file = self.img_create_path + "/efuse_bootheader_cfg.ini"
        group0_bh_file = self.img_create_path + "/bootheader_group0.bin"
        group1_bh_file = self.img_create_path + "/bootheader_group1.bin"
        efuse_file = self.img_create_path + "/efusedata.bin"
        efuse_mask_file = self.img_create_path + "/efusedata_mask.bin"
        group0_bootinfo_file = self.img_create_path + "/bootinfo_group0.bin"
        group1_bootinfo_file = self.img_create_path + "/bootinfo_group1.bin"
        group0_img_output_file = self.img_create_path + "/img_group0.bin"
        group1_img_output_file = self.img_create_path + "/img_group1.bin"
        group0_img_create_section = "Img_Group0_Cfg"
        group1_img_create_section = "Img_Group1_Cfg"
        if os.path.isfile(bh_cfg_file) is False:
            bflb_utils.copyfile(self.efuse_bh_default_cfg, bh_cfg_file)
        shutil.copyfile(self.img_create_cfg_org, self.img_create_cfg)
        # add flash cfg
        if os.path.exists(self.eflash_loader_cfg_tmp):
            cfg1 = BFConfigParser()
            cfg1.read(self.eflash_loader_cfg_tmp)
            if cfg1.has_option("FLASH_CFG", "flash_id"):
                flash_id = cfg1.get("FLASH_CFG", "flash_id")
                if bflb_flash_select.update_flash_cfg(chipname, chiptype, flash_id, bh_cfg_file,
                                                      False, group0_section) is False:
                    error = "flash_id:" + flash_id + " do not support"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0069")
                    return bflb_utils.errorcode_msg()
            else:
                error = "Do not find flash_id in eflash_loader_cfg.ini"
                bflb_utils.printf(error)
                bflb_utils.set_error_code("0070")
                return bflb_utils.errorcode_msg()
            if cfg1.has_option("EFUSE_CFG", "security_save"):
                security_save_efuse = (cfg1.get("EFUSE_CFG", "security_save") == "true")
        else:
            bflb_utils.printf("Config file not found")
            bflb_utils.set_error_code("000B")
            return bflb_utils.errorcode_msg()
        # update config
        cfg = BFConfigParser()
        cfg.read(bh_cfg_file)
        for itrs in cfg.sections():
            bflb_utils.printf(itrs)
            if itrs != group0_section and itrs != group1_section and itrs != "EFUSE_CFG":
                cfg.delete_section(itrs)
        cfg.write(bh_cfg_file, "w+")
        cfg = BFConfigParser()
        cfg.read(bh_cfg_file)

        chip_erase_time = cfg.get(group0_section, 'chip_erase_time')
        if int(chip_erase_time) > 65535:
            bflb_utils.printf("Warning: chip erase time is overflow")

        bflb_utils.update_cfg(cfg, group0_section, "boot2_enable", "0")
        bflb_utils.update_cfg(cfg, group1_section, "boot2_enable", "0")
        #         if "xtal_type" in values.keys():
        #             bflb_utils.update_cfg(cfg, group0_section, "xtal_type",
        #                                   self.xtal_type_.index(values["xtal_type"]))
        if "mcu_clk" in values.keys():
            if values["mcu_clk"] == "WIFIPLL 320M":
                bflb_utils.update_cfg(cfg, group0_section, "mcu_clk", "4")
                bflb_utils.update_cfg(cfg, group0_section, "mcu_clk_div", "0")
        if "flash_clk_type" in values.keys():
            if values["flash_clk_type"] == "XTAL":
                bflb_utils.update_cfg(cfg, group0_section, "flash_clk_type", "1")
                bflb_utils.update_cfg(cfg, group0_section, "flash_clk_div", "0")
                # Set flash clock delay = 1T
                bflb_utils.update_cfg(cfg, group0_section, "sfctrl_clk_delay", "1")
                bflb_utils.update_cfg(cfg, group0_section, "sfctrl_clk_invert", "0x01")
        if "sign_type-group0" in values.keys():
            bflb_utils.update_cfg(cfg, group0_section, "sign",
                                  self.sign_type.index(values["sign_type-group0"]))
        if "encrypt_type-group0" in values.keys():
            tmp = self.encrypt_type.index(values["encrypt_type-group0"])
            if tmp == 4 or tmp == 5 or tmp == 6:
                # XTS 128/256/192
                bflb_utils.update_cfg(cfg, group0_section, "encrypt_type", tmp - 3)
                bflb_utils.update_cfg(cfg, group0_section, "xts_mode", "1")
            else:
                bflb_utils.update_cfg(cfg, group0_section, "encrypt_type", tmp)
                bflb_utils.update_cfg(cfg, group0_section, "xts_mode", "0")
            if tmp == 1 and len(values["encrypt_key-group0"]) != 32:
                error = "group0 key length error"
                bflb_utils.printf(error)
                bflb_utils.set_error_code("0071")
                return bflb_utils.errorcode_msg()
            if tmp == 3 and len(values["encrypt_key-group0"]) != 48:
                error = "group0 key length error"
                bflb_utils.printf(error)
                bflb_utils.set_error_code("0071")
                return bflb_utils.errorcode_msg()
            if tmp == 2 or tmp == 4 or tmp == 5 or tmp == 6:
                if len(values["encrypt_key-group0"]) != 64:
                    error = "group0 key length error"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0071")
                    return bflb_utils.errorcode_msg()
            if tmp != 0:
                if len(values["aes_iv-group0"]) != 32:
                    error = "group0 AES IV length error"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0072")
                    return bflb_utils.errorcode_msg()
                if values["aes_iv-group0"].endswith("00000000") is False:
                    error = "group0 AES IV should endswith 4 bytes zero"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0073")
                    return bflb_utils.errorcode_msg()
        if "key_sel-group0" in values.keys():
            bflb_utils.update_cfg(cfg, group0_section, "key_sel",
                                  self.key_sel.index(values["key_sel-group0"]))
        if "crc_ignore-group0" in values.keys():
            bflb_utils.update_cfg(cfg, group0_section, "crc_ignore",
                                  self.crc_ignore.index(values["crc_ignore-group0"]))
        if "hash_ignore-group0" in values.keys():
            bflb_utils.update_cfg(cfg, group0_section, "hash_ignore",
                                  self.hash_ignore.index(values["hash_ignore-group0"]))
        if "sign_type-group1" in values.keys():
            bflb_utils.update_cfg(cfg, group1_section, "sign",
                                  self.sign_type.index(values["sign_type-group1"]))
        if "encrypt_type-group1" in values.keys():
            tmp = self.encrypt_type.index(values["encrypt_type-group1"])
            if tmp == 4 or tmp == 5 or tmp == 6:
                # XTS 128/256/192
                bflb_utils.update_cfg(cfg, group1_section, "encrypt_type", tmp - 3)
                bflb_utils.update_cfg(cfg, group1_section, "xts_mode", "1")
            else:
                bflb_utils.update_cfg(cfg, group1_section, "encrypt_type", tmp)
                bflb_utils.update_cfg(cfg, group1_section, "xts_mode", "0")
            if tmp == 1 and len(values["encrypt_key-group1"]) != 32:
                error = "group1 key length error"
                bflb_utils.printf(error)
                bflb_utils.set_error_code("0071")
                return bflb_utils.errorcode_msg()
            if tmp == 3 and len(values["encrypt_key-group1"]) != 48:
                error = "group1 key length error"
                bflb_utils.printf(error)
                bflb_utils.set_error_code("0071")
                return bflb_utils.errorcode_msg()
            if tmp == 2 or tmp == 4 or tmp == 5 or tmp == 6:
                if len(values["encrypt_key-group1"]) != 64:
                    error = "group1 key length error"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0071")
                    return bflb_utils.errorcode_msg()
            if tmp != 0:
                if len(values["aes_iv-group1"]) != 32:
                    error = "group1 AES IV length error"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0072")
                    return bflb_utils.errorcode_msg()
                if values["aes_iv-group1"].endswith("00000000") is False:
                    error = "group1 AES IV should endswith 4 bytes zero"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0073")
                    return bflb_utils.errorcode_msg()
        if "key_sel-group1" in values.keys():
            bflb_utils.update_cfg(cfg, group1_section, "key_sel",
                                  self.key_sel.index(values["key_sel-group1"]))
        if "crc_ignore-group1" in values.keys():
            bflb_utils.update_cfg(cfg, group1_section, "crc_ignore",
                                  self.crc_ignore.index(values["crc_ignore-group1"]))
        if "hash_ignore-group1" in values.keys():
            bflb_utils.update_cfg(cfg, group1_section, "hash_ignore",
                                  self.hash_ignore.index(values["hash_ignore-group1"]))
        for index in range(cpu_num):
            num = str(index + 1)
            if values["img%s_group" % num] == "unused":
                bflb_utils.update_cfg(cfg, group0_section, "%s_config_enable" % cpu_list[index],
                                      "0")
                # bflb_utils.update_cfg(cfg, group0_section, "%s_halt_cpu" % cpu_list[index], "1")
                bflb_utils.update_cfg(cfg, group1_section, "%s_config_enable" % cpu_list[index],
                                      "0")
                # bflb_utils.update_cfg(cfg, group1_section, "%s_halt_cpu" % cpu_list[index], "1")
            elif values["img%s_group" % num] == "group0":
                bflb_utils.update_cfg(cfg, group0_section, "%s_config_enable" % cpu_list[index],
                                      "1")
                # bflb_utils.update_cfg(cfg, group0_section, "%s_halt_cpu" % cpu_list[index], "0")
                bflb_utils.update_cfg(cfg, group1_section, "%s_config_enable" % cpu_list[index],
                                      "0")
                # bflb_utils.update_cfg(cfg, group1_section, "%s_halt_cpu" % cpu_list[index], "0")
            elif values["img%s_group" % num] == "group1":
                bflb_utils.update_cfg(cfg, group0_section, "%s_config_enable" % cpu_list[index],
                                      "0")
                # bflb_utils.update_cfg(cfg, group0_section, "%s_halt_cpu" % cpu_list[index], "0")
                bflb_utils.update_cfg(cfg, group1_section, "%s_config_enable" % cpu_list[index],
                                      "1")
                # bflb_utils.update_cfg(cfg, group1_section, "%s_halt_cpu" % cpu_list[index], "0")

        bflb_utils.update_cfg(cfg, group0_section, "img_len_cnt", "0x100")
        bflb_utils.update_cfg(cfg, group1_section, "img_len_cnt", "0x100")
        for index in range(cpu_num):
            if int(img_addr_offset[index].replace("0x", ""), 16) > 0:
                offset = int(img_addr_offset[index].replace("0x", ""), 16) - int(
                    group0_img_start.replace("0x", ""), 16)
                bflb_utils.update_cfg(cfg, group0_section,
                                      "%s_image_address_offset" % cpu_list[index],
                                      "0x%X" % (offset))
                bflb_utils.update_cfg(cfg, group0_section, "%s_boot_entry" % cpu_list[index],
                                      "0x%X" % (int(img_addr_offset[index].replace("0x", ""), 16)))
            if int(img_addr_offset[index + cpu_num].replace("0x", ""), 16) > 0:
                offset = int(img_addr_offset[index + cpu_num].replace("0x", ""), 16) - int(
                    group1_img_start.replace("0x", ""), 16)
                bflb_utils.update_cfg(cfg, group1_section,
                                      "%s_image_address_offset" % cpu_list[index],
                                      "0x%X" % (offset))
                bflb_utils.update_cfg(
                    cfg, group1_section, "%s_boot_entry" % cpu_list[index],
                    "0x%X" % (int(img_addr_offset[index + cpu_num].replace("0x", ""), 16)))

        if values["boot_src"].upper() == "UART/USB":
            for index in range(cpu_num):
                bflb_utils.update_cfg(cfg, group0_section, "%s_boot_entry" % cpu_list[index],
                                      self.img_addr_remap(img_addr_offset[index]))
                bflb_utils.update_cfg(cfg, group1_section, "%s_boot_entry" % cpu_list[index],
                                      self.img_addr_remap(img_addr_offset[index + cpu_num]))
        cfg.write(bh_cfg_file, "w+")
        if values["boot_src"].upper() == "FLASH":
            bflb_efuse_boothd_create.bootheader_create_process(
                chipname, chiptype, bh_cfg_file, group0_bh_file, group1_bh_file,
                self.img_create_path + "/bootheader_dummy.bin")
            bflb_efuse_boothd_create.efuse_create_process(chipname, chiptype, bh_cfg_file,
                                                          efuse_file)
            if group0_enable is not True:
                self.bflb_set_file_ff(group0_bh_file)
            if group1_enable is not True:
                self.bflb_set_file_ff(group1_bh_file)
        else:
            bflb_efuse_boothd_create.bootheader_create_process(chipname, chiptype, bh_cfg_file,
                                                               group0_bh_file, group1_bh_file,
                                                               True)
            bflb_efuse_boothd_create.efuse_create_process(chipname, chiptype, bh_cfg_file,
                                                          efuse_file)
        # create img_create_cfg.ini
        cfg = BFConfigParser()
        cfg.read(self.img_create_cfg)
        bflb_utils.update_cfg(cfg, group0_img_create_section, "boot_header_file", group0_bh_file)
        bflb_utils.update_cfg(cfg, group1_img_create_section, "boot_header_file", group1_bh_file)
        bflb_utils.update_cfg(cfg, group0_img_create_section, "efuse_file", efuse_file)
        bflb_utils.update_cfg(cfg, group1_img_create_section, "efuse_file", efuse_file)
        bflb_utils.update_cfg(cfg, group0_img_create_section, "efuse_mask_file", efuse_mask_file)
        bflb_utils.update_cfg(cfg, group1_img_create_section, "efuse_mask_file", efuse_mask_file)
        # create segheader
        i = 0
        segheader_group0 = ""
        segheader_group1 = ""
        while i < len(segheader_file):
            if i < cpu_num:
                if segheader_group0 != "":
                    segheader_group0 += " "
                segheader_group0 += self.img_create_path + segheader_file[i]
            else:
                if segheader_group1 != "":
                    segheader_group1 += " "
                segheader_group1 += self.img_create_path + segheader_file[i]
            segheader = bytearray(12)
            segheader[0:4] = bflb_utils.int_to_4bytearray_l(
                int(self.img_addr_remap(img_addr_offset[i].replace("0x", "")), 16))
            segfp = open(self.img_create_path + segheader_file[i], 'wb+')
            segfp.write(segheader)
            segfp.close()
            i = i + 1
        bflb_utils.update_cfg(cfg, group0_img_create_section, "segheader_file", segheader_group0)
        bflb_utils.update_cfg(cfg, group1_img_create_section, "segheader_file", segheader_group1)
        bflb_utils.update_cfg(cfg, group0_img_create_section, "segdata_file", group0_img)
        bflb_utils.update_cfg(cfg, group1_img_create_section, "segdata_file", group1_img)
        if "encrypt_key-group0" in values.keys():
            bflb_utils.update_cfg(cfg, group0_img_create_section, "aes_key_org",
                                  values["encrypt_key-group0"])
        if "aes_iv-group0" in values.keys():
            bflb_utils.update_cfg(cfg, group0_img_create_section, "aes_iv",
                                  values["aes_iv-group0"])
        if "public_key_cfg-group0" in values.keys():
            bflb_utils.update_cfg(cfg, group0_img_create_section, "publickey_file",
                                  values["public_key_cfg-group0"])
        if "private_key_cfg-group0" in values.keys():
            bflb_utils.update_cfg(cfg, group0_img_create_section, "privatekey_file_uecc",
                                  values["private_key_cfg-group0"])
        if "encrypt_key-group1" in values.keys():
            bflb_utils.update_cfg(cfg, group1_img_create_section, "aes_key_org",
                                  values["encrypt_key-group1"])
        if "aes_iv-group1" in values.keys():
            bflb_utils.update_cfg(cfg, group1_img_create_section, "aes_iv",
                                  values["aes_iv-group1"])
        if "public_key_cfg-group1" in values.keys():
            bflb_utils.update_cfg(cfg, group1_img_create_section, "publickey_file",
                                  values["public_key_cfg-group1"])
        if "private_key_cfg-group1" in values.keys():
            bflb_utils.update_cfg(cfg, group1_img_create_section, "privatekey_file_uecc",
                                  values["private_key_cfg-group1"])
        bflb_utils.update_cfg(cfg, group0_img_create_section, "bootinfo_file",
                              group0_bootinfo_file)
        bflb_utils.update_cfg(cfg, group1_img_create_section, "bootinfo_file",
                              group1_bootinfo_file)
        bflb_utils.update_cfg(cfg, group0_img_create_section, "img_file", group0_img_output_file)
        bflb_utils.update_cfg(cfg, group1_img_create_section, "img_file", group1_img_output_file)
        bflb_utils.update_cfg(cfg, group0_img_create_section, "whole_img_file",
                              group0_img_output_file.replace(".bin", "_if.bin"))
        bflb_utils.update_cfg(cfg, group1_img_create_section, "whole_img_file",
                              group1_img_output_file.replace(".bin", "_if.bin"))
        cfg.write(self.img_create_cfg, "w+")
        # create img
        if values["boot_src"].upper() == "FLASH":
            options = ["--image=media", "--group=all", "--signer=none"]
            if security_save_efuse is True:
                options.extend(["--security=efuse"])
            args = parser_image.parse_args(options)
            res = bflb_img_create.img_create(args, chipname, chiptype, self.img_create_path,
                                             self.img_create_cfg)
            if res is not True:
                bflb_utils.set_error_code("0060")
                return bflb_utils.errorcode_msg()
        else:
            options = ["--image=if", "--group=all", "--signer=none"]
            if security_save_efuse is True:
                options.extend(["--security=efuse"])
            args = parser_image.parse_args(options)
            res = bflb_img_create.img_create(args, chipname, chiptype, self.img_create_path,
                                             self.img_create_cfg)
            if res is not True:
                bflb_utils.set_error_code("0060")
                return bflb_utils.errorcode_msg()
        i = 0
        while i < len(segheader_file):
            os.remove(self.img_create_path + segheader_file[i])
            i = i + 1
        if os.path.exists(self.img_create_path + '/bootheader_dummy.bin'):
            os.remove(self.img_create_path + "/bootheader_dummy.bin")
        return True

    def create_bl616_img(self, chipname, chiptype, values):
        # basic check
        error = True
        group0_img_start = "0xFFFFFFFF"
        group0_img = ""
        img_addr_offset = "0x0"
        segheader_file = "/segheader.bin"
        security_save_efuse = False

        dts_bytearray = None
        if values["device_tree"]:
            ro_params_d = values["device_tree"]
            try:
                dts_hex = bl_ro_device_tree.bl_dts2hex(ro_params_d)
                dts_bytearray = bflb_utils.hexstr_to_bytearray(dts_hex)
            except Exception as e:
                pass
            if dts_bytearray:
                tlv_bin = self.img_create_path + "/tlv.bin"
                with open(tlv_bin, "wb") as fp:
                    fp.write(dts_bytearray)
                bflb_utils.printf("tlv bin created success")
        if values["img1_file"]:
            img_org = values["img1_file"]
            if parse_rfpa(img_org) == b'BLRFPARA' and dts_bytearray:
                length = len(dts_bytearray)
                with open(img_org, "rb") as fp:
                    bin_byte = fp.read()
                    bin_bytearray = bytearray(bin_byte)
                    bin_bytearray[1032:1032 + length] = dts_bytearray
                filedir, ext = os.path.splitext(img_org)
                img_new = filedir + "_rfpa" + ext
                with open(img_new, "wb") as fp:
                    fp.write(bin_bytearray)
                values["img1_file"] = img_new
                bflb_utils.printf("tlv bin inserted success")
        else:
            if values["dl_chiperase"] == "True":
                bflb_utils.printf("flash chiperase operation")
                return True
            else:
                error = "Please select image1 file"
                bflb_utils.printf(error)
                bflb_utils.set_error_code("0061")
                return bflb_utils.errorcode_msg()
        if values["img1_addr"] == "" or values["img1_addr"] == "0x":
            error = "Please set image1 address"
            bflb_utils.printf(error)
            bflb_utils.set_error_code("0062")
            return bflb_utils.errorcode_msg()
        img_start = int(values["img1_addr"].replace("0x", ""), 16)
        group0_img += values["img1_file"]
        img_addr_offset = values["img1_addr"]
        if int(group0_img_start.replace("0x", ""), 16) > img_start:
            group0_img_start = values["img1_addr"]
        group0_img = group0_img.strip()
        if group0_img_start == "0xFFFFFFFF":
            group0_img_start = "0x00000000"
        if "encrypt_type-group0" in values.keys():
            if "encrypt_key-group0" in values.keys():
                if values["encrypt_type-group0"] != "None" and values["encrypt_key-group0"] == "":
                    error = "Please set group0 AES key"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0064")
                    return bflb_utils.errorcode_msg()
            if "aes_iv-group0" in values.keys():
                if values["encrypt_type-group0"] != "None" and values["aes_iv-group0"] == "":
                    error = "Please set group0 AES IV"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0065")
                    return bflb_utils.errorcode_msg()
        if "sign_type-group0" in values.keys():
            if "public_key_cfg-group0" in values.keys():
                if values["sign_type-group0"] != "None" and values["public_key_cfg-group0"] == "":
                    error = "Please set group0 public key"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0066")
                    return bflb_utils.errorcode_msg()
            if "private_key_cfg-group0" in values.keys():
                if values["sign_type-group0"] != "None" and values["private_key_cfg-group0"] == "":
                    error = "Please set group0 private key"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0067")
                    return bflb_utils.errorcode_msg()
        group0_section = "BOOTHEADER_GROUP0_CFG"
        bh_cfg_file = self.img_create_path + "/efuse_bootheader_cfg.ini"
        group0_bh_file = self.img_create_path + "/bootheader.bin"
        efuse_file = self.img_create_path + "/efusedata.bin"
        efuse_mask_file = self.img_create_path + "/efusedata_mask.bin"
        group0_bootinfo_file = self.img_create_path + "/bootinfo.bin"
        group0_img_output_file = self.img_create_path + "/img.bin"
        group0_img_create_section = "Img_Group0_Cfg"
        if os.path.isfile(bh_cfg_file) is False:
            bflb_utils.copyfile(self.efuse_bh_default_cfg, bh_cfg_file)
        shutil.copyfile(self.img_create_cfg_org, self.img_create_cfg)
        # add flash cfg
        if os.path.exists(self.eflash_loader_cfg_tmp):
            cfg1 = BFConfigParser()
            cfg1.read(self.eflash_loader_cfg_tmp)
            if cfg1.has_option("FLASH_CFG", "flash_id"):
                flash_id = cfg1.get("FLASH_CFG", "flash_id")
                if bflb_flash_select.update_flash_cfg(chipname, chiptype, flash_id, bh_cfg_file,
                                                      False, group0_section) is False:
                    error = "flash_id:" + flash_id + " do not support"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0069")
                    return bflb_utils.errorcode_msg()
            else:
                error = "Do not find flash_id in eflash_loader_cfg.ini"
                bflb_utils.printf(error)
                bflb_utils.set_error_code("0070")
                return bflb_utils.errorcode_msg()
            if cfg1.has_option("EFUSE_CFG", "security_save"):
                security_save_efuse = (cfg1.get("EFUSE_CFG", "security_save") == "true")
        else:
            bflb_utils.printf("Config file not found")
            bflb_utils.set_error_code("000B")
            return bflb_utils.errorcode_msg()
        # update config
        cfg = BFConfigParser()
        cfg.read(bh_cfg_file)
        for itrs in cfg.sections():
            bflb_utils.printf(itrs)
            if itrs != group0_section and itrs != "EFUSE_CFG":
                cfg.delete_section(itrs)
        cfg.write(bh_cfg_file, "w+")
        cfg = BFConfigParser()
        cfg.read(bh_cfg_file)

        chip_erase_time = cfg.get(group0_section, 'chip_erase_time')
        if int(chip_erase_time) > 65535:
            bflb_utils.printf("Warning: chip erase time is overflow")

        bflb_utils.update_cfg(cfg, group0_section, "boot2_enable", "0")
        #         if "xtal_type" in values.keys():
        #             bflb_utils.update_cfg(cfg, group0_section, "xtal_type",
        #                                   self.xtal_type_.index(values["xtal_type"]))
        if "mcu_clk" in values.keys():
            if values["mcu_clk"] == "WIFIPLL 320M":
                bflb_utils.update_cfg(cfg, group0_section, "mcu_clk", "5")
                bflb_utils.update_cfg(cfg, group0_section, "mcu_clk_div", "0")
        if "flash_clk_type" in values.keys():
            if values["flash_clk_type"] == "XTAL":
                bflb_utils.update_cfg(cfg, group0_section, "flash_clk_type", "1")
                bflb_utils.update_cfg(cfg, group0_section, "flash_clk_div", "0")
                # Set flash clock delay = 1T
                bflb_utils.update_cfg(cfg, group0_section, "sfctrl_clk_delay", "1")
                bflb_utils.update_cfg(cfg, group0_section, "sfctrl_clk_invert", "0x01")
        if "sign_type-group0" in values.keys():
            bflb_utils.update_cfg(cfg, group0_section, "sign",
                                  self.sign_type.index(values["sign_type-group0"]))
            if cfg.has_option(group0_section, "custom_ecc_type"):
                bflb_utils.update_cfg(cfg, group0_section, "custom_ecc_type",
                                      self.sign_type.index(values["sign_type-group0"]))
        if "encrypt_type-group0" in values.keys():
            tmp = self.encrypt_type.index(values["encrypt_type-group0"])
            if tmp == 4 or tmp == 5 or tmp == 6:
                # XTS 128/256/192
                bflb_utils.update_cfg(cfg, group0_section, "encrypt_type", tmp - 3)
                bflb_utils.update_cfg(cfg, group0_section, "xts_mode", "1")
            else:
                bflb_utils.update_cfg(cfg, group0_section, "encrypt_type", tmp)
                bflb_utils.update_cfg(cfg, group0_section, "xts_mode", "0")
                if cfg.has_option(group0_section, "custom_aes_type"):
                    bflb_utils.update_cfg(cfg, group0_section, "custom_aes_type", tmp)
            if tmp == 1 and len(values["encrypt_key-group0"]) != 32:
                error = "group0 key length error"
                bflb_utils.printf(error)
                bflb_utils.set_error_code("0071")
                return bflb_utils.errorcode_msg()
            if tmp == 3 and len(values["encrypt_key-group0"]) != 48:
                error = "group0 key length error"
                bflb_utils.printf(error)
                bflb_utils.set_error_code("0071")
                return bflb_utils.errorcode_msg()
            if tmp == 2 or tmp == 4 or tmp == 5 or tmp == 6:
                if len(values["encrypt_key-group0"]) != 64:
                    error = "group0 key length error"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0071")
                    return bflb_utils.errorcode_msg()
            if tmp != 0:
                if len(values["aes_iv-group0"]) != 32:
                    error = "group0 AES IV length error"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0072")
                    return bflb_utils.errorcode_msg()
                if values["aes_iv-group0"].endswith("00000000") is False:
                    error = "group0 AES IV should endswith 4 bytes zero"
                    bflb_utils.printf(error)
                    bflb_utils.set_error_code("0073")
                    return bflb_utils.errorcode_msg()
        if "key_sel-group0" in values.keys():
            bflb_utils.update_cfg(cfg, group0_section, "key_sel",
                                  self.key_sel.index(values["key_sel-group0"]))
        if "crc_ignore-group0" in values.keys():
            bflb_utils.update_cfg(cfg, group0_section, "crc_ignore",
                                  self.crc_ignore.index(values["crc_ignore-group0"]))
        if "hash_ignore-group0" in values.keys():
            bflb_utils.update_cfg(cfg, group0_section, "hash_ignore",
                                  self.hash_ignore.index(values["hash_ignore-group0"]))
        bflb_utils.update_cfg(cfg, group0_section, "m0_config_enable", "1")
        bflb_utils.update_cfg(cfg, group0_section, "m0_halt_cpu", "0")
        bflb_utils.update_cfg(cfg, group0_section, "img_len_cnt", "0x100")

        boot_entry = 0xA0000000
        if chiptype == "bl616":
            boot_entry = 0xA0000000
        elif chiptype == "wb03":
            boot_entry = 0x80000000
        bflb_utils.update_cfg(cfg, group0_section, "m0_image_address_offset", "0x0")
        bflb_utils.update_cfg(cfg, group0_section, "m0_boot_entry", "0x%X" % (boot_entry))
        bflb_utils.update_cfg(cfg, group0_section, "group_image_offset",
                              "0x%X" % (int(img_addr_offset.replace("0x", ""), 16)))
        if chiptype == "wb03":
            bflb_utils.update_cfg(cfg, group0_section, "custom_vendor_boot_offset",
                                  "0x%X" % (int(img_addr_offset.replace("0x", ""), 16)))

        if values["boot_src"].upper() == "UART/USB":
            bflb_utils.update_cfg(cfg, group0_section, "m0_boot_entry", img_addr_offset)
        cfg.write(bh_cfg_file, "w+")
        if values["boot_src"].upper() == "FLASH":
            bflb_efuse_boothd_create.bootheader_create_process(
                chipname, chiptype, bh_cfg_file, group0_bh_file, None,
                self.img_create_path + "/bootheader_dummy.bin")
            bflb_efuse_boothd_create.efuse_create_process(chipname, chiptype, bh_cfg_file,
                                                          efuse_file)
        else:
            bflb_efuse_boothd_create.bootheader_create_process(chipname, chiptype, bh_cfg_file,
                                                               group0_bh_file, None, True)
            bflb_efuse_boothd_create.efuse_create_process(chipname, chiptype, bh_cfg_file,
                                                          efuse_file)
        # create img_create_cfg.ini
        cfg = BFConfigParser()
        cfg.read(self.img_create_cfg)
        bflb_utils.update_cfg(cfg, group0_img_create_section, "boot_header_file", group0_bh_file)
        bflb_utils.update_cfg(cfg, group0_img_create_section, "efuse_file", efuse_file)
        bflb_utils.update_cfg(cfg, group0_img_create_section, "efuse_mask_file", efuse_mask_file)
        # create segheader
        segheader_group0 = self.img_create_path + segheader_file
        segheader = bytearray(12)
        if chiptype == "bl616":
            img_addr_offset = self.bl616_img_addr_remap(img_addr_offset)
        segheader[0:4] = bflb_utils.int_to_4bytearray_l(int(img_addr_offset.replace("0x", ""), 16))
        segfp = open(self.img_create_path + segheader_file, 'wb+')
        segfp.write(segheader)
        segfp.close()

        bflb_utils.update_cfg(cfg, group0_img_create_section, "segheader_file", segheader_group0)
        bflb_utils.update_cfg(cfg, group0_img_create_section, "segdata_file", group0_img)
        if "encrypt_key-group0" in values.keys():
            bflb_utils.update_cfg(cfg, group0_img_create_section, "aes_key_org",
                                  values["encrypt_key-group0"])
        if "aes_iv-group0" in values.keys():
            bflb_utils.update_cfg(cfg, group0_img_create_section, "aes_iv",
                                  values["aes_iv-group0"])
        if "public_key_cfg-group0" in values.keys():
            bflb_utils.update_cfg(cfg, group0_img_create_section, "publickey_file",
                                  values["public_key_cfg-group0"])
        if "private_key_cfg-group0" in values.keys():
            bflb_utils.update_cfg(cfg, group0_img_create_section, "privatekey_file_uecc",
                                  values["private_key_cfg-group0"])
        bflb_utils.update_cfg(cfg, group0_img_create_section, "bootinfo_file",
                              group0_bootinfo_file)
        bflb_utils.update_cfg(cfg, group0_img_create_section, "img_file", group0_img_output_file)
        bflb_utils.update_cfg(cfg, group0_img_create_section, "whole_img_file",
                              group0_img_output_file.replace(".bin", "_if.bin"))
        cfg.write(self.img_create_cfg, "w+")
        # create img
        if values["boot_src"].upper() == "FLASH":
            options = ["--image=media", "--group=all", "--signer=none"]
            if security_save_efuse is True:
                options.extend(["--security=efuse"])
            args = parser_image.parse_args(options)
            res = bflb_img_create.img_create(args, chipname, chiptype, self.img_create_path,
                                             self.img_create_cfg)
            if res is not True:
                bflb_utils.set_error_code("0060")
                return bflb_utils.errorcode_msg()
        else:
            options = ["--image=if", "--group=all", "--signer=none"]
            if security_save_efuse is True:
                options.extend(["--security=efuse"])
            args = parser_image.parse_args(options)
            res = bflb_img_create.img_create(args, chipname, chiptype, self.img_create_path,
                                             self.img_create_cfg)
            if res is not True:
                bflb_utils.set_error_code("0060")
                return bflb_utils.errorcode_msg()
        os.remove(self.img_create_path + segheader_file)
        if os.path.exists(self.img_create_path + '/bootheader_dummy.bin'):
            os.remove(self.img_create_path + "/bootheader_dummy.bin")
        return True

    def program_default_img(self, values, callback=None):
        options = ""
        ret = None
        create_output_path = os.path.relpath(self.img_create_path, app_path)
        if values["img_file"] == "" and values["dl_chiperase"] == "True":
            bflb_utils.printf("Erase Flash")
            # program flash,create eflash_loader_cfg.ini
            cfg = BFConfigParser()
            if os.path.isfile(self.eflash_loader_cfg_tmp) is False:
                shutil.copyfile(self.eflash_loader_cfg, self.eflash_loader_cfg_tmp)
            cfg.read(self.eflash_loader_cfg_tmp)
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "interface", values["dl_device"].lower())
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "device", values["dl_comport"])
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "speed_uart_load", values["dl_comspeed"])
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "speed_jlink", values["dl_jlinkspeed"])
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "erase", "2")
            eflash_loader_bin = os.path.join(
                chip_path, self.chipname, "eflash_loader/" + get_eflash_loader(values["dl_xtal"]))
            if "dl_verify" in values.keys():
                if values["dl_verify"] == "True":
                    bflb_utils.update_cfg(cfg, "LOAD_CFG", "verify", "1")
                else:
                    bflb_utils.update_cfg(cfg, "LOAD_CFG", "verify", "0")
            if cfg.has_option("LOAD_CFG", "xtal_type"):
                bflb_utils.update_cfg(cfg, "LOAD_CFG", "xtal_type",
                                      self.xtal_type_.index(values["xtal_type"]))
            cfg.write("eflash_loader_tmp.ini", "w+")
            options = ["--erase", "--end=0", "-c", "eflash_loader_tmp.ini"]
        else:
            # decide file name
            if values["img_type"] == "SingleCPU":
                bootinfo_file = create_output_path + "/bootinfo.bin"
                img_output_file = create_output_path + "/img.bin"
                whole_img_output_file = create_output_path + "/whole_img.bin"
            elif values["img_type"] == "BLSP_Boot2":
                bootinfo_file = create_output_path + "/bootinfo_blsp_boot2.bin"
                img_output_file = create_output_path + "/img_blsp_boot2.bin"
                whole_img_output_file = create_output_path + "/whole_img_blsp_boot2.bin"
            elif values["img_type"] == "CPU0":
                bootinfo_file = create_output_path + "/bootinfo_cpu0.bin"
                img_output_file = create_output_path + "/img_cpu0.bin"
                whole_img_output_file = create_output_path + "/whole_img_cpu0.bin"
            elif values["img_type"] == "CPU1":
                bootinfo_file = create_output_path + "/bootinfo_cpu1.bin"
                img_output_file = create_output_path + "/img_cpu1.bin"
                whole_img_output_file = create_output_path + "/whole_img_cpu1.bin"
            # uart download
            if values["boot_src"].upper() == "UART/SDIO" or values["boot_src"].upper(
            ) == "UART/USB":
                cfg = BFConfigParser()
                if os.path.isfile(self.eflash_loader_cfg_tmp) is False:
                    shutil.copyfile(self.eflash_loader_cfg, self.eflash_loader_cfg_tmp)
                cfg.read(self.eflash_loader_cfg_tmp)
                boot_speed = int(cfg.get("LOAD_CFG", "speed_uart_boot"))
                if values["img_type"] == "RAW":
                    ret = self.img_loader_thread(values["dl_comport"], boot_speed, boot_speed,
                                                 values["img_file"], None, callback)
                else:
                    ret = self.img_loader_thread(values["dl_comport"], boot_speed, boot_speed,
                                                 img_output_file.replace(".bin", "_if.bin"), None,
                                                 callback)
                if ret is False:
                    ret = "Img load fail"
                return ret
            # program flash,create eflash_loader_cfg.ini
            cfg = BFConfigParser()
            if os.path.isfile(self.eflash_loader_cfg_tmp) is False:
                shutil.copyfile(self.eflash_loader_cfg, self.eflash_loader_cfg_tmp)
            cfg.read(self.eflash_loader_cfg_tmp)
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "interface", values["dl_device"].lower())
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "device", values["dl_comport"])
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "speed_uart_load", values["dl_comspeed"])
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "speed_jlink", values["dl_jlinkspeed"])
            if values["dl_chiperase"] == "True":
                bflb_utils.update_cfg(cfg, "LOAD_CFG", "erase", "2")
            else:
                bflb_utils.update_cfg(cfg, "LOAD_CFG", "erase", "1")
            if "dl_verify" in values.keys():
                if values["dl_verify"] == "True":
                    bflb_utils.update_cfg(cfg, "LOAD_CFG", "verify", "1")
                else:
                    bflb_utils.update_cfg(cfg, "LOAD_CFG", "verify", "0")

            eflash_loader_bin = os.path.join(
                chip_path, self.chipname, "eflash_loader/" + get_eflash_loader(values["dl_xtal"]))

            if cfg.has_option("LOAD_CFG", "xtal_type"):
                bflb_utils.update_cfg(cfg, "LOAD_CFG", "xtal_type",
                                      self.xtal_type_.index(values["xtal_type"]))
            if values["img_type"] == "RAW":
                img_raw_tmp = os.path.join(self.img_create_path, 'img_raw_tmp.bin')
                shutil.copyfile(values["img_file"], img_raw_tmp)
                bflb_utils.update_cfg(cfg, "FLASH_CFG", "file", img_raw_tmp)
                bflb_utils.update_cfg(cfg, "FLASH_CFG", "address",
                                      values["img_addr"].replace("0x", ""))
            else:
                bind_bootinfo = True
                fw_with_bootinfo = False
                if bind_bootinfo is True:
                    img_addr = int(values["img_addr"].replace("0x", ""), 16)
                    bootinfo_filedata = self.bl_get_file_data([bootinfo_file])[0]
                    filedata = self.bl_get_file_data([img_output_file])[0]
                    if bootinfo_filedata[0:4] == filedata[0:4]:
                        whole_img_len = os.path.getsize(os.path.join(app_path, img_output_file))
                        whole_img_data = self.bl_create_flash_default_data(whole_img_len)
                        whole_img_data = filedata
                        fw_with_bootinfo = True
                    else:
                        whole_img_len = img_addr + os.path.getsize(
                            os.path.join(app_path, img_output_file))
                        whole_img_data = self.bl_create_flash_default_data(whole_img_len)
                        whole_img_data[0:len(bootinfo_filedata)] = bootinfo_filedata
                        whole_img_data[img_addr:img_addr + len(filedata)] = filedata
                        fw_with_bootinfo = False
                    fp = open(os.path.join(app_path, whole_img_output_file), 'wb+')
                    fp.write(whole_img_data)
                    fp.close()
                    # bflb_utils.update_cfg(cfg, "FLASH_CFG", "file", convert_path(whole_img_output_file))
                    # bflb_utils.update_cfg(cfg, "FLASH_CFG", "address", values["bootinfo_addr"].replace("0x", ""))
                if fw_with_bootinfo is True:
                    bflb_utils.update_cfg(cfg, "FLASH_CFG", "file", convert_path(img_output_file))
                    bflb_utils.update_cfg(cfg, "FLASH_CFG", "address",
                                          values["bootinfo_addr"].replace("0x", ""))
                else:
                    bflb_utils.update_cfg(
                        cfg, "FLASH_CFG", "file",
                        convert_path(bootinfo_file) + " " + convert_path(img_output_file))
                    bflb_utils.update_cfg(
                        cfg, "FLASH_CFG", "address", values["bootinfo_addr"].replace("0x", "") +
                        " " + values["img_addr"].replace("0x", ""))
            cfg.write(self.eflash_loader_cfg_tmp, "w+")
            # call eflash_loader
            if values["dl_device"].lower() == "uart":
                options = [
                    "--write", "--flash", "-p", values["dl_comport"], "-c",
                    self.eflash_loader_cfg_tmp
                ]
            else:
                options = ["--write", "--flash", "-c", self.eflash_loader_cfg_tmp]
            if cfg.has_option("LOAD_CFG", "boot2_isp_mode"):
                boot2_isp_mode = cfg.get("LOAD_CFG", "boot2_isp_mode")
                if int(boot2_isp_mode) == 1:
                    options.extend(["--isp"])
            if  "encrypt_key" in values.keys() or\
                "encrypt_type" in values.keys() or\
                "aes_iv" in values.keys() or\
                "sign_type" in values.keys() or\
                "public_key_cfg" in values.keys() or\
                "private_key_cfg" in values.keys():
                if (values["encrypt_type"] != "None" and\
                    values["encrypt_key"] != "" and\
                    values["aes_iv"] != "") or\
                   (values["sign_type"] != "None" and\
                    values["public_key_cfg"] != "" and\
                    values["private_key_cfg"] != ""):
                    if values["boot_src"].upper() == "FLASH":
                        options.extend(["--efuse", "--createcfg=" + self.img_create_cfg])
                        self.efuse_load_en = True
        ret = bflb_img_create.compress_dir(self.chipname, "img_create_mcu", self.efuse_load_en)
        if ret is not True:
            return bflb_utils.errorcode_msg()
        if not values["dl_comport"] and values["dl_device"].lower() == "uart":
            error = '{"ErrorCode":"FFFF","ErrorMsg":"BFLB INTERFACE HAS NO COM PORT"}'
            bflb_utils.printf(error)
            return error
        args = parser_eflash.parse_args(options)
        ret = self.eflash_loader_thread(args, eflash_loader_bin, callback,
                                        self.create_img_callback)
        return ret

    def program_bl808_bl628_img(self, values, callback=None):
        options = ""
        ret = None
        create_output_path = os.path.relpath(self.img_create_path, app_path)
        group0_used = False
        group1_used = False
        group0_img_start = 0xFFFFFFFF
        group1_img_start = 0xFFFFFFFF
        group0_bootinfo_file = create_output_path + "/bootinfo_group0.bin"
        group0_img_output_file = create_output_path + "/img_group0.bin"
        group1_bootinfo_file = create_output_path + "/bootinfo_group1.bin"
        group1_img_output_file = create_output_path + "/img_group1.bin"
        whole_img_output_file = create_output_path + "/whole_img.bin"
        if self.chiptype == "bl628":
            cpu_num = 2
        else:
            cpu_num = 3
        for index in range(cpu_num):
            num = str(index + 1)
            if values["img%s_group" % num] != "unused":
                img_start = int(values["img%s_addr" % num].replace("0x", ""), 16)
                if values["img%s_group" % num] == "group0":
                    if group0_img_start > img_start:
                        group0_img_start = int(values["img%s_addr" % num].replace("0x", ""), 16)
                elif values["img%s_group" % num] == "group1":
                    if group1_img_start > img_start:
                        group1_img_start = int(values["img%s_addr" % num].replace("0x", ""), 16)
        if self.chiptype == "bl628":
            if values["img1_group"] == "group0" or\
                values["img2_group"] == "group0":
                group0_used = True
                group0_img_start &= 0x3FFFFFF
            else:
                group0_img_start = 0
            if values["img1_group"] == "group1" or\
                values["img2_group"] == "group1":
                group1_used = True
                group1_img_start &= 0x3FFFFFF
            else:
                group1_img_start = 0
        else:
            if values["img1_group"] == "group0" or\
                values["img2_group"] == "group0" or\
                values["img3_group"] == "group0":
                group0_used = True
                group0_img_start &= 0x3FFFFFF
            else:
                group0_img_start = 0
            if values["img1_group"] == "group1" or\
                values["img2_group"] == "group1" or\
                values["img3_group"] == "group1":
                group1_used = True
                group1_img_start &= 0x3FFFFFF
            else:
                group1_img_start = 0
        # uart download
        if values["boot_src"].upper() == "UART/USB":
            cfg = BFConfigParser()
            if os.path.isfile(self.eflash_loader_cfg_tmp) is False:
                shutil.copyfile(self.eflash_loader_cfg, self.eflash_loader_cfg_tmp)
            cfg.read(self.eflash_loader_cfg_tmp)
            boot_speed = int(cfg.get("LOAD_CFG", "speed_uart_boot"))
            if values["img_type"] == "RAW":
                ret = self.img_loader_thread(values["dl_comport"], boot_speed, boot_speed,
                                             values["img1_file"], None, callback)
            else:
                if group0_used is True and group1_used is False:
                    ret = self.img_loader_thread(values["dl_comport"], boot_speed, boot_speed,
                                                 group0_img_output_file.replace(".bin", "_if.bin"),
                                                 None, callback)
                elif group0_used is False and group1_used is True:
                    ret = self.img_loader_thread(values["dl_comport"], boot_speed, boot_speed,
                                                 group1_img_output_file.replace(".bin", "_if.bin"),
                                                 None, callback)
                elif group0_used is True and group1_used is True:
                    ret = self.img_loader_thread(values["dl_comport"], boot_speed, boot_speed,
                                                 group0_img_output_file.replace(".bin", "_if.bin"),
                                                 group1_img_output_file.replace(".bin", "_if.bin"),
                                                 callback)
            if ret is False:
                ret = "Img load fail"
            return ret
        # program flash, create eflash_loader_cfg.ini
        cfg = BFConfigParser()
        if os.path.isfile(self.eflash_loader_cfg_tmp) is False:
            shutil.copyfile(self.eflash_loader_cfg, self.eflash_loader_cfg_tmp)
        cfg.read(self.eflash_loader_cfg_tmp)
        bflb_utils.update_cfg(cfg, "LOAD_CFG", "interface", values["dl_device"].lower())
        bflb_utils.update_cfg(cfg, "LOAD_CFG", "device", values["dl_comport"])
        bflb_utils.update_cfg(cfg, "LOAD_CFG", "speed_uart_load", values["dl_comspeed"])
        bflb_utils.update_cfg(cfg, "LOAD_CFG", "speed_jlink", values["dl_jlinkspeed"])
        if values["dl_chiperase"] == "True":
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "erase", "2")
        else:
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "erase", "1")
        if "dl_verify" in values.keys():
            if values["dl_verify"] == "True":
                bflb_utils.update_cfg(cfg, "LOAD_CFG", "verify", "1")
            else:
                bflb_utils.update_cfg(cfg, "LOAD_CFG", "verify", "0")

        eflash_loader_bin = os.path.join(chip_path, self.chipname,
                                         "eflash_loader/" + get_eflash_loader(values["dl_xtal"]))

        if cfg.has_option("LOAD_CFG", "xtal_type"):
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "xtal_type",
                                  self.xtal_type_.index(values["xtal_type"]))
        if values["img_type"] == "RAW":
            bflb_utils.update_cfg(cfg, "FLASH_CFG", "file", values["img1_file"])
            bflb_utils.update_cfg(cfg, "FLASH_CFG", "address",
                                  values["img1_addr"].replace("0x", ""))
        else:
            read_data = self.bl_get_file_data([group0_bootinfo_file])[0]
            if self.chiptype == "bl628":
                group0_img_offset = bflb_utils.bytearray_to_int(
                    bflb_utils.bytearray_reverse(read_data[128:132]))
                group0_img_len = bflb_utils.bytearray_to_int(
                    bflb_utils.bytearray_reverse(read_data[136:140]))
                read_data = self.bl_get_file_data([group1_bootinfo_file])[0]
                group1_img_offset = bflb_utils.bytearray_to_int(
                    bflb_utils.bytearray_reverse(read_data[128:132]))
                group1_img_len = bflb_utils.bytearray_to_int(
                    bflb_utils.bytearray_reverse(read_data[136:140]))
            else:
                group0_img_offset = bflb_utils.bytearray_to_int(
                    bflb_utils.bytearray_reverse(read_data[132:136]))
                group0_img_len = bflb_utils.bytearray_to_int(
                    bflb_utils.bytearray_reverse(read_data[140:144]))
                read_data = self.bl_get_file_data([group1_bootinfo_file])[0]
                group1_img_offset = bflb_utils.bytearray_to_int(
                    bflb_utils.bytearray_reverse(read_data[132:136]))
                group1_img_len = bflb_utils.bytearray_to_int(
                    bflb_utils.bytearray_reverse(read_data[140:144]))
            bind_bootinfo = True
            group0_fw_with_bootinfo = False
            group1_fw_with_bootinfo = False
            if bind_bootinfo is True:
                whole_img_len = 0
                if group0_img_offset + group0_img_len < group1_img_offset + group1_img_len \
                   and group1_used is True:
                    whole_img_len = group1_img_offset + group1_img_len + group1_img_start
                else:
                    whole_img_len = group0_img_offset + group0_img_len + group0_img_start
                whole_img_data = self.bl_create_flash_default_data(whole_img_len)

                if group0_img_len > 0:
                    group0_bootinfo_filedata = self.bl_get_file_data([group0_bootinfo_file])[0]

                if group1_img_len > 0:
                    group1_bootinfo_filedata = self.bl_get_file_data([group1_bootinfo_file])[0]

                if group0_img_len > 0:
                    group0_filedata = self.bl_get_file_data([group0_img_output_file])[0]
                    if group0_img_len != len(group0_filedata):
                        bflb_utils.printf("group0 img len error, get %d except %d" %
                                          (group0_img_len, len(group0_filedata)))
                    if group0_bootinfo_filedata[0:4] == group0_filedata[0:4]:
                        whole_img_data = group0_filedata
                        group0_fw_with_bootinfo = True
                    else:
                        whole_img_data[0:len(group0_bootinfo_filedata)] = group0_bootinfo_filedata
                        whole_img_data[group0_img_offset+group0_img_start : \
                                    group0_img_offset+len(group0_filedata)+group0_img_start] = group0_filedata
                        group0_fw_with_bootinfo = False

                if group1_img_len > 0:
                    group1_filedata = self.bl_get_file_data([group1_img_output_file])[0]
                    if group1_img_len != len(group1_filedata):
                        bflb_utils.printf("group1 img len error, get %d except %d" %
                                          (group1_img_len, len(group1_filedata)))
                    if group1_bootinfo_filedata[0:4] == group1_filedata[0:4]:
                        whole_img_data = group1_filedata
                        group1_fw_with_bootinfo = True
                    else:
                        whole_img_data[0x1000:len(group1_bootinfo_filedata
                                                 )] = group1_bootinfo_filedata
                        whole_img_data[group1_img_offset+group1_img_start : \
                                    group1_img_offset+len(group1_filedata)+group1_img_start] = group1_filedata
                        group1_fw_with_bootinfo = False

                fp = open(os.path.join(app_path, whole_img_output_file), 'wb+')
                fp.write(whole_img_data)
                fp.close()
                # bflb_utils.update_cfg(cfg, "FLASH_CFG", "file", convert_path(whole_img_output_file))
                # bflb_utils.update_cfg(cfg, "FLASH_CFG", "address", "00000000")
            file_list = ""
            addr_list = ""
            group0_bootinfo_addr = 0x0
            group1_bootinfo_addr = 0x1000
            group0_img_offset += group0_img_start
            group1_img_offset += group1_img_start
            if group0_used is True and group1_used is False:
                if group0_fw_with_bootinfo is True:
                    file_list = convert_path(group0_img_output_file)
                    addr_list = "%x" % (group0_bootinfo_addr)
                else:
                    file_list = convert_path(group0_bootinfo_file) + " "\
                                + convert_path(group0_img_output_file)
                    addr_list = "%x %x" % (group0_bootinfo_addr, group0_img_offset)
            elif group0_used is False and group1_used is True:
                if group1_fw_with_bootinfo is True:
                    file_list = convert_path(group1_img_output_file)
                    addr_list = "%x" % (group1_bootinfo_addr)
                else:
                    file_list = convert_path(group1_bootinfo_file) + " "\
                                + convert_path(group1_img_output_file)
                    addr_list = "%x %x" % (group1_bootinfo_addr, group1_img_offset)
            elif group0_used is True and group1_used is True:
                if group0_fw_with_bootinfo is True:
                    file_list = convert_path(group0_img_output_file)
                    addr_list = "%x" % (group0_bootinfo_addr)
                else:
                    file_list = convert_path(group0_bootinfo_file) + " "\
                                + convert_path(group1_bootinfo_file) + " "\
                                + convert_path(group0_img_output_file) + " "\
                                + convert_path(group1_img_output_file)
                    addr_list = "%x %x %x %x" % (group0_bootinfo_addr, group1_bootinfo_addr,
                                                 group0_img_offset, group1_img_offset)
            bflb_utils.update_cfg(cfg, "FLASH_CFG", "file", file_list)
            bflb_utils.update_cfg(cfg, "FLASH_CFG", "address", addr_list.replace("0x", ""))
        cfg.write(self.eflash_loader_cfg_tmp, "w+")
        # call eflash_loader
        if values["dl_device"].lower() == "uart":
            options = [
                "--write", "--flash", "-p", values["dl_comport"], "-c", self.eflash_loader_cfg_tmp
            ]
        else:
            options = ["--write", "--flash", "-c", self.eflash_loader_cfg_tmp]
        if cfg.has_option("LOAD_CFG", "boot2_isp_mode"):
            boot2_isp_mode = cfg.get("LOAD_CFG", "boot2_isp_mode")
            if int(boot2_isp_mode) == 1:
                options.extend(["--isp"])
        if  "encrypt_key-group0" in values.keys() or\
            "encrypt_key-group1" in values.keys() or\
            "encrypt_type-group0" in values.keys() or\
            "encrypt_type-group1" in values.keys() or\
            "aes_iv-group0" in values.keys() or\
            "aes_iv-group1" in values.keys() or\
            "sign_type-group0" in values.keys() or\
            "sign_type_group1" in values.keys() or\
            "public_key_cfg-group0"in values.keys() or\
            "public_key_cfg-group1"in values.keys() or\
            "private_key_cfg-group0" in values.keys() or\
            "private_key_cfg-group1" in values.keys():
            if (values["encrypt_type-group0"] != "None" and\
                values["encrypt_key-group0"] != "" and\
                values["aes_iv-group0"] != "") or\
               (values["encrypt_type-group1"] != "None" and\
                values["encrypt_key-group1"] != "" and\
                values["aes_iv-group1"] != "") or\
               (values["sign_type-group0"] != "None" and\
                values["public_key_cfg-group0"] != "" and\
                values["private_key_cfg-group0"] != "") or\
               (values["sign_type-group1"] != "None" and\
                values["public_key_cfg-group1"] != "" and\
                values["private_key_cfg-group1"] != ""):
                if values["boot_src"].upper() == "FLASH":
                    options.extend(["--efuse", "--createcfg=" + self.img_create_cfg])
                    self.efuse_load_en = True
        ret = bflb_img_create.compress_dir(self.chipname, "img_create_mcu", self.efuse_load_en)
        if ret is not True:
            return bflb_utils.errorcode_msg()
        if not values["dl_comport"] and values["dl_device"].lower() == "uart":
            error = '{"ErrorCode":"FFFF","ErrorMsg":"BFLB INTERFACE HAS NO COM PORT"}'
            bflb_utils.printf(error)
            return error
        args = parser_eflash.parse_args(options)
        ret = self.eflash_loader_thread(args, eflash_loader_bin, callback,
                                        self.create_img_callback)
        return ret

    def program_bl616_img(self, values, callback=None):
        options = ""
        ret = None
        create_output_path = os.path.relpath(self.img_create_path, app_path)
        group0_used = True
        group0_bootinfo_file = create_output_path + "/bootinfo.bin"
        group0_img_output_file = create_output_path + "/img.bin"
        whole_img_output_file = create_output_path + "/whole_img.bin"
        # uart download
        if values["boot_src"].upper() == "UART/USB":
            cfg = BFConfigParser()
            if os.path.isfile(self.eflash_loader_cfg_tmp) is False:
                shutil.copyfile(self.eflash_loader_cfg, self.eflash_loader_cfg_tmp)
            cfg.read(self.eflash_loader_cfg_tmp)
            boot_speed = int(cfg.get("LOAD_CFG", "speed_uart_boot"))
            if values["img_type"] == "RAW":
                ret = self.img_loader_thread(values["dl_comport"], boot_speed, boot_speed,
                                             values["img1_file"], None, callback)
            else:
                ret = self.img_loader_thread(values["dl_comport"], boot_speed, boot_speed,
                                             group0_img_output_file.replace(".bin", "_if.bin"),
                                             None, callback)
            if ret is False:
                ret = "Img load fail"
            return ret
        # program flash, create eflash_loader_cfg.ini
        cfg = BFConfigParser()
        if os.path.isfile(self.eflash_loader_cfg_tmp) is False:
            shutil.copyfile(self.eflash_loader_cfg, self.eflash_loader_cfg_tmp)
        cfg.read(self.eflash_loader_cfg_tmp)
        bflb_utils.update_cfg(cfg, "LOAD_CFG", "interface", values["dl_device"].lower())
        bflb_utils.update_cfg(cfg, "LOAD_CFG", "device", values["dl_comport"])
        bflb_utils.update_cfg(cfg, "LOAD_CFG", "speed_uart_load", values["dl_comspeed"])
        bflb_utils.update_cfg(cfg, "LOAD_CFG", "speed_jlink", values["dl_jlinkspeed"])
        if values["dl_chiperase"] == "True":
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "erase", "2")
        else:
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "erase", "1")
        if "dl_verify" in values.keys():
            if values["dl_verify"] == "True":
                bflb_utils.update_cfg(cfg, "LOAD_CFG", "verify", "1")
            else:
                bflb_utils.update_cfg(cfg, "LOAD_CFG", "verify", "0")

        eflash_loader_bin = os.path.join(chip_path, self.chipname,
                                         "eflash_loader/" + get_eflash_loader(values["dl_xtal"]))

        if cfg.has_option("LOAD_CFG", "xtal_type"):
            bflb_utils.update_cfg(cfg, "LOAD_CFG", "xtal_type",
                                  self.xtal_type_.index(values["xtal_type"]))
        if values["img_type"] == "RAW":
            bflb_utils.update_cfg(cfg, "FLASH_CFG", "file", values["img1_file"])
            bflb_utils.update_cfg(cfg, "FLASH_CFG", "address",
                                  values["img1_addr"].replace("0x", ""))
        else:
            start_pos = 0
            if self.chiptype == "wb03":
                start_pos = 208
            read_data = self.bl_get_file_data([group0_bootinfo_file])[0]
            group0_img_offset = bflb_utils.bytearray_to_int(
                bflb_utils.bytearray_reverse(read_data[124 + start_pos:128 + start_pos]))
            group0_img_len = bflb_utils.bytearray_to_int(
                bflb_utils.bytearray_reverse(read_data[132 + start_pos:136 + start_pos]))
            bind_bootinfo = True
            fw_with_bootinfo = False
            if bind_bootinfo is True:
                bootinfo_filedata = self.bl_get_file_data([group0_bootinfo_file])[0]
                filedata = self.bl_get_file_data([group0_img_output_file])[0]
                if group0_img_len != len(filedata):
                    bflb_utils.printf("group0 img len error, get %d except %d" %
                                      (group0_img_len, len(filedata)))
                if bootinfo_filedata[0:4] == filedata[0:4]:
                    whole_img_len = group0_img_len
                    whole_img_data = self.bl_create_flash_default_data(whole_img_len)
                    whole_img_data = filedata
                    fw_with_bootinfo = True
                else:
                    whole_img_len = group0_img_offset + group0_img_len
                    whole_img_data = self.bl_create_flash_default_data(whole_img_len)
                    whole_img_data[0:len(bootinfo_filedata)] = bootinfo_filedata
                    whole_img_data[group0_img_offset:group0_img_offset + len(filedata)] = filedata
                    fw_with_bootinfo = False

                fp = open(os.path.join(app_path, whole_img_output_file), 'wb+')
                fp.write(whole_img_data)
                fp.close()
                # bflb_utils.update_cfg(cfg, "FLASH_CFG", "file", convert_path(whole_img_output_file))
                # bflb_utils.update_cfg(cfg, "FLASH_CFG", "address", "00000000")
            if fw_with_bootinfo is True:
                file_list = convert_path(group0_img_output_file)
                addr_list = "00000000"
            else:
                file_list = convert_path(group0_bootinfo_file) + " " + convert_path(
                    group0_img_output_file)
                addr_list = "00000000 %x" % (group0_img_offset)
            bflb_utils.update_cfg(cfg, "FLASH_CFG", "file", file_list)
            bflb_utils.update_cfg(cfg, "FLASH_CFG", "address", addr_list.replace("0x", ""))
        cfg.write(self.eflash_loader_cfg_tmp, "w+")
        # call eflash_loader
        if values["dl_device"].lower() == "uart":
            options = [
                "--write", "--flash", "-p", values["dl_comport"], "-c", self.eflash_loader_cfg_tmp
            ]
        else:
            options = ["--write", "--flash", "-c", self.eflash_loader_cfg_tmp]
        if cfg.has_option("LOAD_CFG", "boot2_isp_mode"):
            boot2_isp_mode = cfg.get("LOAD_CFG", "boot2_isp_mode")
            if int(boot2_isp_mode) == 1:
                options.extend(["--isp"])
        if  "encrypt_key-group0" in values.keys() or\
            "encrypt_type-group0" in values.keys() or\
            "aes_iv-group0" in values.keys() or\
            "sign_type-group0" in values.keys() or\
            "public_key_cfg-group0"in values.keys() or\
            "private_key_cfg-group0" in values.keys():
            if (values["encrypt_type-group0"] != "None" and\
                values["encrypt_key-group0"] != "" and\
                values["aes_iv-group0"] != "") or\
               (values["sign_type-group0"] != "None" and\
                values["public_key_cfg-group0"] != "" and\
                values["private_key_cfg-group0"] != ""):
                if values["boot_src"].upper() == "FLASH":
                    options.extend(["--efuse", "--createcfg=" + self.img_create_cfg])
                    self.efuse_load_en = True
        ret = bflb_img_create.compress_dir(self.chipname, "img_create_mcu", self.efuse_load_en)
        if ret is not True:
            return bflb_utils.errorcode_msg()
        if not values["dl_comport"] and values["dl_device"].lower() == "uart":
            error = '{"ErrorCode":"FFFF","ErrorMsg":"BFLB INTERFACE HAS NO COM PORT"}'
            bflb_utils.printf(error)
            return error
        args = parser_eflash.parse_args(options)
        ret = self.eflash_loader_thread(args, eflash_loader_bin, callback,
                                        self.create_img_callback)
        return ret

    def create_img(self, chipname, chiptype, values):
        # basic check
        self.config = values
        error = True
        try:
            if chiptype == "bl808" or chiptype == "bl628":
                error = self.create_bl808_bl628_img(chipname, chiptype, values)
                return error
            elif chiptype == "bl616" or chiptype == "wb03":
                error = self.create_bl616_img(chipname, chiptype, values)
                return error
            else:
                error = self.create_default_img(chipname, chiptype, values)
                return error
        except Exception as e:
            error = str(e)
            bflb_utils.printf(error)
            bflb_utils.set_error_code("0075")
            traceback.print_exc(limit=5, file=sys.stdout)
        finally:
            return error

    def program_img_thread(self, values, callback=None):
        ret = None
        bflb_utils.printf("========= eflash loader config =========")
        try:
            if not values["dl_comspeed"].isdigit() or not values["dl_jlinkspeed"].isdigit():
                ret = '{"ErrorCode":"FFFF","ErrorMsg":"BAUDRATE MUST BE DIGIT"}'
                return ret
            if self.chiptype == "bl60x" \
            or self.chiptype == "bl602" \
            or self.chiptype == "bl702" \
            or self.chiptype == "bl702l":
                ret = self.program_default_img(values, callback)
            elif self.chiptype == "bl808" or self.chiptype == "bl628":
                ret = self.program_bl808_bl628_img(values, callback)
            else:
                ret = self.program_bl616_img(values, callback)
        except Exception as e:
            ret = str(e)
            traceback.print_exc(limit=5, file=sys.stdout)
        finally:
            return ret

    def create_img_callback(self):
        error = None
        values = self.config
        error = self.create_img(self.chipname, self.chiptype, values)
        if error:
            bflb_utils.printf(error)
        return error

    def log_read_thread(self):
        try:
            ret, data = self.eflash_loader_t.log_read_process()
            self.eflash_loader_t.close_port()
            return ret, data
        except Exception as e:
            traceback.print_exc(limit=10, file=sys.stdout)
            ret = str(e)
            return False, ret


def get_value(args):
    if args.firmware:
        firmware = args.firmware.replace('~', expanduser("~"))
    else:
        firmware = None
    if not firmware or not os.path.exists(firmware):
        bflb_utils.printf("firmware is not existed")
        sys.exit(1)

    if args.firmware_group1:
        firmware_group1 = args.firmware_group1.replace('~', expanduser("~"))
    else:
        firmware_group1 = None

    if args.dts:
        dts = args.dts.replace('~', expanduser("~"))
        if not os.path.exists(dts):
            bflb_utils.printf("device tree is not existed")
            sys.exit(1)
    else:
        dts = None

    chipname = args.chipname
    chiptype = gol.dict_chip_cmd.get(chipname, "unkown chip type")
    config = dict()
    config.setdefault('xtal_type', 'XTAL_38.4M')
    config.setdefault('pll_clk', '160M')
    config.setdefault('boot_src', 'FLASH')
    config.setdefault('img_type', 'SingleCPU')
    config.setdefault('encrypt_type', 'None')
    config.setdefault('key_sel', '0')
    config.setdefault('cache_way_disable', 'None')
    config.setdefault('sign_type', 'None')
    config.setdefault('crc_ignore', 'False')
    config.setdefault('hash_ignore', 'False')
    config.setdefault('encrypt_key', '')
    config.setdefault('aes_iv', '')
    config.setdefault('public_key_cfg', '')
    config.setdefault('private_key_cfg', '')
    config.setdefault('bootinfo_addr', '0x0')
    config["dl_device"] = args.interface.lower()
    config["dl_comport"] = args.port
    config["dl_comspeed"] = str(args.baudrate)
    config["dl_jlinkspeed"] = str(args.baudrate)
    config["img_file"] = firmware
    config["img_addr"] = "0x" + args.addr.replace("0x", "")
    config["device_tree"] = dts

    if chiptype == "bl602":
        if not args.xtal:
            config["dl_xtal"] = "40M"
            config["xtal_type"] = 'XTAL_40M'
            bflb_utils.printf("Default xtal is 40M")
        else:
            config["dl_xtal"] = args.xtal
            config["xtal_type"] = 'XTAL_' + args.xtal
        if not args.flashclk:
            config["flash_clk_type"] = "XTAL"
            bflb_utils.printf("Default flash clock is XTAL")
        else:
            config["flash_clk_type"] = args.flashclk
        if not args.pllclk:
            config["pll_clk"] = "160M"
            bflb_utils.printf("Default pll clock is 160M")
        else:
            config["pll_clk"] = args.pllclk
        if not args.bootsrc:
            config["boot_src"] = "FLASH"
            bflb_utils.printf("Default boot source is flash")
        else:
            config["boot_src"] = args.bootsrc
    elif chiptype == "bl702" or chiptype == "bl702l":
        config["key_sel"] = "1"
        if not args.xtal:
            config["dl_xtal"] = "32M"
            config["xtal_type"] = 'XTAL_32M'
            bflb_utils.printf("Default xtal is 32M")
        else:
            config["dl_xtal"] = args.xtal
            config["xtal_type"] = 'XTAL_' + args.xtal
        if not args.flashclk:
            config["flash_clk_type"] = "XCLK"
            bflb_utils.printf("Default flash clock is XCLK")
        else:
            config["flash_clk_type"] = args.flashclk
        if not args.pllclk:
            config["pll_clk"] = "144M"
            bflb_utils.printf("Default pll clock is 144M")
        else:
            config["pll_clk"] = args.pllclk
        if not args.bootsrc:
            config["boot_src"] = "FLASH"
            bflb_utils.printf("Default boot source is flash")
        else:
            config["boot_src"] = args.bootsrc
    elif chiptype == "bl60x":
        if not args.xtal:
            config["dl_xtal"] = "38.4M"
            config["xtal_type"] = 'XTAL_38.4M'
            bflb_utils.printf("Default xtal is 38.4M")
        else:
            config["dl_xtal"] = args.xtal
            config["xtal_type"] = 'XTAL_' + args.xtal
        if not args.flashclk:
            config["flash_clk_type"] = "XTAL"
            bflb_utils.printf("Default flash clock is XTAL")
        else:
            config["flash_clk_type"] = args.flashclk
        if not args.pllclk:
            config["pll_clk"] = "160M"
        else:
            config["pll_clk"] = args.pllclk
            bflb_utils.printf("Default pll clock is 160M")
        if not args.bootsrc:
            config["boot_src"] = "FLASH"
            bflb_utils.printf("Default boot source is flash")
        else:
            config["boot_src"] = args.bootsrc
    elif chiptype == "bl616" or chiptype == "wb03":
        if not args.xtal:
            config["dl_xtal"] = "40M"
            config["xtal_type"] = 'XTAL_40M'
            bflb_utils.printf("Default xtal is 40M")
        else:
            config["dl_xtal"] = args.xtal
            config["xtal_type"] = 'XTAL_' + args.xtal
        if not args.flashclk:
            config["flash_clk_type"] = "XTAL"
            bflb_utils.printf("Default flash clock is XTAL")
        else:
            config["flash_clk_type"] = args.flashclk
        if not args.pllclk:
            config["pll_clk"] = "WIFIPLL 320M"
            bflb_utils.printf("Default pll clock is WIFIPLL 320M")
        else:
            config["pll_clk"] = args.pllclk
        if not args.bootsrc:
            config["boot_src"] = "FLASH"
            bflb_utils.printf("Default boot source is flash")
        else:
            config["boot_src"] = args.bootsrc
        config["img1_file"] = firmware
        if args.addr:
            config["img1_addr"] = args.addr
    elif chiptype == "bl808" or chiptype == "bl628":
        config["key_sel"] = "0"
        if not args.xtal:
            config["dl_xtal"] = "40M"
            config["xtal_type"] = 'XTAL_40M'
            bflb_utils.printf("Default xtal is 40M")
        else:
            config["dl_xtal"] = args.xtal
            config["xtal_type"] = 'XTAL_' + args.xtal
        if not args.flashclk:
            config["flash_clk_type"] = "XTAL"
            bflb_utils.printf("Default flash clock is XTAL")
        else:
            config["flash_clk_type"] = args.flashclk
        if not args.pllclk:
            config["mcu_clk"] = "WIFIPLL 320M"
            bflb_utils.printf("Default mcu clock is WIFIPLL 320M")
        else:
            config["mcu_clk"] = args.pllclk
        if not args.bootsrc:
            config["boot_src"] = "FLASH"
            bflb_utils.printf("Default boot source is flash")
        else:
            config["boot_src"] = args.bootsrc
        config["encrypt_type-group0"] = 'None'
        config["key_sel-group0"] = '0'
        config["cache_way_disable-group0"] = '0'
        config["sign_type-group0"] = 'None'
        config["crc_ignore-group0"] = 'False'
        config["hash_ignore-group0"] = 'False'
        config["encrypt_key-group0"] = ''
        config["aes_iv-group0"] = ''
        config["public_key_cfg-group0"] = ''
        config["private_key_cfg-group0"] = ''
        config["encrypt_type-group1"] = 'None'
        config["key_sel-group1"] = '0'
        config["cache_way_disable-group1"] = '0'
        config["sign_type-group1"] = 'None'
        config["crc_ignore-group1"] = 'False'
        config["hash_ignore-group1"] = 'False'
        config["encrypt_key-group1"] = ''
        config["aes_iv-group1"] = ''
        config["public_key_cfg-group1"] = ''
        config["private_key_cfg-group1"] = ''
        config["img1_group"] = "group0"
        if args.firmware_group1:
            config["img2_group"] = "group1"
        else:
            config["img2_group"] = "unused"
        config["img3_group"] = "unused"
        config["img2_file"] = firmware_group1
        config["img2_addr"] = ""
        config["img3_file"] = ""
        config["img3_addr"] = ""
        config["img1_file"] = firmware
        if args.addr:
            if args.addr == "0x2000" or args.addr == "2000":
                config["img1_addr"] = "0x58000000"
                if args.firmware_group1:
                    config["img2_addr"] = "0x58000000"
            else:
                config["img1_addr"] = "0x" + args.addr.replace("0x", "")
                if args.firmware_group1:
                    config["img2_addr"] = "0x" + args.addr.replace("0x", "")
        else:
            config["img1_addr"] = "0x58000000"
            if args.firmware_group1:
                config["img2_addr"] = "0x58000000"
    else:
        bflb_utils.printf("Chip type is not correct")
        sys.exit(1)

    if config["dl_device"] == "jlink" and args.baudrate > 12000:
        config["dl_jlinkspeed"] = "12000"

    if args.erase:
        config["dl_chiperase"] = "True"
    else:
        config["dl_chiperase"] = "False"
    return config


def run(argv):
    port = None
    ports = []
    for item in get_serial_ports():
        ports.append(item["port"])
    if ports:
        try:
            port = sorted(ports, key=lambda x: int(re.match('COM(\d+)', x).group(1)))[0]
        except Exception:
            port = sorted(ports)[0]
    firmware_default = os.path.join(app_path, "img/project.bin")
    parser = argparse.ArgumentParser(description='mcu-tool')
    parser.add_argument('--chipname', required=True, help='chip name')
    parser.add_argument("--interface", dest="interface", default="uart", help="interface to use")
    parser.add_argument("--bootsrc", dest="bootsrc", default="Flash", help="boot source select")
    parser.add_argument("--port", dest="port", default=port, help="serial port to use")
    parser.add_argument("--baudrate",
                        dest="baudrate",
                        default=115200,
                        type=int,
                        help="the speed at which to communicate")
    parser.add_argument("--xtal", dest="xtal", help="xtal type")
    parser.add_argument("--flashclk", dest="flashclk", help="flash clock")
    parser.add_argument("--pllclk", dest="pllclk", help="pll clock")
    parser.add_argument("--firmware",
                        dest="firmware",
                        default=firmware_default,
                        help="image to write")
    parser.add_argument("--firmware-group1",
                        dest="firmware_group1",
                        default="",
                        help="image to write to group1")
    parser.add_argument("--addr", dest="addr", default="0x2000", help="address to write")
    parser.add_argument("--dts", dest="dts", help="device tree")
    parser.add_argument("--build", dest="build", action="store_true", help="build image")
    parser.add_argument("--erase", dest="erase", action="store_true", help="chip erase")
    parser.add_argument("--log", dest="log", action="store_true", help="enable logging")
    args = parser.parse_args(argv)
    if args.log:
        logger = record_log()
        redir = RedirectText(logger)
        sys.stdout = redir
    bflb_utils.printf("\r")
    bflb_utils.printf("==================================================")
    bflb_utils.printf("Chip name is %s" % args.chipname)
    gol.chip_name = args.chipname
    if conf_sign:
        reload(cgc)
    if args.port:
        bflb_utils.printf("Serial port is " + args.port)
    elif port:
        bflb_utils.printf("Serial port is " + port)
    else:
        bflb_utils.printf("Serial port is not found")
    bflb_utils.printf("Baudrate is " + str(args.baudrate))
    bflb_utils.printf("Firmware is " + str(args.firmware))
    bflb_utils.printf("Firmware group1 is " + str(args.firmware_group1))
    bflb_utils.printf("Device Tree is " + str(args.dts))
    bflb_utils.printf("==================================================")
    config = get_value(args)
    obj_mcu = BflbMcuTool(args.chipname, gol.dict_chip_cmd.get(args.chipname, "unkown chip type"))
    try:
        res = obj_mcu.create_img(args.chipname, gol.dict_chip_cmd[args.chipname], config)
        if res is not True:
            sys.exit(1)
        if args.build:
            obj_mcu.bind_img(config)
            f_org = os.path.join(chip_path, args.chipname, "img_create_mcu", "whole_img.bin")
            f = "firmware.bin"
            shutil.copyfile(f_org, f)
        else:
            obj_mcu.program_img_thread(config)
    except Exception as e:
        error = str(e)
        bflb_utils.printf(error)
        traceback.print_exc(limit=5, file=sys.stdout)


if __name__ == '__main__':
    print(sys.argv)
    run(sys.argv[1:])
