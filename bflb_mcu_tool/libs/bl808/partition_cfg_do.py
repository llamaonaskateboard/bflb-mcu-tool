# -*- coding:utf-8 -*-

import binascii
from libs import bflb_utils

partition1_addr = "E000"
partition2_addr = "F000"
fireware_name = "FW"
partition_magic_code = 0x42465054


def check_pt_data(data):
    """
    partition data 0~15 is partition table config
    parrition data 12~15 is partition table config crc32
    partition data 16~16+36 is partition entry 1, 16+36~16+72 is partition entry 2 ...
    partition data last 4 byte is partition entry data crc32
    """
    # bflb_utils.printf(binascii.hexlify(data))
    if partition_magic_code != bflb_utils.bytearray_to_int(data[0:4]):
        bflb_utils.printf("partition bin magic check fail ", binascii.hexlify(data[0:4]))
        return False, 0, 0
    table_count = bflb_utils.bytearray_to_int(
        data[6:7]) + (bflb_utils.bytearray_to_int(data[7:8]) << 8)
    # bflb_utils.printf("table count: ", table_count)
    if table_count > 16:
        bflb_utils.printf("error, pt enter size > 16")
        return False, 0, 0
    crcarray = bflb_utils.get_crc32_bytearray(data[:12])
    if data[12:16] != crcarray:
        bflb_utils.printf("pt table crc fail ", binascii.hexlify(crcarray))
        return False, 0, 0
    crcarray = bflb_utils.get_crc32_bytearray(data[16:16 + (36 * table_count)])
    if data[16 + (36 * table_count):16 + (36 * table_count) + 4] != crcarray:
        bflb_utils.printf("pt entries crc fail ", binascii.hexlify(crcarray))
        return False, 0, 0
    age = bflb_utils.bytearray_to_int(data[8:9]) + (bflb_utils.bytearray_to_int(data[9:10])<<8) +\
         (bflb_utils.bytearray_to_int(data[10:11])<<16) + (bflb_utils.bytearray_to_int(data[11:12])<<24)
    return True, table_count, age
