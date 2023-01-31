# -*- coding: utf-8 -*-


def img_load_create_predata_before_run_img():
    pre_data = bytearray(12)
    pre_data[0] = 0x50
    pre_data[1] = 0x00
    pre_data[2] = 0x08
    pre_data[3] = 0x00
    pre_data[4] = 0x00
    pre_data[5] = 0xF1
    pre_data[6] = 0x00
    pre_data[7] = 0x40
    pre_data[8] = 0x45
    pre_data[9] = 0x48
    pre_data[10] = 0x42
    pre_data[11] = 0x4E

    pre_data2 = bytearray(12)
    pre_data2[0] = 0x50
    pre_data2[1] = 0x00
    pre_data2[2] = 0x08
    pre_data2[3] = 0x00
    pre_data2[4] = 0x04
    pre_data2[5] = 0xF1
    pre_data2[6] = 0x00
    pre_data2[7] = 0x40
    pre_data2[8] = 0x00
    pre_data2[9] = 0x00
    pre_data2[10] = 0x01
    pre_data2[11] = 0x22

    pre_data3 = bytearray(12)
    pre_data3[0] = 0x50
    pre_data3[1] = 0x00
    pre_data3[2] = 0x08
    pre_data3[3] = 0x00
    pre_data3[4] = 0x18
    pre_data3[5] = 0x00
    pre_data3[6] = 0x00
    pre_data3[7] = 0x40
    pre_data3[8] = 0x00
    pre_data3[9] = 0x00
    pre_data3[10] = 0x00
    pre_data3[11] = 0x00

    pre_data4 = bytearray(12)
    pre_data4[0] = 0x50
    pre_data4[1] = 0x00
    pre_data4[2] = 0x08
    pre_data4[3] = 0x00
    pre_data4[4] = 0x18
    pre_data4[5] = 0x00
    pre_data4[6] = 0x00
    pre_data4[7] = 0x40
    pre_data4[8] = 0x02
    pre_data4[9] = 0x00
    pre_data4[10] = 0x00
    pre_data4[11] = 0x00

    return pre_data + pre_data2 + pre_data3 + pre_data4
