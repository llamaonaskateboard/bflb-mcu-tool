# -*- coding: utf-8 -*-
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
import re

import config as gol
from libs import bflb_utils
from libs.bflb_utils import app_path, chip_path, conf_sign
from libs.bflb_configobj import BFConfigParser


def get_int_mask(pos, length):
    ones = "1" * 32
    zeros = "0" * 32
    mask = ones[0:32 - pos - length] + zeros[0:length] + ones[0:pos]
    return int(mask, 2)


def update_flash_para_from_cfg(config_keys, config_file):
    section = "FLASH_CFG"
    # bflb_utils.printf("Updating data according to <" + config_file + "[" + section + "]>")
    cfg = BFConfigParser()
    cfg.read(config_file)
    # get finally data len
    filelen = 0
    offset = 0
    minOffset = 0xFFFFFFFF
    maxOffset = 0
    flashCrcOffset = 0
    crcOffset = 0
    if config_keys.get("crc32") != None:
        crcOffset = int(config_keys.get("crc32")["offset"], 10)
    if config_keys.get("flashcfg_crc32") != None:
        flashCrcOffset = int(config_keys.get("flashcfg_crc32")["offset"], 10)
    for key in cfg.options(section):
        if config_keys.get(key) == None:
            continue
        offset = int(config_keys.get(key)["offset"], 10)
        if offset < minOffset:
            minOffset = offset
        if offset > maxOffset:
            maxOffset = offset
    filelen = maxOffset - minOffset + 4
    data = bytearray(filelen)
    # bflb_utils.printf(binascii.hexlify(data))
    for key in cfg.options(section):
        if config_keys.get(key) == None:
            bflb_utils.printf(key + " not exist")
            continue
        # bflb_utils.printf(key)
        val = cfg.get(section, key)
        if val.startswith("0x"):
            val = int(val, 16)
        else:
            val = int(val, 10)
        # bflb_utils.printf(val)
        offset = int(config_keys.get(key)["offset"], 10) - minOffset
        pos = int(config_keys.get(key)["pos"], 10)
        bitlen = int(config_keys.get(key)["bitlen"], 10)

        oldval = bflb_utils.bytearray_to_int(bflb_utils.bytearray_reverse(data[offset:offset + 4]))
        newval = (oldval & get_int_mask(pos, bitlen)) + (val << pos)
        # bflb_utils.printf(newval,binascii.hexlify(bflb_utils.int_to_4bytearray_l(newval)))
        data[offset:offset + 4] = bflb_utils.int_to_4bytearray_l(newval)
    # bflb_utils.printf(binascii.hexlify(data))
    return minOffset, filelen, data, flashCrcOffset, crcOffset


def update_flash_cfg_data_do(chipname, chiptype, flash_id):
    if conf_sign:
        cfg_dir = app_path + "/utils/flash/" + chipname + '/'
    else:
        cfg_dir = app_path + "/utils/flash/" + gol.flash_dict[chipname] + '/'
    sub_module = __import__("libs." + chiptype, fromlist=[chiptype])
    conf_name = sub_module.flash_select_do.get_suitable_file_name(cfg_dir, flash_id)
    if os.path.isfile(cfg_dir + conf_name) == False:
        return None, None, None, None, None
    return update_flash_para_from_cfg(sub_module.bootheader_cfg_keys.bootheader_cfg_keys,
                                      cfg_dir + conf_name)


def flash_bootheader_config_check(chipname, chiptype, flashid, file, parafile):
    magic_code = 0x504e4642
    flash_magic_code = 0x47464346
    offset, flashCfgLen, data, flashCrcOffset, crcOffset =\
        update_flash_cfg_data_do(chipname, chiptype, flashid)
    if data is None:
        offset = 12
        flashCfgLen = 84

    if parafile != "" and data != None:
        fp = open(os.path.join(app_path, parafile), 'wb')
        fp.write(data)
        fp.close()

    fp = open(os.path.join(app_path, file), 'rb')
    rdata = bytearray(fp.read())
    fp.close()
    i = 0
    length = 128
    flashCfg = bytearray(256)
    while i < length:
        if rdata[i:i + 4] == bflb_utils.int_to_4bytearray_l(magic_code):
            if rdata[i + 8:i + 12] == bflb_utils.int_to_4bytearray_l(flash_magic_code):
                if data != None:
                    data[2:4] = rdata[i + 14:i + 16]
                flashCfg = rdata[i + offset:i + offset + flashCfgLen]
                if data != None:
                    if data != flashCfg:
                        if flashCfg[13:14] != b'\xff':
                            return False
                else:
                    if flashCfg[13:14] != b'\xff':
                        return False
        i += 4
    return True


def update_flash_cfg_data(chipname, chiptype, flash_id, cfg, bh_cfg_file, cfg_key):
    cfg2 = BFConfigParser()
    cfg2.read(bh_cfg_file)
    magic_code = cfg2.get(cfg_key, "magic_code")
    magic_code = int(magic_code, 16)
    flash_magic_code = cfg2.get(cfg_key, "flashcfg_magic_code")
    flash_magic_code = int(flash_magic_code, 16)
    sub_module = __import__("libs." + chiptype, fromlist=[chiptype])
    offset, flashCfgLen, data, flashCrcOffset, crcOffset = update_flash_cfg_data_do(
        chipname, chiptype, flash_id)

    para_file = cfg.get("FLASH_CFG", "flash_para")
    if para_file != "":
        fp = open(os.path.join(app_path, para_file), 'wb')
        fp.write(data)
        fp.close()

    flash_file = re.compile('\s+').split(cfg.get("FLASH_CFG", "file"))
    for f in flash_file:
        fp = open(os.path.join(app_path, f), 'rb')
        rdata = bytearray(fp.read())
        fp.close()
        i = 0
        length = len(rdata)
        while i < length:
            if rdata[i:i + 4] == bflb_utils.int_to_4bytearray_l(magic_code):
                if rdata[i + 8:i + 12] == bflb_utils.int_to_4bytearray_l(flash_magic_code):
                    data[2:4] = rdata[i + 14:i + 16]
                    flashCfg = rdata[i + offset:i + offset + flashCfgLen]
                    if data != flashCfg:
                        return False
            i += 4
    return True


def check_basic_flash_cfg(cfg_file, section):
    if os.path.isfile(cfg_file) is False:
        return False
    cfg = BFConfigParser()
    cfg.read(cfg_file)
    if cfg.has_option(section, "mfg_id"):
        if cfg.get(section, "mfg_id") == "0xff" or cfg.get(section, "mfg_id") == "0xFF":
            cfg.set(section, "io_mode", "0x10")
            cfg.set(section, "cont_read_support", "0")
            cfg.write(cfg_file, "w+")
            return True
    return False


def update_flash_cfg(chipname, chiptype, flash_id, file=None, create=False, section=None):
    sub_module = __import__("libs." + chiptype, fromlist=[chiptype])
    if check_basic_flash_cfg(file, section):
        return True
    if sub_module.flash_select_do.update_flash_cfg_do(chipname, chiptype, flash_id, file, create,
                                                      section) == False:
        return False
    return True


def get_supported_flash(chiptype):
    sub_module = __import__("libs." + chiptype, fromlist=[chiptype])
    return sub_module.flash_select_do.get_supported_flash_do()
