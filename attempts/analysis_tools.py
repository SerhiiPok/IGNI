import os
import sys

import kaitaistruct

from collections.abc import Iterable
import matplotlib
import matplotlib.pyplot as plt


def resolve_relative_path(rel_path):
    return os.path.realpath(os.path.join(ROOT, rel_path))


ROOT = os.path.dirname(os.path.realpath(__file__))

# import mdb binding --
sys.path.append(resolve_relative_path('bindings/python'))
from mdb import Mdb

# --

# exposed functions --
EXPOSED_FUNCTIONS = []


def exposed(description):
    def exposed_function(func):
        EXPOSED_FUNCTIONS.append([func, description])
        return func

    return exposed_function


# --


CONTENT_DIR = os.path.realpath(os.path.join(ROOT, 'unbiffed'))
MESH_DIR = os.path.realpath(os.path.join(ROOT, 'unbiffed/meshes00'))


class ResourceType:
    def __init__(self, name, extension, validator=None, description=None):
        self.name = name
        self.extension = extension

        if validator is None:
            self.user_validate = lambda s: True
        else:
            self.user_validate = validator

        self.description = '' if description is None else description

    def validate(self, fpath):
        if not fpath.endswith(self.extension):
            return False
        return self.user_validate(fpath)

    def __str__(self):
        return self.name

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if not isinstance(other, ResourceType):
            return False
        else:
            if self.name == other.name:
                return True


def is_true_binary_3d(fpath):
    bytes = open(fpath, 'rb').read(4)
    return not (any([b != 0 for b in bytes]))


class ResourceLoader:
    class ResourceTypes:
        MDB = ResourceType('MDB', '.mdb', validator=lambda s: is_true_binary_3d(s))  # binary witcher 3d model
        MBA = ResourceType('MBA', '.mba', validator=lambda s: is_true_binary_3d(s))  # binary animation but has same binary structure as MDB
        CMDB = ResourceType('CMDB', '.mdb',
                            description='compound model (text format)',
                            validator=lambda s: not is_true_binary_3d(s))  # compound binary model - is a text-based format !

    RESOURCE_LOADERS = {
        ResourceTypes.MDB: lambda fp: Mdb.from_file(fp),
        ResourceTypes.MBA: lambda fp: Mdb.from_file(fp)
    }

    class Resource:
        def __init__(self, name, path, type: ResourceType, object):
            self.name = name
            self.path = path
            self.type = type
            self.resource = object

        def get(self):
            return self.resource

    def __init__(self, root_content_dir):
        self.content_root = root_content_dir
        self.errors = {}

    def locate(self, resource_name=None, resource_type: ResourceType = None):
        if resource_name is None and resource_type is None:
            raise Exception('one of resource_name and resource_type must be present (not none)')

        located_resources = []

        def locate_resources_in_folder(folder_path, res_name, res_type, out_located_resources):
            if not os.path.isdir(folder_path):
                return

            if res_name is None:  # all resources of the type
                out_located_resources.extend(
                    [os.path.join(folder_path, f) for f in os.listdir(folder_path)
                     if res_type.validate(os.path.join(folder_path, f))]
                )

            elif res_type is None:  # resources of all types with the name
                out_located_resources.extend(
                    [os.path.join(folder_path, f) for f in os.listdir(folder_path)
                     if f[:f.find('.')] == res_name]
                )

            else:  # for type and name
                if os.path.exists(os.path.join(folder_path, res_name + res_type.extension)) and \
                        res_type.validate(os.path.join(folder_path, res_name + res_type.extension)):
                    out_located_resources.append(os.path.join(folder_path, res_name + res_type.extension))

            for subfolder in [f for f in os.listdir(folder_path) if not '.' in f]:
                locate_resources_in_folder(os.path.join(folder_path, subfolder), res_name, res_type, out_located_resources)

        locate_resources_in_folder(self.content_root, resource_name, resource_type, located_resources)
        return located_resources

    def load(self, resource_name, resource_type):
        fp = self.locate(resource_name, resource_type)
        if len(fp) == 0:
            raise Exception('no resource with this name ({}) and type ({}) found'.format(resource_name, resource_type))
        elif len(fp) > 1:
            raise Exception('multiple resources with this name and type found')
        else:
            return self.RESOURCE_LOADERS[resource_type](fp[0])

    def new_session(self):
        self.errors = {}


RESOURCE_LOADER = ResourceLoader(CONTENT_DIR)


@exposed('get resource loader')
def resources():
    return RESOURCE_LOADER


@exposed('print list members one by one')
def enlist(lst: list):
    for lst_el in lst:
        print(lst_el)


@exposed('create parsed mdb (binary model) file from file name')
def mdb(fname):
    RESOURCE_LOADER.new_session()
    return RESOURCE_LOADER.load(fname, ResourceLoader.ResourceTypes.MDB)


@exposed('create parsed mba (binary animation) file from file name')
def mba(fname):
    RESOURCE_LOADER.new_session()
    return RESOURCE_LOADER.load(fname, ResourceLoader.ResourceTypes.MBA)


# tries to resolve anything to mdb, if it's not already
def ensure_mdb(thing):
    if isinstance(thing, Mdb):
        return thing
    elif isinstance(thing, str):
        return mdb(thing)


