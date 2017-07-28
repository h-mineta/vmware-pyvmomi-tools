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

    parser.add_argument('-V', '--vmhosts',
                        required=True,
                        action='append',
                        help='VMhost names')

    parser.add_argument('-P', '--destination-pool',
                        required=False,
                        default=None,
                        help='Destination resource pool name')

    parser.add_argument('-H', '--destination-esxi',
                        required=False,
                        default=None,
                        help='Destination ESXi hostname')

    parser.add_argument('-D', '--destination-datastore',
                        required=False,
                        default=None,
                        help='Destination datastore name')

    parser.add_argument('--verbose',
                        action='store_true',
                        default=False,
                        help='Verbose mode(default: False)',)

    parser.add_argument('--timezone',
                        required=False,
                        default='Asia/Tokyo',
                        help='Default time zone (Asia/Tokyo)')

    return cli.prompt_for_password(parser.parse_args())

def print_task(task, timezone_name='Asia/Tokyo'):
    error_type = None
    message = ''

    if task.error != None:
        error = task.error
        if isinstance(error, vmodl.fault.InvalidArgument):
            error_type = 'InvalidArgument'

        elif isinstance(error, vmodl.RuntimeFault):
            error_type = 'RuntimeFault'

        if isinstance(error, vim.fault.DisallowedOperationOnFailoverHost):
            error_type = 'DisallowedOperationOnFailoverHost'

        elif isinstance(error, vim.fault.FileFault):
            error_type = 'FileFault'

        elif isinstance(error, vim.fault.InsufficientResourcesFault):
            error_type = 'InsufficientResourcesFault'

        elif isinstance(error, vmodl.fault.InvalidArgument):
            error_type = 'InvalidArgument'

        elif isinstance(error, vim.fault.InvalidState):
            if isinstance(error, vim.fault.InvalidPowerState):
                error_type = 'InvalidPowerState'
            elif isinstance(error, vim.fault.InvalidDatastore):
                error_type = 'InvalidDatastore'
            elif isinstance(error, vim.fault.InvalidHostState):
                error_type = 'InvalidHostState'
            elif isinstance(error, vim.fault.InvalidVmState):
                error_type = 'InvalidVmState'
            elif isinstance(error, vim.fault.VmPowerOnDisabled):
                error_type = 'VmPowerOnDisabled'
            else:
                error_type = 'InvalidState'

        elif isinstance(error, vim.fault.MigrationFault):
            error_type = 'MigrationFault'

        elif isinstance(error, vim.fault.Timedout):
            error_type = 'Timedout'

        elif isinstance(error, vim.fault.VmConfigFault):
            error_type = 'VmConfigFault'

        else:
            error_type = str(type(error))

        # error message
        if hasattr(error, 'msg'):
            message = error.msg

    tz = pytz.timezone(timezone_name)
    time_to_queue = tz.normalize(task.queueTime.astimezone(tz))
    time_to_start = tz.normalize(task.startTime.astimezone(tz))
    time_to_complite = "unset"
    time_to_difference = "unset"
    if task.completeTime:
        time_to_complite = tz.normalize(task.completeTime.astimezone(tz))
        time_to_difference = task.completeTime - task.startTime

    output = "View TaskInfo" \
        + "\n Task          : " + str(task.task).strip('\'') \
        + "\n Queue time    : " + time_to_queue.strftime('%Y-%m-%d %H:%M:%S %Z') \
        + "\n Start time    : " + time_to_start.strftime('%Y-%m-%d %H:%M:%S %Z') \
        + "\n Complete time : " + time_to_complite.strftime('%Y-%m-%d %H:%M:%S %Z') \
        + "\n Diff time     : " + str(time_to_difference) + ' (complete - start)' \
        + "\n Name          : " + task.entityName \
        + "\n Entyty        : " + str(task.entity).strip('\'') \
        + "\n State         : " + task.state \
        + "\n Cancelled     : " + str(task.cancelled) \
        + "\n Cancelable    : " + str(task.cancelable)

    if error_type:
        output = output \
            + "\n Error type    : " + error_type \
            + "\n Error message : " + message
        logger.error(output + "\n")

    else:
        logger.info(output + "\n")

