from pyVim import connect
from pyVmomi import vmodl
from pyVmomi import vim

__author__ = "h-mineta@0nyx.net"

def _get_objects(content, vimtype):
    container_view = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
    containers = container_view.view
    container_view.Destroy()

    return containers

def _get_objects_by_names(content, vimtype, names):
    objects = []
    containers = _get_objects(content, vimtype)
    for container in containers:
        if container.name in names:
            objects.append(container)

    return objects

def _get_name_by_object(content, vimtype, object_):
    name = None
    containers = _get_objects(content, vimtype)
    for container in containers:
        if container == object_:
            name = container.name
            break

    return name

def get_vm_by_name(content, name):
    objects = _get_objects_by_names(content, [vim.VirtualMachine], [name])
    if len(objects):
        return objects[0]
    else:
        return None

def get_vms_by_names(content, names):
    return _get_objects_by_names(content, [vim.VirtualMachine], names)

def get_host_by_name(content, name):
    objects = _get_objects_by_names(content, [vim.HostSystem], [name])
    if len(objects):
        return objects[0]
    else:
        return None

def get_hosts_by_names(content, names):
    return _get_objects_by_names(content, [vim.HostSystem], names)

def get_datastore_by_name(content, name):
    objects = _get_objects_by_names(content, [vim.Datastore], [name])
    if len(objects):
        return objects[0]
    else:
        return None

def get_datastores_by_names(content, names):
    return _get_objects_by_names(content, [vim.Datastore], names)

def get_pool(content, identifer):
    return get_pool_by_identifer(content, identifer)

def get_pool_by_identifer(content, identifer):
    object_ = None
    containers = _get_objects(content, [vim.ResourcePool])
    for container in containers:
        if str(container).strip('\'') == identifer:
            object_ = container
            break

    return object_
