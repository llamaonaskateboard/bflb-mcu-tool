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
import shutil
import traceback

try:
    import bflb_path
except ImportError:
    from libs import bflb_path
from libs import bflb_utils
from libs.bflb_utils import app_path, chip_path, convert_path
from libs.bflb_configobj import BFConfigParser


def bootheader_update_flash_pll_crc(bootheader_data, chiptype):
    flash_cfg_start = 8
    flash_cfg_len = 4 + 84 + 4
    if chiptype == "wb03":
        flash_cfg_start += 208
    # magic+......+CRC32
    flash_cfg = bootheader_data[flash_cfg_start + 4:flash_cfg_start + flash_cfg_len - 4]
    crcarray = bflb_utils.get_crc32_bytearray(flash_cfg)
    bootheader_data[flash_cfg_start + flash_cfg_len - 4:flash_cfg_start + flash_cfg_len] = crcarray
    pll_cfg_start = flash_cfg_start + flash_cfg_len
    pll_cfg_len = 4 + 8 + 4
    if chiptype == "bl808":
        pll_cfg_len = 4 + 20 + 4
    elif chiptype == "bl628":
        pll_cfg_len = 4 + 16 + 4
    elif chiptype == "bl616" or chiptype == "wb03":
        pll_cfg_len = 4 + 12 + 4
    # magic+......+CRC32
    pll_cfg = bootheader_data[pll_cfg_start + 4:pll_cfg_start + pll_cfg_len - 4]
    crcarray = bflb_utils.get_crc32_bytearray(pll_cfg)
    bootheader_data[pll_cfg_start + pll_cfg_len - 4:pll_cfg_start + pll_cfg_len] = crcarray
    return bootheader_data


def get_int_mask(pos, length):
    ones = "1" * 32
    zeros = "0" * 32
    mask = ones[0:32 - pos - length] + zeros[0:length] + ones[0:pos]
    return int(mask, 2)


def update_data_from_cfg(config_keys, config_file, section):
    bflb_utils.printf("Updating data according to <" + config_file + "[" + section + "]>")
    cfg = BFConfigParser()
    cfg.read(config_file)
    # get finally data len
    filelen = 0
    for key in config_keys:
        offset = int(config_keys.get(key)["offset"], 10)
        if offset > filelen:
            filelen = offset
    filelen += 4
    bflb_utils.printf("Created file len:" + str(filelen))
    data = bytearray(filelen)
    data_mask = bytearray(filelen)
    # bflb_utils.printf(binascii.hexlify(data))
    for key in cfg.options(section):
        if config_keys.get(key) is None:
            bflb_utils.printf(key + " not exist")
            continue
        # bflb_utils.printf(key)
        val = cfg.get(section, key)
        if val.startswith("0x"):
            val = int(val, 16)
        else:
            val = int(val, 10)
        # bflb_utils.printf(val)
        offset = int(config_keys.get(key)["offset"], 10)
        pos = int(config_keys.get(key)["pos"], 10)
        bitlen = int(config_keys.get(key)["bitlen"], 10)

        oldval = bflb_utils.bytearray_to_int(bflb_utils.bytearray_reverse(data[offset:offset + 4]))
        oldval_mask = bflb_utils.bytearray_to_int(
            bflb_utils.bytearray_reverse(data_mask[offset:offset + 4]))
        newval = (oldval & get_int_mask(pos, bitlen)) + (val << pos)
        if val != 0:
            newval_mask = (oldval_mask | (~get_int_mask(pos, bitlen)))
        else:
            newval_mask = oldval_mask
        # bflb_utils.printf(newval,binascii.hexlify(bflb_utils.int_to_4bytearray_l(newval)))
        data[offset:offset + 4] = bflb_utils.int_to_4bytearray_l(newval)
        data_mask[offset:offset + 4] = bflb_utils.int_to_4bytearray_l(newval_mask)
    # bflb_utils.printf(binascii.hexlify(data))
    return data, data_mask