def wait_for_tasks(service_instance, tasks):
    finish_tasks = {}

    if not len(tasks):
        return finish_tasks

    property_collector = service_instance.content.propertyCollector
    task_list = [str(task) for task in tasks]
    # Create filter
    obj_specs = [vmodl.query.PropertyCollector.ObjectSpec(obj=task)
                 for task in tasks]
    property_spec = vmodl.query.PropertyCollector.PropertySpec(type=vim.Task,
                                                               pathSet=[],
                                                               all=True)
    filter_spec = vmodl.query.PropertyCollector.FilterSpec()
    filter_spec.objectSet = obj_specs
    filter_spec.propSet = [property_spec]
    pcfilter = property_collector.CreateFilter(filter_spec, True)
    atexit.register(pcfilter.Destroy)

    try:
        version = None
        # Loop looking for updates till the state moves to a completed state.
        while len(task_list):
            update = property_collector.WaitForUpdates(version)
            for filter_set in update.filterSet:
                for obj_set in filter_set.objectSet:
                    task = obj_set.obj
                    task_name = str(task)
                    if not task_name in task_list:
                        continue

                    for change in obj_set.changeSet:
                        # Append finish task values
                        if isinstance(change.val, vim.TaskInfo):
                            # set
                            finish_tasks[task_name] = change.val
                            logger.info("Name: %s, State: %s" % (finish_tasks[task_name].entityName, finish_tasks[task_name].state))

                        elif task_name in finish_tasks:
                            matchese = re.match(r'^info\.(.+)$', change.name)
                            if matchese:
                                # modify(Update)
                                key = matchese.group(1)
                                setattr(finish_tasks[task_name], key, change.val)
                                if key == 'progress' and isinstance(change.val, int) == True:
                                    logger.debug("Name: %s, Progress: %d" % (finish_tasks[task_name].entityName, change.val))
                                elif key == 'state':
                                    if change.val == 'error':
                                        logger.error("Name: %s, State: %s" % (finish_tasks[task_name].entityName, change.val))
                                    else:
                                        logger.info("Name: %s, State: %s" % (finish_tasks[task_name].entityName, change.val))

                    if task_name in finish_tasks \
                    and (finish_tasks[task_name].state == 'success' or finish_tasks[task_name].state == 'error') \
                    and finish_tasks[task_name].completeTime != None:
                        # Remove task from taskList
                        task_list.remove(task_name)

            # Move to next version
            version = update.version

    except vmodl.RuntimeFault as ex:
        logger.error('Caught RuntimeFault fault : ' + ex.msg)

    except vmodl.MethodFault as ex:
        logger.error('Caught MethodFault fault : ' + ex.msg)

    except Exception as ex:
        raise

    return finish_tasks

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

    if not args.destination_esxi and not args.destination_datastore:
        logger.critical("Could not destination esxi or datastore")
        sys.exit(1)

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
        vm_list = get.get_vms_by_names(content, args.vmhosts)
        if len(vm_list) == 0:
            logger.warning('Virtual Machine is not found')
            sys.exit(1)

        # Relocate(vMotion)のためのSpecデータ作成
        relocate_spec = vim.VirtualMachineRelocateSpec()
        if args.destination_esxi:
            relocate_spec.host  = get.get_host_by_name(content, args.destination_esxi)
            if relocate_spec.host is None:
                logger.warning('ESXi host is not found')
                sys.exit(1)

        if args.destination_datastore:
            relocate_spec.datastore = get.get_datastore_by_name(content, args.destination_datastore)
            if relocate_spec.datastore is None:
                logger.warning('Datastore is not found')
                sys.exit(1)

        if args.destination_pool:
            relocate_spec.pool = get.get_pool(content, args.destination_pool)
            if relocate_spec.pool is None:
                logger.warning('Pool is not found')
                sys.exit(1)

        # 例) ['vim.Task:task-1137', 'vim.Task:task-1138', 'vim.Task:task-1139']
        task_list = [vm.RelocateVM_Task(spec=relocate_spec, priority='defaultPriority') for vm in vm_list]

        if len(task_list) == 0:
            logger.error('Relocate task is not create')
            sys.exit(2)

        finish_tasks = {}
        finish_tasks = wait_for_tasks(service_instance, task_list)

        if len(finish_tasks) == 0:
            logger.error('Finish task is not found')
            sys.exit(2)

        for key in finish_tasks.keys():
            print_task(finish_tasks[key], args.timezone)
            if finish_tasks[key].state == 'error':
                exit_status = 2

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
