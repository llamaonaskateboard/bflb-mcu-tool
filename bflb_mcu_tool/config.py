# -*- coding: utf-8 -*-

import os
import sys

try:
    from version import *
except ImportError:
    version = "1.8.1"

chip_name = "tg7100c"
obj_cklink = None
ENABLE_HAIER = False
ENABLE_AITHINKER = False
NUM_ERROR_LOG = 0

if ENABLE_AITHINKER:
    version = version + " for AiThinker"

# Get app path
if getattr(sys, "frozen", False):
    app_path = os.path.dirname(sys.executable)
else:
    app_path = os.path.dirname(__file__)

try:
    import changeconf as cgc
    conf_sign = True
except ImportError:
    cgc = None
    conf_sign = False

if not conf_sign:
    back_color = "#B3DCFB"
    list_chip = ["BL602/604", "BL702/704/706", "BL702L/704L", "BL808", "BL606P", "BL616/618"]
    #list_chip = ["BL602/604", "BL702/704/706", "BL702L/704L", "BL808", "BL606P", "BL616/618", "BL628"]
    #list_chip = ["WB03"]
    type_chip = ("bl602", "bl602")
    dict_chip = {
        "BL561/563": ("bl56x", "bl60x"),
        "BL606/608": ("bl60x", "bl60x"),
        "BL562/564": ("bl562", "bl602"),
        "BL602/604": ("bl602", "bl602"),
        "BL702/704/706": ("bl702", "bl702"),
        "BL702L/704L": ("bl702l", "bl702l"),
        "BL808": ("bl808", "bl808"),
        "BL606P": ("bl606p", "bl808"),
        "BL616/618": ("bl616", "bl616"),
        "BL628": ("bl628", "bl628"),
        "WB03": ("wb03", "wb03"),
    }
    dict_chip_cmd = {
        "bl56x": "bl60x",
        "bl60x": "bl60x",
        "bl562": "bl602",
        "bl602": "bl602",
        "bl702": "bl702",
        "bl702l": "bl702l",
        "bl808": "bl808",
        "bl606p": "bl808",
        "bl616": "bl616",
        "bl628": "bl628",
        "wb03": "wb03",
    }
    flash_dict = {
        "bl56x": "bl60x",
        "bl60x": "bl60x",
        "bl562": "bl602",
        "bl602": "bl602",
        "bl702": "bl702",
        "bl702l": "bl702l",
        "bl808": "bl808",
        "bl606p": "bl808",
        "bl616": "bl616",
        "bl628": "bl628",
        "wb03": "wb03",
    }
    bl_factory_params_file_prefix = 'bl_factory_params_'
else:
    dict_chip = cgc.dict_chip
    dict_chip_cmd = cgc.dict_chip_cmd
    list_chip = cgc.list_chip
    type_chip = cgc.type_chip
    back_color = cgc.back_color
    bl_factory_params_file_prefix = cgc.show_text_first_value


def read_version_file(file_path):
    version_dict = {}
    with open(file_path, 'r', encoding='utf-8') as fp:
        for line in fp.readlines():
            line_list = line.strip().split('=')
            version_dict[line_list[0].strip()] = line_list[1].strip()
    return version_dict


xtal_type = {}
xtal_type_ = {}
pll_clk = {}
encrypt_type = {}
key_sel = {}
sign_type = {}
cache_way_disable = {}
flash_clk_type = {}
crc_ignore = {}
hash_ignore = {}
img_type = {}
boot_src = {}
cpu_type = {}

# BL60X
xtal_type['bl60x'] = ["None", "32M", "38.4M", "40M", "26M", "52M"]
xtal_type_['bl60x'] = ["XTAL_" + item for item in xtal_type['bl60x']]
pll_clk['bl60x'] = ["160M", "Manual"]
encrypt_type['bl60x'] = ["None", "AES128", "AES256", "AES192"]
key_sel['bl60x'] = ["0", "1", "2", "3"]
sign_type['bl60x'] = ["None", "ECC"]
cache_way_disable['bl60x'] = ["None", "OneWay", "TwoWay", "ThreeWay", "FourWay"]
flash_clk_type['bl60x'] = ["XTAL", "Manual"]
crc_ignore['bl60x'] = ["False", "True"]
hash_ignore['bl60x'] = ["False", "True"]
img_type['bl60x'] = ["CPU0", "CPU1", "SingleCPU", "BLSP_Boot2", "RAW"]
boot_src['bl60x'] = ["Flash", "UART/SDIO"]
cpu_type['bl60x'] = ["CPU0", "CPU1"]

