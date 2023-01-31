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

import sys
import time
import socket
import threading
import binascii
import concurrent.futures

from Crypto.Util import Counter
from Crypto.Cipher import AES
from Crypto.Hash import SHA256

try:
    import bflb_path
except ImportError:
    from libs import bflb_path
import config as gol
from libs import bflb_eflash_loader
from libs import bflb_version
from libs import bflb_ecdh
from libs import bflb_utils
from libs.bflb_utils import eflash_loader_parser_init

total_cnt = 0
success_cnt = 0
ecdh_enable = False

try:
    import changeconf as cgc
    conf_sign = True
except ImportError:
    conf_sign = False


def create_decrypt_data(data_bytearray, key_bytearray, iv_bytearray):
    cryptor = AES.new(key_bytearray, AES.MODE_CBC, iv_bytearray)
    plaintext = cryptor.decrypt(data_bytearray)
    return plaintext


def eflash_loader_server(socket_server, port, echo, aes_key):
    ecdh_shared_key = None
    socket_address = ('', port)
    socket_server.bind(socket_address)
    bflb_utils.enable_udp_send_log(echo)
    try:
        while True:
            try:
                recv_data, recv_addr = socket_server.recvfrom(1024)
                bflb_utils.printf('\n')
                bflb_utils.printf('Recieve:[from IP:<%s>]' % recv_addr[0])
            except Exception as e:
                bflb_utils.printf(e)
                continue
            global ecdh_enable
            if aes_key:
                try:
                    if len(recv_data) % 16 != 0:
                        recv_data = recv_data + bytearray(16 - (len(recv_data) % 16))
                    recv_data = create_decrypt_data(recv_data, bytearray.fromhex(aes_key),
                                                    bytearray(16))
                    i = 0
                    while True:
                        if recv_data[i:i + 1] == bytearray(1):
                            recv_data = recv_data[0:i]
                            break
                        i += 1
                except Exception as e:
                    bflb_utils.printf(e)
            elif ecdh_enable:
                if ecdh_shared_key is None:
                    try:
                        tmp_ecdh = bflb_ecdh.BflbEcdh()
                        ssk = tmp_ecdh.create_public_key()
                        ecdh_private_key = binascii.hexlify(
                            tmp_ecdh.ecdh.private_key.to_string()).decode("utf-8")
                        # bflb_utils.printf("ecdh private key")
                        # bflb_utils.printf(ecdh_private_key)
                        if recv_data.decode('utf-8', 'ignore').startswith("csk:"):
                            ecdh_peer_public_key = binascii.hexlify(recv_data[4:]).decode("utf-8")
                            # bflb_utils.printf("ecdh peer key")
                            # bflb_utils.printf(ecdh_peer_public_key)
                            ecdh_shared_key = tmp_ecdh.create_shared_key(ecdh_peer_public_key)
                            socket_server.sendto(
                                bytearray.fromhex(binascii.hexlify(b'ssk:').decode("utf-8") + ssk),
                                recv_addr)
                            continue
                    except Exception as e:
                        bflb_utils.printf(e)
                else:
                    try:
                        if len(recv_data) % 16 != 0:
                            recv_data = recv_data + bytearray(16 - (len(recv_data) % 16))
                        recv_data = create_decrypt_data(recv_data,
                                                        bytearray.fromhex(ecdh_shared_key[0:32]),
                                                        bytearray(16))
                        ecdh_shared_key = None
                        i = 0
                        while True:
                            if recv_data[i:i + 1] == bytearray(1):
                                recv_data = recv_data[0:i]
                                break
                            i += 1
                    except Exception as e:
                        bflb_utils.printf(e)

            if recv_data.decode('utf-8', 'ignore').startswith("stop"):
                break
            eflash_loader_monitor_thread = threading.Thread(target=eflash_loader_monitor,
                                                            args=(recv_addr, recv_data))

            eflash_loader_monitor_thread.start()
            time.sleep(0.001)
    finally:
        return


def eflash_loader_monitor(client_addr, client_data):
    global total_cnt, success_cnt
    total_cnt += 1
    try:
        # eflash_loader_worker_thread = threading.Thread(target=eflash_loader_worker,
        #                                                args=(socket_server, client_addr, client_data))
        # eflash_loader_worker_thread.start()
        # bflb_utils.printf(eflash_loader_worker_thread.join())
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(eflash_loader_worker, client_addr, client_data)
            return_value = future.result()
            if return_value:
                success_cnt += 1
            bflb_utils.printf("State:" + str(success_cnt) + "/" + str(total_cnt))
    except Exception:
        bflb_utils.printf("eflash_loader_monitor fail")
        bflb_utils.printf("State:" + str(success_cnt) + "/" + str(total_cnt))


def eflash_loader_worker(client_addr, client_data):
    tid = threading.get_ident()
    request = client_data.decode('utf-8')
    bflb_utils.printf("Worker ID:" + str(tid) + " deal request:" + request)
    bflb_utils.add_udp_client(str(tid), client_addr)
    ret = False
    try:
        parser = eflash_loader_parser_init()
        args = parser.parse_args(request.split(" "))
        eflash_loader_t = bflb_eflash_loader.BflbEflashLoader(args.chipname,
                                                              gol.dict_chip_cmd[args.chipname])
        ret = eflash_loader_t.efuse_flash_loader(args, None, None)
    finally:
        udp_socket_result = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        bflb_utils.remove_udp_client(str(tid))
        if ret is True:
            udp_socket_result.sendto(
                bytearray.fromhex(binascii.hexlify(b'Finished with success').decode("utf-8")),
                client_addr)
            bflb_utils.printf("Worker ID:" + str(tid) + " Finished with success")
            udp_socket_result.close()
            del eflash_loader_t
            return True
        else:
            udp_socket_result.sendto(
                bytearray.fromhex(binascii.hexlify(b'Finished with fail').decode("utf-8")),
                client_addr)
            bflb_utils.printf("Worker ID:" + str(tid) + " Finished with fail!!!!!!!!!")
            udp_socket_result.close()
            del eflash_loader_t
            return False


def usage():
    bflb_utils.printf(sys.argv[0])
    bflb_utils.printf("-p/--port=     :specify UDP listen port")
    bflb_utils.printf("--echo         :open local log echo")
    bflb_utils.printf("--ecdh         :open ecdh function")
    bflb_utils.printf("--key=         :aes 128 encrypt")


def eflash_loader_server_main():
    global ecdh_enable
    port = 8080
    echo = False
    aes_key = ""
    parser = eflash_loader_parser_init()
    args = parser.parse_args()
    if conf_sign:
        bflb_utils.printf(
            "Version: ",
            bflb_version.eflash_loader_version_text.replace(
                'bflb', cgc.eflash_loader_version_text_first_value))
    else:
        bflb_utils.printf("Version: ", bflb_version.eflash_loader_version_text)
    if args.port:
        port = int(args.port)
    if args.key:
        aes_key = args.key
    if args.ecdh:
        ecdh_enable = True
        bflb_utils.printf("ECDH Enable")
    else:
        ecdh_enable = False
    if args.echo:
        echo = True
    if args.usage:
        usage()
        return
    if aes_key != "" and ecdh_enable is True:
        bflb_utils.printf("key and ecdh can only set one")
        time.sleep(2)
        sys.exit()
    socket_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    bflb_utils.printf("Listening on " + str(port))
    eflash_loader_server_thread = threading.Thread(target=eflash_loader_server,
                                                   args=(socket_server, port, echo, aes_key))
    eflash_loader_server_thread.start()


if __name__ == '__main__':
    eflash_loader_server_main()