def bootheader_create_do(chipname, chiptype, config_file, section, output_file=None, if_img=False):
    efuse_bootheader_path = os.path.join(chip_path, chipname, "efuse_bootheader")
    try:
        bflb_utils.printf("Create bootheader using ", config_file)
        sub_module = __import__("libs." + chiptype, fromlist=[chiptype])
        bh_data, tmp = update_data_from_cfg(sub_module.bootheader_cfg_keys.bootheader_cfg_keys,
                                            config_file, section)
        bh_data = bootheader_update_flash_pll_crc(bh_data, chiptype)
        if output_file is None:
            fp = open(efuse_bootheader_path + "/" + section.lower().replace("_cfg", ".bin"), 'wb+')
        else:
            fp = open(output_file, 'wb+')
        if section == "BOOTHEADER_CFG" and chiptype == "bl60x":
            final_data = bytearray(8 * 1024)
            # add sp core feature
            # halt
            bh_data[118] = (bh_data[118] | (1 << 2))
            final_data[0:176] = bh_data
            final_data[4096 + 0:4096 + 176] = bh_data
            # change magic
            final_data[4096 + 2] = 65
            # change waydis to 0xf
            final_data[117] = (final_data[117] | (15 << 4))
            # change crc and hash ignore
            final_data[4096 + 118] = final_data[4096 + 118] | 0x03
            bh_data = final_data
        if if_img is True:
            # clear flash magic
            bh_data[8:12] = bytearray(4)
            # clear clock magic
            bh_data[100:104] = bytearray(4)
            if chiptype == "bl808":
                fp.write(bh_data[0:384])
            elif chiptype == "bl628":
                fp.write(bh_data[0:256])
            elif chiptype == "bl616":
                fp.write(bh_data[0:256])
            elif chiptype == "wb03":
                fp.write(bh_data[0:208 + 256])
            elif chiptype == "bl702l":
                fp.write(bh_data[0:240])
            else:
                fp.write(bh_data[0:176])
        else:
            fp.write(bh_data)
        fp.close()

        if chiptype == "bl808":
            if section == "BOOTHEADER_GROUP0_CFG":
                fp = open(efuse_bootheader_path + "/clock_para.bin", 'wb+')
                fp.write(bh_data[100:100 + 28])
                fp.close()
                fp = open(efuse_bootheader_path + "/flash_para.bin", 'wb+')
                fp.write(bh_data[12:12 + 84])
                fp.close()
        elif chiptype == "bl628":
            if section == "BOOTHEADER_GROUP0_CFG":
                fp = open(efuse_bootheader_path + "/clock_para.bin", 'wb+')
                fp.write(bh_data[100:100 + 24])
                fp.close()
                fp = open(efuse_bootheader_path + "/flash_para.bin", 'wb+')
                fp.write(bh_data[12:12 + 84])
                fp.close()
        elif chiptype == "bl616":
            if section == "BOOTHEADER_GROUP0_CFG":
                fp = open(efuse_bootheader_path + "/clock_para.bin", 'wb+')
                fp.write(bh_data[100:100 + 20])
                fp.close()
                fp = open(efuse_bootheader_path + "/flash_para.bin", 'wb+')
                fp.write(bh_data[12:12 + 84])
                fp.close()
        elif chiptype == "wb03":
            if section == "BOOTHEADER_GROUP0_CFG":
                fp = open(efuse_bootheader_path + "/clock_para.bin", 'wb+')
                fp.write(bh_data[208 + 100:208 + 100 + 20])
                fp.close()
                fp = open(efuse_bootheader_path + "/flash_para.bin", 'wb+')
                fp.write(bh_data[208 + 12:208 + 12 + 84])
                fp.close()
        elif chiptype == "bl702l":
            if section == "BOOTHEADER_CFG":
                fp = open(efuse_bootheader_path + "/clock_para.bin", 'wb+')
                fp.write(bh_data[100:100 + 16])
                fp.close()
                fp = open(efuse_bootheader_path + "/flash_para.bin", 'wb+')
                fp.write(bh_data[12:12 + 84])
                fp.close()
        else:
            fp = open(efuse_bootheader_path + "/flash_para.bin", 'wb+')
            fp.write(bh_data[12:12 + 84])
            fp.close()
    except Exception as e:
        bflb_utils.printf("bootheader_create_do fail!!")
        bflb_utils.printf(e)
        traceback.print_exc(limit=5, file=sys.stdout)