# BL602
xtal_type['bl602'] = ["None", "24M", "32M", "38.4M", "40M", "26M", "RC32M"]
xtal_type_['bl602'] = ["XTAL_" + item for item in xtal_type['bl602']]
pll_clk['bl602'] = ["160M", "Manual"]
encrypt_type['bl602'] = ["None", "AES128", "AES256", "AES192"]
#key_sel['bl602'] = ["0", "1", "2", "3"]
key_sel['bl602'] = ["0"]
sign_type['bl602'] = ["None", "ECC"]
cache_way_disable['bl602'] = ["None", "OneWay", "TwoWay", "ThreeWay", "FourWay"]
flash_clk_type['bl602'] = ["XTAL", "Manual"]
crc_ignore['bl602'] = ["False", "True"]
hash_ignore['bl602'] = ["False", "True"]
img_type['bl602'] = ["SingleCPU", "RAW"]
boot_src['bl602'] = ["Flash", "UART/SDIO"]

# BL702
xtal_type['bl702'] = ["None", "32M", "RC32M"]
xtal_type_['bl702'] = ["XTAL_" + item for item in xtal_type['bl702']]
pll_clk['bl702'] = ["144M", "Manual"]
encrypt_type['bl702'] = ["None", "AES128", "AES256", "AES192"]
#key_sel['bl702'] = ["0", "1", "2", "3"]
key_sel['bl702'] = ["1"]
sign_type['bl702'] = ["None", "ECC"]
cache_way_disable['bl702'] = ["None", "OneWay", "TwoWay", "ThreeWay", "FourWay"]
flash_clk_type['bl702'] = ["XCLK", "Manual"]
crc_ignore['bl702'] = ["False", "True"]
hash_ignore['bl702'] = ["False", "True"]
img_type['bl702'] = ["SingleCPU", "RAW"]
boot_src['bl702'] = ["Flash", "UART/USB"]

# BL702L
xtal_type['bl702l'] = ["None", "32M", "RC32M"]
xtal_type_['bl702l'] = ["XTAL_" + item for item in xtal_type['bl702l']]
pll_clk['bl702l'] = ["144M", "Manual"]
encrypt_type['bl702l'] = ["None", "AES128", "AES256", "AES192"]
#key_sel['bl702l'] = ["0", "1", "2", "3"]
key_sel['bl702l'] = ["1"]
sign_type['bl702l'] = ["None", "ECC"]
cache_way_disable['bl702l'] = ["None", "OneWay", "TwoWay", "ThreeWay", "FourWay"]
flash_clk_type['bl702l'] = ["XCLK", "Manual"]
crc_ignore['bl702l'] = ["False", "True"]
hash_ignore['bl702l'] = ["False", "True"]
img_type['bl702l'] = ["SingleCPU", "RAW"]
boot_src['bl702l'] = ["Flash", "UART/USB"]

# BL808
xtal_type['bl808'] = ["None", "24M", "32M", "38.4M", "40M", "26M", "RC32M", "Auto"]
xtal_type_['bl808'] = ["XTAL_" + item for item in xtal_type['bl808']]
pll_clk['bl808'] = ["WIFIPLL 320M", "Manual"]
encrypt_type['bl808'] = ["None", "AES CTR128", "AES CTR256", "AES CTR192", "AES XTS128", "AES XTS256", "AES XTS192"]
key_sel['bl808'] = ["0", "1", "2", "3"]
sign_type['bl808'] = ["None", "ECC"]
cache_way_disable['bl808'] = ["None", "OneWay", "TwoWay", "ThreeWay", "FourWay"]
flash_clk_type['bl808'] = ["XTAL", "Manual"]
crc_ignore['bl808'] = ["False", "True"]
hash_ignore['bl808'] = ["False", "True"]
img_type['bl808'] = ["SingleCPU", "RAW"]
boot_src['bl808'] = ["Flash", "UART/USB"]
cpu_type['bl808'] = ["Group0", "Group1"]