# this function removes the 'pointer' nature of an object, if object is a pointer
def p(thing):
    is_pointer = getattr(thing, 'archtype', 'none') == 'pointer'
    list_like = isinstance(thing, Iterable)

    if list_like:
        return [p(x) for x in thing]
    if is_pointer:
        return p(thing.data)
    else:
        return thing


@exposed('get nodes of an mdb')
def nodes(mdb: Mdb, filter=None):
    mdb = ensure_mdb(mdb)

    def _apply_filter(node):
        if filter is not None:
            return filter(node)
        else:
            return True

    def recursive_get_nodes(node: Mdb.Node, out_nodes: list):
        for node_ in p(node.children):
            if _apply_filter(node_):
                out_nodes.append(node_)
            recursive_get_nodes(node_, out_nodes)

    nodes = []
    recursive_get_nodes(mdb.root_node, nodes)
    return nodes


@exposed('list nodes and count of each node of an mdb')
def which_node_types(model):
    nds = [str(nd.node_type) for nd in nodes(model)]
    return {node_type: len(instances) for node_type, instances in
            {node_type: [node_type_ for node_type_ in nds if node_type_ == node_type] for node_type in
             set(nds)}.items()}


@exposed('get all mdb files available')
def meshes():
    return [name_ for name_ in os.listdir(MESH_DIR) if name_.endswith('.mdb')]


@exposed('get all nodes as node tree (dict)')
def node_tree(model, describe=None):
    model = ensure_mdb(model)

    if describe is None:
        describe = lambda nd: (nd.node_name, nd.node_type.name)

    def recursive_get_nodes(root: Mdb.Node, out: list):
        for nd in p(root.children):
            if len(nd.children.data) > 0:
                describe_nd = describe(nd)
                d = {describe_nd: []}
                out.append(d)
                recursive_get_nodes(nd, d[describe_nd])
            else:
                out.append(describe(nd))

    nodes = {describe(model.root_node): []}
    recursive_get_nodes(model.root_node, nodes[describe(model.root_node)])
    return nodes


@exposed('pretty print')
def pretty_print(thing):
    if isinstance(thing, dict):
        def recursive_dict_print(dct: dict, indent, level):
            for key in dct.keys():
                print(indent * level + str(key))
                for lst_member in dct[key]:
                    if isinstance(lst_member, dict):
                        recursive_dict_print(lst_member, indent, level + 1)
                    else:
                        print(indent * (level + 1) + str(lst_member))

        recursive_dict_print(thing, ' -- ', 0)


#  DRAWING -----------------------
def show_verts(verts, spec='yz', colorize='by_type'):
    figure, axis = plt.subplots()
    plt.axis('off')
    plt.style.use('dark_background')
    axis.set_aspect('equal')

    x = verts[spec[0]]
    y = verts[spec[1]]

    axis.scatter(x, y, s=0.3)


def get_mesh_verts(nodes, out_verts):
    for nd in nodes:
        verts_ = []
        nd_type = ''

        if nd.node_type == Mdb.NodeType.trimesh:
            verts_ = nd.node_data.mesh_data.vertices.data
            nd_type = 'trimesh'
        elif nd.node_type == Mdb.NodeType.skin:
            verts_ = nd.node_data.vertices.data
            nd_type = 'skin'

        out_verts['x'].extend([v.x for v in verts_])
        out_verts['y'].extend([v.y for v in verts_])
        out_verts['z'].extend([v.z for v in verts_])
        out_verts['host'].extend([nd.node_name] * len(verts_))
        out_verts['type'].extend([nd_type] * len(verts_))


@exposed("draw supplied nodes")
def drawn(nodes, spec='yz'):
    vertices = {'x': [], 'y': [], 'z': [], 'host': [], 'type': []}
    get_mesh_verts(nodes, vertices)
    show_verts(vertices, spec)


@exposed("draw supplied mdb model")
def draw(mdb, spec='yz', filters=None):
    nds = nodes(mdb, filters)
    drawn(nds, spec)


# ----------------------- DRAWING


def help():
    which_functions()


# create a renderable mesh from mesh_data
def rmesh(mesh_data: Mdb.MeshData):
    class Mesh:

        def __init__(self):
            # vertices follow each other in a long array
            # each three consecutive vertices represent
            # a new face
            self.vertices = []
            self.material = None

    mesh = Mesh()
    mesh.vertices = []
    mesh.material = Material(name="default",
                             diffuse=[0.6, 0.6, 0.6],
                             ambient=[1.0, 1.0, 1.0],
                             specular=[0.5, 0.5, 0.5],
                             emission=[0.0, 0.0, 0.0],
                             shininess=100.0)

    for fce in mesh_data.faces.face:
        for vert_index in [fce.c1, fce.c2, fce.c3]:
            mesh.vertices.extend([
                mesh_data.vertices.vert[vert_index].x,
                mesh_data.vertices.vert[vert_index].y,
                mesh_data.vertices.vert[vert_index].z
            ])
    return mesh


def which_functions():
    for func, descr in EXPOSED_FUNCTIONS:
        print(func.__name__ + ' (' + descr + ')')
