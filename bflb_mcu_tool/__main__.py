# -*- coding:utf-8 -*-

import sys
from core import bflb_mcu_tool

def run_main():
    bflb_mcu_tool.run(sys.argv[1:])

if __name__ == '__main__':
    run_main()