# BL606P
xtal_type['bl606p'] = ["None", "24M", "32M", "38.4M", "40M", "26M", "RC32M", "Auto"]
xtal_type_['bl606p'] = ["XTAL_" + item for item in xtal_type['bl808']]
pll_clk['bl606p'] = ["WIFIPLL 320M", "Manual"]
encrypt_type['bl606p'] = ["None", "AES CTR128", "AES CTR256", "AES CTR192", "AES XTS128", "AES XTS256", "AES XTS192"]
key_sel['bl606p'] = ["0", "1", "2", "3"]
sign_type['bl606p'] = ["None", "ECC"]
cache_way_disable['bl606p'] = ["None", "OneWay", "TwoWay", "ThreeWay", "FourWay"]
flash_clk_type['bl606p'] = ["XTAL", "Manual"]
crc_ignore['bl606p'] = ["False", "True"]
hash_ignore['bl606p'] = ["False", "True"]
img_type['bl606p'] = ["SingleCPU", "RAW"]
boot_src['bl606p'] = ["Flash", "UART/USB"]
cpu_type['bl606p'] = ["Group0", "Group1"]

# BL616
xtal_type['bl616'] = ["None", "24M", "32M", "38.4M", "40M", "26M", "RC32M", "Auto"]
xtal_type_['bl616'] = ["XTAL_" + item for item in xtal_type['bl616']]
pll_clk['bl616'] = ["WIFIPLL 320M", "Manual"]
encrypt_type['bl616'] = ["None", "AES CTR128", "AES CTR256", "AES CTR192", "AES XTS128", "AES XTS256", "AES XTS192"]
key_sel['bl616'] = ["0", "1", "2", "3"]
sign_type['bl616'] = ["None", "ECC"]
cache_way_disable['bl616'] = ["None", "OneWay", "TwoWay", "ThreeWay", "FourWay"]
flash_clk_type['bl616'] = ["XTAL", "Manual"]
crc_ignore['bl616'] = ["False", "True"]
hash_ignore['bl616'] = ["False", "True"]
img_type['bl616'] = ["SingleCPU", "RAW"]
boot_src['bl616'] = ["Flash", "UART/USB"]

# BL628
xtal_type['bl628'] = ["None", "24M", "32M", "38.4M", "40M", "26M", "RC32M", "Auto"]
xtal_type_['bl628'] = ["XTAL_" + item for item in xtal_type['bl628']]
pll_clk['bl628'] = ["WIFIPLL 320M", "Manual"]
encrypt_type['bl628'] = ["None", "AES CTR128", "AES CTR256", "AES CTR192", "AES XTS128", "AES XTS256", "AES XTS192"]
key_sel['bl628'] = ["0", "1", "2", "3"]
sign_type['bl628'] = ["None", "ECC"]
cache_way_disable['bl628'] = ["None", "OneWay", "TwoWay", "ThreeWay", "FourWay"]
flash_clk_type['bl628'] = ["XTAL", "Manual"]
crc_ignore['bl628'] = ["False", "True"]
hash_ignore['bl628'] = ["False", "True"]
img_type['bl628'] = ["SingleCPU", "RAW"]
boot_src['bl628'] = ["Flash", "UART/USB"]
cpu_type['bl628'] = ["Group0", "Group1"]

# WB03
xtal_type['wb03'] = ["None", "24M", "32M", "38.4M", "40M", "26M", "RC32M", "Auto"]
xtal_type_['wb03'] = ["XTAL_" + item for item in xtal_type['wb03']]
pll_clk['wb03'] = ["WIFIPLL 320M", "Manual"]
encrypt_type['wb03'] = ["None", "AES CTR128", "AES CTR256", "AES CTR192", "AES XTS128", "AES XTS256", "AES XTS192"]
key_sel['wb03'] = ["0", "1", "2", "3"]
sign_type['wb03'] = ["None", "ECC"]
cache_way_disable['wb03'] = ["None", "OneWay", "TwoWay", "ThreeWay", "FourWay"]
flash_clk_type['wb03'] = ["XTAL", "Manual"]
crc_ignore['wb03'] = ["False", "True"]
hash_ignore['wb03'] = ["False", "True"]
img_type['wb03'] = ["SingleCPU", "RAW"]
boot_src['wb03'] = ["Flash", "UART/USB"]

