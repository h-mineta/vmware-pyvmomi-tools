#!/usr/bin/python3.5 -tt
# -*- coding: utf-8 -*-

"""
Copyright (c) 2017 h-mineta <h-mineta@0nyx.net>
This software is released under the MIT License.

pip3 install pyvmomi pytz
"""

import atexit
import sys
import re
from datetime import datetime
from logging import getLogger, Formatter, StreamHandler, CRITICAL, WARNING, INFO, DEBUG
logger = getLogger(__name__)

from pyVim import connect
from pyVmomi import vmodl
from pyVmomi import vim
import pytz

from tools import cli, get

def setup_args():
    parser = cli.build_arg_parser()

    parser.add_argument('-V', '--vmhost',
                        required=True,
                        help='VMhost name')

    parser.add_argument('-O', '--poweroff',
                        action='store_true',
                        default=False,
                        help='Power off virtual machine')

    parser.add_argument('--verbose',
                        action='store_true',
                        default=False,
                        help='Verbose mode(default: False)')

    parser.add_argument('--timezone',
                        required=False,
                        default='Asia/Tokyo',
                        help='Default time zone (Asia/Tokyo)')

    return cli.prompt_for_password(parser.parse_args())

def main():
    args = setup_args()
    exit_status = 0

    # logger setting
    formatter = Formatter('[%(asctime)s]%(levelname)s - %(message)s')
    #formatter = Formatter('[%(asctime)s][%(funcName)s:%(lineno)d]%(levelname)s - %(message)s')
    logger.setLevel(DEBUG) # debug 固定

    console = StreamHandler()
    if hasattr(args, 'verbose') and args.verbose == True:
        console.setLevel(DEBUG)
    else:
        console.setLevel(INFO)
    console.setFormatter(formatter)
    logger.addHandler(console)

    try:
        if args.disable_ssl_verification:
            service_instance = connect.SmartConnectNoSSL(host=args.host,
                                                         user=args.user,
                                                         pwd=args.password,
                                                         port=int(args.port))
        else:
            service_instance = connect.SmartConnect(host=args.host,
                                                    user=args.user,
                                                    pwd=args.password,
                                                    port=int(args.port))

        if not service_instance:
            logger.critical("Could not connect to the specified host ' \
                            'using specified username and password")
            sys.exit(1)

        atexit.register(connect.Disconnect, service_instance)

        content = service_instance.RetrieveContent()

        # VM List作成
        vm_list = get.get_vms_by_names(content, args.vmhost)
        if len(vm_list) == 0:
            logger.warning('Virtual Machine is not found')
            sys.exit(1)

        summary = vm_list[0].summary
        power = summary.runtime.powerState
        logger.info("Power state: %s" % (power))
        if args.poweroff == True and power == 'poweredOn':
            logger.warning('Virtual machine is powered on.')
            sys.exit(3)
        elif args.poweroff == False and power == 'poweredOff':
            logger.warning('Virtual machine is powered off.')
            sys.exit(3)

    except vmodl.MethodFault as ex:
        logger.critical('Caught vmodl fault : ' + ex.msg)
        import traceback
        traceback.print_exc()
        sys.exit(253)

    except Exception as ex:
        logger.critical('Caught exception : ' + str(ex))
        import traceback
        traceback.print_exc()
        sys.exit(254)

    sys.exit(exit_status)

# Start program
if __name__ == "__main__":
    main()
