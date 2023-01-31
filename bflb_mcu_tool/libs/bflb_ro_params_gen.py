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

from libs import bflb_toml as toml


class RoParamsTomlCfg(object):

    def __init__(self, toml_config):
        self.toml_dict = toml.load(toml_config)

    def read_ap_info(self):
        return self.toml_dict['ap']

    def read_broad_info(self):
        return self.toml_dict['brd']

    def read_broad_rf_info(self):
        return self.toml_dict['brd']['rf']


class ApInfo(object):

    def __init__(self, ap_dict):
        self.ssid = ap_dict['ssid']
        self.pwd = ap_dict['pwd']
        self.chan = ap_dict['ap_channel']
        self.auto_chan_detect_en = ap_dict['auto_chan_detect_en']

    def write(self):
        ap_info_bytes = bytearray()
        # ssid len and ssid
        ssid_len = len(self.ssid)
        ap_info_bytes.append(ssid_len)
        ap_info_bytes.extend(self.ssid.encode())
        ap_info_bytes.extend(bytes([0] * (32 - ssid_len)))
        # pwd len and pwd
        pwd_len = len(self.pwd)
        ap_info_bytes.append(pwd_len)
        # maybe a bug for psk
        ap_info_bytes.extend(self.pwd.encode())
        ap_info_bytes.extend(bytes([0] * (64 - pwd_len)))
        ap_info_bytes.append(self.chan)
        ap_info_bytes.append(self.auto_chan_detect_en)
        return ap_info_bytes


class BroadInfo(object):

    def __init__(self, brd_dict, brd_rf_dict):
        self.sta_mac_addr = brd_dict['sta_mac_addr']
        self.ap_mac_addr = brd_dict['ap_mac_addr']
        self.country_code = brd_dict['country_code']
        self.xtal = brd_rf_dict['xtal']
        self.pwr_table = brd_rf_dict['pwr_table']
        self.channel_div_table = brd_rf_dict['channel_div_table']
        self.channel_cnt_table = brd_rf_dict['channel_cnt_table']
        self.lo_fcal_div = brd_rf_dict['lo_fcal_div']

    def write(self):
        brd_info_bytes = bytearray()

        # mac addr
        def _mac_addr_to_bytes(mac_addr_s):
            mac_addr_int_l = []
            mac_addr_str_l = mac_addr_s.split(":")
            for mac_i in mac_addr_str_l:
                mac_addr_int_l.append(int(mac_i, 16))
            return bytes(mac_addr_int_l)

        brd_info_bytes.extend(_mac_addr_to_bytes(self.sta_mac_addr))
        brd_info_bytes.extend(_mac_addr_to_bytes(self.ap_mac_addr))
        # coutry_code
        brd_info_bytes.append(self.country_code)
        # xtal_cap
        for byte in self.xtal:
            brd_info_bytes.append(byte)
        # tx_pwr_tbl

        def _pwr_tbl_to_bytes(pwr_tbl):
            tbl = bytearray()
            for one_pwr in pwr_tbl:
                tbl.extend(bytes(one_pwr))
            return tbl

        brd_info_bytes.extend(_pwr_tbl_to_bytes(self.pwr_table))

        def _int_to_bytes(x):
            return x.to_bytes((x.bit_length() + 7) // 8, 'little')

        def _tbl_to_bytes(dim_tbl):
            tbl = bytearray()
            for val in dim_tbl:
                tbl.extend(_int_to_bytes(val))
            return tbl

        brd_info_bytes.extend(_tbl_to_bytes(self.channel_div_table))
        brd_info_bytes.extend(_tbl_to_bytes(self.channel_cnt_table))
        brd_info_bytes.extend(_int_to_bytes(self.lo_fcal_div))
        return brd_info_bytes


def bl_ro_params_gen(in_toml_config, out_bin_file):
    toml_config = in_toml_config
    bin_file = out_bin_file
    ro_params_cfg = RoParamsTomlCfg(toml_config)
    brd_info_b = BroadInfo(ro_params_cfg.read_broad_info(),
                           ro_params_cfg.read_broad_rf_info()).write()
    ap_info_b = ApInfo(ro_params_cfg.read_ap_info()).write()
    with open(bin_file, 'wb') as bin_f:
        bin_f.write(str.encode('bl_ro_params') + b'\x00')
        bin_f.write(brd_info_b)
        bin_f.write(ap_info_b)
