#!/usr/bin/env python

from setuptools import setup, find_packages

longdesc = """
## Bouffalolab Mcu Command Tool
====================================

The functions of bflb_mcu_tool is the same as DevCube(MCU View) which is a GUI tool for image programing.
bflb_mcu_tool is designed for the convenience of integrating into the compilation system after image buid,
and making it more easy for users who are accustomed to using command line operations.

### basic download config:

* --chipname：mandatory, name of chip(bl602/bl702/bl616...)
* --interface：1.uart, 2.jlink, 3.cklink, 4.openocd, default is uart
* --bootsrc：1.flash, 2.uart/sdio, 3.uart/usb, default is flash
* --port：serial port or jlink serial number
* --baudrate：baudrate of serial port, default is 115200
* --xtal：xtal on the board, for bl602,1:24M,2:32M,3:38.4M,4:40M(default value when not specified),5:26M; for bl702,1:32M(default value when not specified); for bl616,just use value 7(auto adjust)
* --config：eflash loader configuration file,default is chips/blXXXX/eflash_loader/eflash_loader_cfg.ini
* --flashclk：clock of flash
* --pllclk：clock of pll

### files for download:

* --firmware：mandatory, select the firmware binary file which your sdk build out
* --dts：optional,select the device tree file you used
* --addr：address to program, default is 0x2000
* --erase：erase the whole flash

### other options:

* --build：build image only

### EXAMPLE:
* bflb_mcu_tool.exe --chipname=bl602 --port=COM28 --baudrate=2000000 --firmware="helloworld_bl602.bin"
* bflb_mcu_tool.exe --chipname=bl602 --port=COM28 --baudrate=2000000 --firmware="helloworld_bl602.bin" --erase
* bflb_mcu_tool.exe --chipname=bl602 --port=COM28 --baudrate=2000000 --firmware="helloworld_bl602.bin" --build

"""

packages = [
    'bflb_mcu_tool',
    'bflb_mcu_tool.core',
    'bflb_mcu_tool.libs',
    'bflb_mcu_tool.libs.bl616',
    'bflb_mcu_tool.libs.bl602',
    'bflb_mcu_tool.libs.bl702',
    'bflb_mcu_tool.libs.bl702l',
    'bflb_mcu_tool.libs.bl808',
]

entry_points = {'console_scripts': ['bflb-mcu-tool = bflb_mcu_tool.__main__:run_main']}

setup(
    name="bflb-mcu-tool",
    version="1.8.1",
    author="bouffalolab",
    author_email="jxtan@bouffalolab.com",
    description="Bouffalolab Mcu Tool",
    long_description=longdesc,
    long_description_content_type="text/markdown",
    license="MIT",
    url="https://pypi.org/project/bflb-mcu-tool/",
    packages=packages,  # 包的代码主目录
    #package_data=package_data,
    include_package_data=True,
    entry_points=entry_points,
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: MacOS',
        'Operating System :: Microsoft',
        'Operating System :: Unix',
        'Environment :: Console',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Programming Language :: Python :: 3',
    ],
    install_requires=[
        'ecdsa>=0.15',
        'pycryptodome==3.9.8',
        'bflb-crypto-plus==1.0',
        'pycklink>=0.1.1',
        'pyserial==3.5',
        'pylink-square==0.5.0',
        'portalocker==2.0.0'       
    ],
    python_requires='>=3.6',
    zip_safe=False,
)