try:
    logo1 = '''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
            AQADByJ1+Dnq3AAAAABJRU5ErkJggg=='''
    logo2 = '''AAABAAEAICAAAAEAGADYAQAAFgAAAIlQTkcNChoKAAAADUlIRFIAAAAgAAAAIAgGAAAAc3p69AAAA
            AFzUkdCAK7OHOkAAAAEZ0FNQQAAsY8L/GEFAAAACXBIWXMAAA7DAAAOwwHHb6hkAAABbUlEQVRYR2NgG
            AWjITAaAqMhMBoCJIaATusecaOWff+xYcOmvVdDV61iJtFIBgawYU17o/BpNGg94IrLYqyOaTxgic88n
            Ya9tUYte/+C1Ri07s0EGaLftK8cXZNR814nUixGV2tYv98Ew8yWvStA6nTbdyvB5Qxb9s2ixCKS9Tbvi
            8YaQkbN+36QbBiONIHVnOa9n0hOIyANVp0bePXr9wto1a9is6/fz4HN8NDQVcwTt91in7//vsCq/S959
            u//z0KWZdg0IVto2LL3OUgNkH4EEjds3teGrGf+kQcHYJimDsBmePeO6996dt38D8N0dwDVLMTMOojCB
            xYF1Wsv/8eHq9ZehuRzagBsaSBtwemnaQvPvMeHQ1ddYaOG/ZDSEophIUAVg4k1hBQHBE099h+GAycfe
            UCsHXjVoTngKzDr9ROD9Vv2SFPdAaSUlFSxHGQIKZbC1FLNcrADmveeJwE7UdXyUcNGQ4CWIQAAiakrc
            tfuVAEAAAAASUVORK5CYII='''
except Exception:
    logo1 = ""
    logo2 = ""

if conf_sign:
    about_tool = '''
            <html><body>
            <table bgcolor="''' + back_color + '''" width="100%" cellspacing="2" cellpadding="1" border="0">
            <tr>
            <td align="center"><font face="微软雅黑" color=\"grey\"><h2>{}</h2></font></td>
            </tr>
            <tr>
            <td align="center"><font face="微软雅黑" color=\"grey\" size=2>version: '''.format(cgc.title) + version + '''</font></td>
            </tr>
            </table>
            <br><br><br>
            <font color = \"black\" size=3 face="微软雅黑">
            <ul>
            <li>simple flasher
            <li>image tool
            <li>partition tool
            <li>security tool
            <li>efuse key tool
            <li>flash utils
            <li>iap tool
            <li>mfg tool
            </ul>
            </font>
            </body></html>
    '''
else:
    about_tool = '''\
                <html><body>
                <table bgcolor="''' + back_color + '''" width="100%" cellspacing="2"
                cellpadding="1" border="0">
                <tr>
                <td align="center"><font face="微软雅黑" color=\"grey\"><h2>Bouffalo Lab Dev Cube</h2></font></td>
                </tr>
                <tr>
                <td align="center"><font face="微软雅黑" color=\"grey\" size=2>version: ''' + version + '''</font></td>
                </tr>
                <tr>
                <td align="center"><font face="微软雅黑" color=\"grey\" size=2>jxtan@bouffalolab.com</font></td>
                </tr>
                </table>
                <br><br><br>
                <font color = \"black\" size=3 face="微软雅黑">
                <ul>
                <li>iot tool
                <li>mcu tool
                <li>partition tool
                <li>security tool
                <li>efuse key tool
                <li>flash utils
                <li>rf mfg tool
                </ul>
                </font>   
                </body></html>
    '''

DEFAULT_STYLE = """
QProgressBar{
    border: 1px solid grey;
    border-radius: 5px;
    text-align: center
}

QProgressBar::chunk {
    background-color: grey;
    width: 1px;
    margin: 0.1px;
}
"""

SUCCESS_STYLE = """
QProgressBar{
    border: 1px solid grey;
    border-radius: 5px;
    text-align: center
}

QProgressBar::chunk {
    background-color: green;
    width: 1px;
    margin: 0.1px;
}
"""

ERROR_STYLE = """
QProgressBar{
    border: 1px solid grey;
    border-radius: 5px;
    text-align: center
}

QProgressBar::chunk {
    background-color: red;
    width: 1px;
    margin: 0.1px;
}
"""

WARN_STYLE = """
QProgressBar{
    border: 1px solid grey;
    border-radius: 5px;
    text-align: center
}

QProgressBar::chunk {
    background-color: orange;
    width: 1px;
    margin: 0.1px;
}
"""