def bootheader_create_process(chipname,
                              chiptype,
                              config_file,
                              output_file1=None,
                              output_file2=None,
                              if_img=False):
    fp = open(config_file, 'r')
    data = fp.read()
    fp.close()
    if "BOOTHEADER_CFG" in data:
        bootheader_create_do(chipname, chiptype, config_file, "BOOTHEADER_CFG", output_file1,
                             if_img)
    if "BOOTHEADER_CPU0_CFG" in data:
        bootheader_create_do(chipname, chiptype, config_file, "BOOTHEADER_CPU0_CFG", output_file1,
                             if_img)
    if "BOOTHEADER_CPU1_CFG" in data:
        bootheader_create_do(chipname, chiptype, config_file, "BOOTHEADER_CPU1_CFG", output_file2,
                             if_img)
    if "BOOTHEADER_GROUP0_CFG" in data:
        bootheader_create_do(chipname, chiptype, config_file, "BOOTHEADER_GROUP0_CFG",
                             output_file1, if_img)
    if "BOOTHEADER_GROUP1_CFG" in data:
        bootheader_create_do(chipname, chiptype, config_file, "BOOTHEADER_GROUP1_CFG",
                             output_file2, if_img)


def efuse_create_process(chipname, chiptype, config_file, output_file=None):
    efuse_bootheader_path = os.path.join(chip_path, chipname, "efuse_bootheader")
    eflash_loader_path = os.path.join(chip_path, chipname, "eflash_loader")
    filedir = ""
    bflb_utils.printf("Create efuse using ", config_file)
    cfgfile = eflash_loader_path + "/eflash_loader_cfg.ini"
    if os.path.isfile(cfgfile) is False:
        shutil.copyfile(eflash_loader_path + "/eflash_loader_cfg.conf", cfgfile)
    cfg = BFConfigParser()
    cfg.read(cfgfile)
    sub_module = __import__("libs." + chiptype, fromlist=[chiptype])
    efuse_data, mask = update_data_from_cfg(sub_module.efuse_cfg_keys.efuse_cfg_keys, config_file,
                                            "EFUSE_CFG")
    if output_file is None:
        filedir = efuse_bootheader_path + "/efusedata.bin"
    else:
        filedir = output_file
    fp = open(filedir, 'wb+')
    fp.write(efuse_data)
    fp.close()
    bflb_utils.update_cfg(cfg, "EFUSE_CFG", "file",
                          convert_path(os.path.relpath(filedir, app_path)))
    if output_file is None:
        filedir = efuse_bootheader_path + "/efusedata_mask.bin"
    else:
        filedir = output_file.replace(".bin", "_mask.bin")
    fp = open(filedir, 'wb+')
    fp.write(mask)
    fp.close()
    bflb_utils.update_cfg(cfg, "EFUSE_CFG", "maskfile",
                          convert_path(os.path.relpath(filedir, app_path)))
    cfg.write(cfgfile, "w+")


def efuse_boothd_create_process(chipname, chiptype, config_file):
    bootheader_create_process(chipname, chiptype, config_file)
    efuse_create_process(chipname, chiptype, config_file)


def run():
    chip_dict = {
        "bl56x": "bl60x",
        "bl60x": "bl60x",
        "bl562": "bl602",
        "bl602": "bl602",
        "bl702": "bl702",
        "bl702l": "bl702l",
        "bl808": "bl808",
        "bl628": "bl628",
        "bl616": "bl616",
        "wb03": "wb03",
    }
    chipname = sys.argv[1]
    chiptype = chip_dict[chipname]
    img_create_path = os.path.join(chip_path, chipname, "img_create_mcu")
    bh_cfg_file = img_create_path + "/efuse_bootheader_cfg.ini"
    bh_file = img_create_path + "/bootheader.bin"
    bootheader_create_process(chipname, chiptype, bh_cfg_file, bh_file,
                              img_create_path + "/bootheader_dummy.bin")


if __name__ == '__main__':
    run()
