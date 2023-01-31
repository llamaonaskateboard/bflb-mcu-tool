# -*- coding:utf-8 -*-

efuse_cfg_keys = {
    "ef_sf_aes_mode": {
        "offset": "0",
        "pos": "0",
        "bitlen": "2"
    },
    "ef_ai_dis": {
        "offset": "0",
        "pos": "2",
        "bitlen": "1"
    },
    "ef_cpu0_dis": {
        "offset": "0",
        "pos": "3",
        "bitlen": "1"
    },
    "ef_sboot_en": {
        "offset": "0",
        "pos": "4",
        "bitlen": "2"
    },
    "ef_uart_dis": {
        "offset": "0",
        "pos": "6",
        "bitlen": "4"
    },
    "ef_bus_rmp_sw_en": {
        "offset": "0",
        "pos": "10",
        "bitlen": "1"
    },
    "ef_bus_rmp_dis": {
        "offset": "0",
        "pos": "11",
        "bitlen": "1"
    },
    "ef_sf_key_re_sel": {
        "offset": "0",
        "pos": "12",
        "bitlen": "2"
    },
    "ef_sdu_dis": {
        "offset": "0",
        "pos": "14",
        "bitlen": "1"
    },
    "ef_btdm_dis": {
        "offset": "0",
        "pos": "15",
        "bitlen": "1"
    },
    "ef_wifi_dis": {
        "offset": "0",
        "pos": "16",
        "bitlen": "1"
    },
    "ef_0_key_enc_en": {
        "offset": "0",
        "pos": "17",
        "bitlen": "1"
    },
    "ef_cam_dis": {
        "offset": "0",
        "pos": "18",
        "bitlen": "1"
    },
    "ef_m154_dis": {
        "offset": "0",
        "pos": "19",
        "bitlen": "1"
    },
    "ef_sdu_rst_opt": {
        "offset": "0",
        "pos": "20",
        "bitlen": "1"
    },
    "ef_cpu_rst_dbg_dis": {
        "offset": "0",
        "pos": "21",
        "bitlen": "1"
    },
    "ef_se_dbg_dis": {
        "offset": "0",
        "pos": "22",
        "bitlen": "1"
    },
    "ef_efuse_dbg_dis": {
        "offset": "0",
        "pos": "23",
        "bitlen": "1"
    },
    "ef_dbg_jtag_1_dis": {
        "offset": "0",
        "pos": "24",
        "bitlen": "2"
    },
    "ef_dbg_jtag_0_dis": {
        "offset": "0",
        "pos": "26",
        "bitlen": "2"
    },
    "ef_dbg_mode": {
        "offset": "0",
        "pos": "28",
        "bitlen": "4"
    },
    "ef_dbg_pwd_low": {
        "offset": "4",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_dbg_pwd_high": {
        "offset": "8",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_dbg_pwd2_low": {
        "offset": "12",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_dbg_pwd2_high": {
        "offset": "16",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_wifi_mac_low": {
        "offset": "20",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_wifi_mac_high": {
        "offset": "24",
        "pos": "0",
        "bitlen": "32"
    },
    ###################################################################
    "ef_key_slot_0_w0": {
        "offset": "28",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_0_w1": {
        "offset": "32",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_0_w2": {
        "offset": "36",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_0_w3": {
        "offset": "40",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_1_w0": {
        "offset": "44",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_1_w1": {
        "offset": "48",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_1_w2": {
        "offset": "52",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_1_w3": {
        "offset": "56",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_2_w0": {
        "offset": "60",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_2_w1": {
        "offset": "64",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_2_w2": {
        "offset": "68",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_2_w3": {
        "offset": "72",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_3_w0": {
        "offset": "76",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_3_w1": {
        "offset": "80",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_3_w2": {
        "offset": "84",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_3_w3": {
        "offset": "88",
        "pos": "0",
        "bitlen": "32"
    },
    "bootrom_protect": {
        "offset": "92",
        "pos": "0",
        "bitlen": "1"
    },
    "uart_log_disable": {
        "offset": "92",
        "pos": "1",
        "bitlen": "1"
    },
    "boot_pin_cfg": {
        "offset": "92",
        "pos": "2",
        "bitlen": "1"
    },
    "mediaboot_disable": {
        "offset": "92",
        "pos": "3",
        "bitlen": "1"
    },
    "uartboot_disable": {
        "offset": "92",
        "pos": "4",
        "bitlen": "1"
    },
    "usbboot_enable": {
        "offset": "92",
        "pos": "5",
        "bitlen": "1"
    },
    "uart_log_reopen": {
        "offset": "92",
        "pos": "6",
        "bitlen": "1"
    },
    "sign_cfg": {
        "offset": "92",
        "pos": "7",
        "bitlen": "1"
    },
    "dcache_disable": {
        "offset": "92",
        "pos": "8",
        "bitlen": "1"
    },
    "jtag_cfg": {
        "offset": "92",
        "pos": "9",
        "bitlen": "3"
    },
    "fix_key_sel": {
        "offset": "92",
        "pos": "12",
        "bitlen": "1"
    },
    "sdh_en": {
        "offset": "92",
        "pos": "13",
        "bitlen": "1"
    },
    "sf_pin_cfg": {
        "offset": "92",
        "pos": "14",
        "bitlen": "6"
    },
    "boot_pin_dly": {
        "offset": "92",
        "pos": "20",
        "bitlen": "2"
    },
    "power_trim_disable": {
        "offset": "92",
        "pos": "22",
        "bitlen": "1"
    },
    "trim_enable": {
        "offset": "92",
        "pos": "23",
        "bitlen": "1"
    },
    "flash_power_delay": {
        "offset": "92",
        "pos": "24",
        "bitlen": "2"
    },
    "boot_level_revert": {
        "offset": "92",
        "pos": "26",
        "bitlen": "1"
    },
    "tz_boot": {
        "offset": "92",
        "pos": "27",
        "bitlen": "1"
    },
    "usb_desc_cfg": {
        "offset": "92",
        "pos": "28",
        "bitlen": "1"
    },
    "hbn_check_sign": {
        "offset": "92",
        "pos": "29",
        "bitlen": "1"
    },
    "keep_dbg_port_closed": {
        "offset": "92",
        "pos": "30",
        "bitlen": "1"
    },
    "hbn_jump_disable": {
        "offset": "92",
        "pos": "31",
        "bitlen": "1"
    },
    "xtal_type": {
        "offset": "96",
        "pos": "0",
        "bitlen": "3"
    },
    "wifipll_pu": {
        "offset": "96",
        "pos": "3",
        "bitlen": "1"
    },
    "aupll_pu": {
        "offset": "96",
        "pos": "4",
        "bitlen": "1"
    },
    "product_id": {
        "offset": "96",
        "pos": "5",
        "bitlen": "2"
    },
    "sdioboot_enable": {
        "offset": "96",
        "pos": "7",
        "bitlen": "1"
    },
    "mcu_clk": {
        "offset": "96",
        "pos": "8",
        "bitlen": "3"
    },
    "mcu_clk_div": {
        "offset": "96",
        "pos": "11",
        "bitlen": "1"
    },
    "mcu_pbclk_div": {
        "offset": "96",
        "pos": "12",
        "bitlen": "2"
    },
    "uart_download_cfg": {
        "offset": "96",
        "pos": "14",
        "bitlen": "2"
    },
    "pin_func_0_init": {
        "offset": "96",
        "pos": "16",
        "bitlen": "1"
    },
    "always_uart": {
        "offset": "96",
        "pos": "17",
        "bitlen": "1"
    },
    "abt_shake_hands_dis": {
        "offset": "96",
        "pos": "18",
        "bitlen": "1"
    },
    "no_hd_boot_en": {
        "offset": "96",
        "pos": "19",
        "bitlen": "1"
    },
    "ocram_way_dis_cfg": {
        "offset": "96",
        "pos": "20",
        "bitlen": "2"
    },
    "xtal_level_revert": {
        "offset": "96",
        "pos": "22",
        "bitlen": "1"
    },
    "flash_clk_type": {
        "offset": "96",
        "pos": "23",
        "bitlen": "3"
    },
    "flash_clk_div": {
        "offset": "96",
        "pos": "26",
        "bitlen": "1"
    },
    "ldo18io_cfg_dis": {
        "offset": "96",
        "pos": "27",
        "bitlen": "1"
    },
    "bootlog_pin_cfg": {
        "offset": "96",
        "pos": "28",
        "bitlen": "1"
    },
    "abt_offset": {
        "offset": "96",
        "pos": "29",
        "bitlen": "1"
    },
    "boot_pull_cfg": {
        "offset": "96",
        "pos": "30",
        "bitlen": "1"
    },
    "usb_if_int_disable": {
        "offset": "96",
        "pos": "31",
        "bitlen": "1"
    },
    "ef_sw_usage_2": {
        "offset": "100",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_sw_usage_3": {
        "offset": "104",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_11_w0": {
        "offset": "108",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_11_w1": {
        "offset": "112",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_11_w2": {
        "offset": "116",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_11_w3": {
        "offset": "120",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_sec_lifecycle": {
        "offset": "124",
        "pos": "0",
        "bitlen": "4"
    },
    "wr_lock_rsvd_0": {
        "offset": "124",
        "pos": "4",
        "bitlen": "8"
    },
    "wr_lock_rsvd_1": {
        "offset": "124",
        "pos": "12",
        "bitlen": "1"
    },
    "flash_dly_coe": {
        "offset": "124",
        "pos": "13",
        "bitlen": "1"
    },
    "wr_lock_boot_mode": {
        "offset": "124",
        "pos": "14",
        "bitlen": "1"
    },
    "wr_lock_dbg_pwd": {
        "offset": "124",
        "pos": "15",
        "bitlen": "1"
    },
    "wr_lock_wifi_mac": {
        "offset": "124",
        "pos": "16",
        "bitlen": "1"
    },
    "wr_lock_key_slot_0": {
        "offset": "124",
        "pos": "17",
        "bitlen": "1"
    },
    "wr_lock_key_slot_1": {
        "offset": "124",
        "pos": "18",
        "bitlen": "1"
    },
    "wr_lock_key_slot_2": {
        "offset": "124",
        "pos": "19",
        "bitlen": "1"
    },
    "wr_lock_key_slot_3": {
        "offset": "124",
        "pos": "20",
        "bitlen": "1"
    },
    "wr_lock_sw_usage_0": {
        "offset": "124",
        "pos": "21",
        "bitlen": "1"
    },
    "wr_lock_sw_usage_1": {
        "offset": "124",
        "pos": "22",
        "bitlen": "1"
    },
    "wr_lock_sw_usage_2": {
        "offset": "124",
        "pos": "23",
        "bitlen": "1"
    },
    "wr_lock_sw_usage_3": {
        "offset": "124",
        "pos": "24",
        "bitlen": "1"
    },
    "wr_lock_key_slot_11": {
        "offset": "124",
        "pos": "25",
        "bitlen": "1"
    },
    "rd_lock_dbg_pwd": {
        "offset": "124",
        "pos": "26",
        "bitlen": "1"
    },
    "rd_lock_key_slot_0": {
        "offset": "124",
        "pos": "27",
        "bitlen": "1"
    },
    "rd_lock_key_slot_1": {
        "offset": "124",
        "pos": "28",
        "bitlen": "1"
    },
    "rd_lock_key_slot_2": {
        "offset": "124",
        "pos": "29",
        "bitlen": "1"
    },
    "rd_lock_key_slot_3": {
        "offset": "124",
        "pos": "30",
        "bitlen": "1"
    },
    "rd_lock_key_slot_11": {
        "offset": "124",
        "pos": "31",
        "bitlen": "1"
    },
    "ef_key_slot_4_w0": {
        "offset": "128",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_4_w1": {
        "offset": "132",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_4_w2": {
        "offset": "136",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_4_w3": {
        "offset": "140",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_5_w0": {
        "offset": "144",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_5_w1": {
        "offset": "148",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_5_w2": {
        "offset": "152",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_5_w3": {
        "offset": "156",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_6_w0": {
        "offset": "160",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_6_w1": {
        "offset": "164",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_6_w2": {
        "offset": "168",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_6_w3": {
        "offset": "172",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_7_w0": {
        "offset": "176",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_7_w1": {
        "offset": "180",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_7_w2": {
        "offset": "184",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_7_w3": {
        "offset": "188",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_8_w0": {
        "offset": "192",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_8_w1": {
        "offset": "196",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_8_w2": {
        "offset": "200",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_8_w3": {
        "offset": "204",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_9_w0": {
        "offset": "208",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_9_w1": {
        "offset": "212",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_9_w2": {
        "offset": "216",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_9_w3": {
        "offset": "220",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_10_w0": {
        "offset": "224",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_10_w1": {
        "offset": "228",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_10_w2": {
        "offset": "232",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_key_slot_10_w3": {
        "offset": "236",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_dat_1_rsvd_0": {
        "offset": "240",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_dat_1_rsvd_1": {
        "offset": "244",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_dat_1_rsvd_2": {
        "offset": "248",
        "pos": "0",
        "bitlen": "32"
    },
    "wr_lock_rsvd_2": {
        "offset": "252",
        "pos": "0",
        "bitlen": "15"
    },
    "wr_lock_key_slot_4": {
        "offset": "252",
        "pos": "15",
        "bitlen": "1"
    },
    "wr_lock_key_slot_5": {
        "offset": "252",
        "pos": "16",
        "bitlen": "1"
    },
    "wr_lock_key_slot_6": {
        "offset": "252",
        "pos": "17",
        "bitlen": "1"
    },
    "wr_lock_key_slot_7": {
        "offset": "252",
        "pos": "18",
        "bitlen": "1"
    },
    "wr_lock_key_slot_8": {
        "offset": "252",
        "pos": "19",
        "bitlen": "1"
    },
    "wr_lock_key_slot_9": {
        "offset": "252",
        "pos": "20",
        "bitlen": "1"
    },
    "wr_lock_key_slot_10": {
        "offset": "252",
        "pos": "21",
        "bitlen": "1"
    },
    "wr_lock_dat_1_rsvd_0": {
        "offset": "252",
        "pos": "22",
        "bitlen": "1"
    },
    "wr_lock_dat_1_rsvd_1": {
        "offset": "252",
        "pos": "23",
        "bitlen": "1"
    },
    "wr_lock_dat_1_rsvd_2": {
        "offset": "252",
        "pos": "24",
        "bitlen": "1"
    },
    "rd_lock_key_slot_4": {
        "offset": "252",
        "pos": "25",
        "bitlen": "1"
    },
    "rd_lock_key_slot_5": {
        "offset": "252",
        "pos": "26",
        "bitlen": "1"
    },
    "rd_lock_key_slot_6": {
        "offset": "252",
        "pos": "27",
        "bitlen": "1"
    },
    "rd_lock_key_slot_7": {
        "offset": "252",
        "pos": "28",
        "bitlen": "1"
    },
    "rd_lock_key_slot_8": {
        "offset": "252",
        "pos": "29",
        "bitlen": "1"
    },
    "rd_lock_key_slot_9": {
        "offset": "252",
        "pos": "30",
        "bitlen": "1"
    },
    "rd_lock_key_slot_10": {
        "offset": "252",
        "pos": "31",
        "bitlen": "1"
    },
    "ef_zone_00_w0": {
        "offset": "256",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_00_w1": {
        "offset": "260",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_00_w2": {
        "offset": "264",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_00_w3": {
        "offset": "268",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_01_w0": {
        "offset": "272",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_01_w1": {
        "offset": "276",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_01_w2": {
        "offset": "280",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_01_w3": {
        "offset": "284",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_02_w0": {
        "offset": "288",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_02_w1": {
        "offset": "292",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_02_w2": {
        "offset": "296",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_02_w3": {
        "offset": "300",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_03_w0": {
        "offset": "304",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_03_w1": {
        "offset": "308",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_03_w2": {
        "offset": "312",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_03_w3": {
        "offset": "316",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_04_w0": {
        "offset": "320",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_04_w1": {
        "offset": "324",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_04_w2": {
        "offset": "328",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_04_w3": {
        "offset": "332",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_05_w0": {
        "offset": "336",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_05_w1": {
        "offset": "340",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_05_w2": {
        "offset": "344",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_05_w3": {
        "offset": "348",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_06_w0": {
        "offset": "352",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_06_w1": {
        "offset": "356",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_06_w2": {
        "offset": "360",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_06_w3": {
        "offset": "364",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_07_w0": {
        "offset": "368",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_07_w1": {
        "offset": "372",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_07_w2": {
        "offset": "376",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_07_w3": {
        "offset": "380",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_08_w0": {
        "offset": "384",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_08_w1": {
        "offset": "388",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_08_w2": {
        "offset": "392",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_08_w3": {
        "offset": "396",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_09_w0": {
        "offset": "400",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_09_w1": {
        "offset": "404",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_09_w2": {
        "offset": "408",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_09_w3": {
        "offset": "412",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_10_w0": {
        "offset": "416",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_10_w1": {
        "offset": "420",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_10_w2": {
        "offset": "424",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_10_w3": {
        "offset": "428",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_11_w0": {
        "offset": "432",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_11_w1": {
        "offset": "436",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_11_w2": {
        "offset": "440",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_11_w3": {
        "offset": "444",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_12_w0": {
        "offset": "448",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_12_w1": {
        "offset": "452",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_12_w2": {
        "offset": "456",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_12_w3": {
        "offset": "460",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_13_w0": {
        "offset": "464",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_13_w1": {
        "offset": "468",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_13_w2": {
        "offset": "472",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_13_w3": {
        "offset": "476",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_14_w0": {
        "offset": "480",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_14_w1": {
        "offset": "484",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_14_w2": {
        "offset": "488",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_14_w3": {
        "offset": "492",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_15_w0": {
        "offset": "496",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_15_w1": {
        "offset": "500",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_15_w2": {
        "offset": "504",
        "pos": "0",
        "bitlen": "32"
    },
    "ef_zone_15_w3": {
        "offset": "508",
        "pos": "0",
        "bitlen": "32"
    },
}

efuse_mac_slot_offset = {
    "slot0": "20",
    "slot1": "100",
    "slot2": "112",
}
