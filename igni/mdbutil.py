from .mdb import Mdb

'''
defines a wrapper for kaitai auto-generated Mdb class
'''


class AnimationCurve:

    def __init__(self, controller_def: Mdb.ControllerDef, controller_data):
        self.data = {}

        times_start = controller_def.times_start
        values_start = controller_def.values_start
        key_count = controller_def.key_count
        chnl_count = controller_def.channel_count

        times = controller_data[times_start:(times_start + key_count)]

        values = controller_data[values_start:(values_start + key_count*chnl_count)]
        values = [values[i:(i + chnl_count)] for i in range(0, key_count)]

        self.data = {times[i]: values[i] for i in range(0, key_count)}


class AnimationNode:

    def __init__(self, name: str, curves: dict = {}, children: list = []):
        self.name = name
        self.animation_curves = curves
        self.children = children


class Animation:

    def __init__(self, name: str):
        self.name = name
        self.anim_nodes = []
        self.root_node = None

        self._length = 0
        self._key_count = 0
        self._node_count = 0


class Skeleton:

    def __init__(self, name: str):
        pass


# a wrapper class for trimesh (triangular mesh) objects
class Trimesh:

    def __init__(self, trimesh: Mdb.Trimesh, host_node: Mdb.Node = None):

        self.vertices = ()
        self.faces = ()
        self.normals = ()
        self.binormals = ()
        self.tangents = ()
        self.uv_sets = {}
        self.trimesh: Mdb.Trimesh = trimesh
        self.host_node = host_node

        self._init_data()

    def _init_data(self):

        self.vertices = ((v.x, v.y, v.z) for v in self.trimesh.vertices.data)
        self.faces = ((f.vert1, f.vert2, f.vert3) for f in self.trimesh.faces.data)
        self.normals = ((n.x, n.y, n.z) for n in self.trimesh.normals.data)
        self.binormals = ((b.x, b.y, b.z) for b in self.trimesh.binormals.data)
        self.tangents = ((t.x, t.y, t.z) for t in self.trimesh.tangents.data)

        for i in range(0, 4):
            uv_array_pointer = self.trimesh.uvs[i]
            if uv_array_pointer.data is not None and len(uv_array_pointer.data) > 0:
                self.uv_sets['UvSet{}'.format(i)] = ((c.u, c.v) for c in uv_array_pointer.data)


# a wrapper class for mdb materials
class Material:

    def __init__(self, material_descr: Mdb.Material, host_node: Mdb.Node = None):
        if material_descr is None:
            raise Exception('tried to create material wrapper but material description is None')

        self.shader = ''
        self.textures = {}
        self.bumpmaps = {}
        self.properties = {}
        self.host_node = host_node

        self.parse_data(material_descr.material_spec)

    def __str__(self):
        data = {'shader': self.shader,
                'textures': self.textures,
                'bumpmaps': self.bumpmaps,
                'properties': self.properties}
        return str(data)

    def parse_data(self, material_spec: list):

        def line_clean_up(line):
            return line.replace('\\r\\n', ' ').lstrip().rstrip()

        for line in material_spec:
            l_ = line_clean_up(line)

            if len(l_) == 0:
                continue

            parts = l_.split(' ')
            descriptor = parts[0]

            if descriptor == 'shader':
                if len(parts) != 2:
                    raise Exception('unexpected shader specification: {}'.format(l_))
                else:
                    self.shader = parts[1]

            elif descriptor == 'texture':
                if len(parts) != 3:
                    raise Exception('unexpected texture specification: {}'.format(l_))
                else:
                    if parts[1] in self.textures:
                        raise Exception('duplicated texture found: {}'.format(l_))
                    self.textures[parts[1]] = parts[2]

            elif descriptor == 'bumpmap':
                if len(parts) != 3:
                    raise Exception('unexpected bumpmap specification: {}'.format(l_))
                else:
                    if parts[1] in self.bumpmaps:
                        raise Exception('duplicated bumpmap found: {}'.format(l_))
                    self.bumpmaps[parts[1]] = parts[2]

            elif descriptor == 'float' or descriptor == 'string':
                if len(parts) != 3:
                    raise Exception('unexpected property specification: {}'.format(l_))
                else:
                    self.properties[parts[1]] = parts[2]

            elif descriptor == 'vector':
                if len(parts) != 6:
                    raise Exception('unexpected vector property specification: {}'.format(l_))
                else:
                    self.properties[parts[1]] = (parts[2], parts[3], parts[4], parts[5])

            else:
                raise Exception('unexpected material line: {}'.format(l_))


def print_node_tree(node, print_this=lambda nd: nd.node_name.string):

    def recursive_print(nodes, indent_string, depth, print_this):
        if len(nodes) == 0:
            return
        for node in [node_ptr.data for node_ptr in nodes]:
            this = print_this(node)
            print(indent_string*depth + this)
            recursive_print(node.children.data, indent_string, depth + 1, print_this)

    print(print_this(node))
    recursive_print(node.children.data, '-- ', 1, print_this)


class MdbWrapper:

    def _init_data(self):
        if self.mdb is None:
            return

        # nodes
        def recursive_node_scan(node: Mdb.Node, mdb_wrapper):

            self.nodes.append(node)

            if node.node_type == Mdb.NodeType.trimesh and isinstance(node.node_data, Mdb.Trimesh):
                # geometry
                mdb_wrapper.meshes.append(Trimesh(node.node_data, node))

                # materials
                if node.node_data.material.data is not None:
                    self.materials.append(Material(node.node_data.material.data))

            for child_node_pointer in node.children.data:
                recursive_node_scan(child_node_pointer.data, mdb_wrapper)

        self.nodes.append(self.mdb.root_node)
        recursive_node_scan(self.mdb.root_node, self)

        # animations

    def get_node_by(self, eval_expr):
        for node in self.nodes:
            if eval_expr(node):
                return node

    def get_node_by_name(self, name: str):
        return self.get_node_by(lambda nd: nd.node_name.string == name)

    def __init__(self, mdb: Mdb):
        self.mdb = mdb
        self.nodes = []
        self.meshes = []
        self.materials = []
        self.animations = []

        self._init_data()
