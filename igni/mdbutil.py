from .mdb import Mdb
from collections.abc import Iterable
from typing import List

'''
defines a wrapper for kaitai auto-generated Mdb class and some utility functions
'''


class AnimationCurve:

    def __init__(self, controller_def: Mdb.ControllerDef, controller_data):
        self.data = {}

        times_start = controller_def.times_start
        values_start = controller_def.values_start
        key_count = controller_def.key_count
        chnl_count = controller_def.channel_count

        times = controller_data[times_start:(times_start + key_count)]

        values = controller_data[values_start:(values_start + key_count * chnl_count)]
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

        self.vertices = tuple((v.x, v.y, v.z) for v in self.trimesh.vertices.data)
        self.faces = tuple((f.vert1, f.vert2, f.vert3) for f in self.trimesh.faces.data)
        self.normals = tuple((n.x, n.y, n.z) for n in self.trimesh.normals.data)
        self.binormals = tuple((b.x, b.y, b.z) for b in self.trimesh.binormals.data)
        self.tangents = tuple((t.x, t.y, t.z) for t in self.trimesh.tangents.data)

        for i in range(0, 4):
            uv_array_pointer = self.trimesh.uvs[i]
            if uv_array_pointer.data is not None and len(uv_array_pointer.data) > 0:
                self.uv_sets['UvSet{}'.format(i)] = ((c.u, c.v) for c in uv_array_pointer.data)


class NodeProperty:

    @staticmethod
    def _is_empty_(data):
        return data is None or len(data) == 0

    @staticmethod
    def _is_formatted_as_animation_(data):
        for time_val in data:
            if isinstance(time_val, tuple) and len(time_val) == 2:
                return True

    def __init__(self, property_type, data):
        self.type = property_type

        if self._is_empty_(data):
            self.value = None
            self.frames = None
        elif self._is_formatted_as_animation_(data):
            self.frames = data
            self.value = self.frames[0][1]
        else:
            self.value = data
            self.frames = tuple(0.0, data)

    def empty(self):
        return self._is_empty_(self.value)

    def is_animated(self):
        return self.key_count() > 1

    def key_count(self):
        if not self.empty():
            return len(self.frames)
        else:
            return 0


class NodeProperties:

    ePropertyTypeLocation = 'location'
    ePropertyTypeRotation = 'rotation'
    ePropertyTypeAlpha = 'alpha'
    ePropertyTypeScale = 'scale'
    ePropertyTypeSelfIllum = 'self_illum'

    @classmethod
    def from_node(cls, node: Mdb.Node):
        return cls(node.controller_defs.data, node.controller_data.data)

    def __init__(self, controller_defs, controller_data):

        # location, rotation, etc. are either a dict (representing animation) or a single value (no animation, static)
        self.location: NodeProperty = None
        self.rotation: NodeProperty = None
        self.scale: NodeProperty = None
        self.self_illum: NodeProperty = None
        self.alpha: NodeProperty = None

        self._mdb_controller_type_map = {
            'position': self.ePropertyTypeLocation,
            'orientation': self.ePropertyTypeRotation,
            'alpha': self.ePropertyTypeAlpha,
            'scale': self.ePropertyTypeScale,
            'self_illum': self.ePropertyTypeSelfIllum
        }

        self._init_data_(controller_defs, controller_data)

    def _is_unknown_controller_type_(self, controller_def):
        if not isinstance(controller_def.controller_type, Mdb.ControllerType) or \
                controller_def.controller_type.name not in self._mdb_controller_type_map:
            return True
        return False

    @classmethod
    def _get_property_data_(cls,
                            shared_array,
                            times_start,
                            values_start,
                            channel_count,
                            key_count):
        times = shared_array[times_start:(times_start + key_count)]
        values = shared_array[values_start:(values_start + channel_count * key_count)]

        if len(times) == 0 or len(values) == 0 or len(times) != len(values) / channel_count:
            raise Exception('property data seems to have inconsistent number of keys or values')

        values = [tuple(values[i:(i + channel_count)]) for i
                  in range(0, len(values), channel_count)]
        return [tuple([time, value]) for time, value in zip(times, values)]

    def _init_data_(self, controller_defs, controller_data):
        for controller_def in controller_defs:
            if self._is_unknown_controller_type_(controller_def):
                continue  # log

            property_type = self._mdb_controller_type_map[controller_def.controller_type.name.lower()]
            self.__setattr__(
                property_type,
                NodeProperty(property_type, self._get_property_data_(controller_data,
                                                                     controller_def.times_start,
                                                                     controller_def.values_start,
                                                                     controller_def.channel_count,
                                                                     controller_def.key_count))
            )


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

    def is_empty(self):
        return len(self.shader) == 0 and len(self.textures) == 0 and len(self.bumpmaps) == 0

    def __str__(self):
        data = {'shader': self.shader,
                'textures': self.textures,
                'bumpmaps': self.bumpmaps,
                'properties': self.properties}
        return str(data)

    def get_all_textures(self):
        textures = {key: val for key, val in self.textures.items()}
        textures.update(self.bumpmaps)
        return textures

    def as_dict(self):
        textures = {key: val for key, val in self.textures.items()}
        textures.update(self.bumpmaps)
        return {
            'shader': self.shader,
            'textures': textures,
            'parameters': self.properties
        }

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
            print(indent_string * depth + this)
            recursive_print(node.children.data, indent_string, depth + 1, print_this)

    print(print_this(node))
    recursive_print(node.children.data, '-- ', 1, print_this)


class MdbWrapper:

    @staticmethod
    def get_all_nodes(mdb: Mdb) -> List[Mdb.Node]:
        flat_nodes = []

        def recursive_append_node_and_children(node: Mdb.Node):
            flat_nodes.append(node)
            for child in node.children.data:
                recursive_append_node_and_children(child.data)

        recursive_append_node_and_children(mdb.root_node)

        return flat_nodes

    @staticmethod
    def get_all_materials(mdb: Mdb) -> Material:
        nodes = get_all_nodes(mdb)

        materials = []

        for node in nodes:
            material = Material(node.node_data.material.data, node)
            if not material.is_empty():
                materials.append(material)

        return materials

    @staticmethod
    def get_all_bones(mdb: Mdb) -> List[Mdb.Node]:

        bones: List[Mdb.Node] = []
        nodes = get_all_nodes(mdb)

        skins = [node for node in get_all_nodes(mdb) if node.node_type == Mdb.NodeType.skin]
        for skin in skins:
            for bone in skin.node_data.bones.data:
                if bone.bone_name.string not in [node.node_name.string for node in bones]:
                    nodes_matched_by_bone_name = [node for node in nodes if
                                                  node.node_name.string == bone.bone_name.string]
                    if len(nodes_matched_by_bone_name) != 1:
                        raise Exception('found zero or >1 nodes matching the bone name')
                    bones.append(nodes_matched_by_bone_name[0])

        return bones

    @staticmethod
    def get_all_animated_nodes(mdb: Mdb) -> List[Mdb.Node]:

        def get_animation_nodes(animation: Mdb.Animation) -> List[Mdb.AnimationNode]:

            animation_nodes: List[Mdb.AnimationNode] = []

            def add_animation_nodes_recursive(anim_node: Mdb.AnimationNode):
                animation_nodes.append(anim_node)
                for anim_child_node in anim_node.children.data:
                    add_animation_nodes_recursive(anim_child_node.data)

            add_animation_nodes_recursive(animation.root_animation_node.data)

            return animation_nodes

        nodes = get_all_nodes(mdb)
        animations = mdb.animations.animation_array_pointer.data

        animated_nodes: List[Mdb.Node] = []

        for animation in animations:
            animation_nodes = get_animation_nodes(animation.data)
            for animation_node in animation_nodes:
                nodes_matching_by_animated_node_name = [node for node in nodes if
                                                        node.node_name.string == animation_node.name.string]
                if len(nodes_matching_by_animated_node_name) != 1:
                    raise Exception('found 0 or >1 nodes matching animated node by name')
                animated_nodes.append(nodes_matching_by_animated_node_name[0])

        return animated_nodes

    def _init_data(self):
        if self.mdb is None:
            return

        # nodes
        self.nodes = self.get_all_nodes(self.mdb)

        # meshes
        self.meshes = [node for node in self.nodes if node.node_type in {Mdb.NodeType.skin, Mdb.NodeType.trimesh}]

        # materials
        all_materials = [Material(node.node_data.material.data) for node in self.meshes]
        self.materials = [material for material in all_materials if not material.is_empty()]

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


def get_all_nodes(mdb: Mdb) -> List[Mdb.Node]:
    flat_nodes = []

    def recursive_append_node_and_children(node: Mdb.Node):
        flat_nodes.append(node)
        for child in node.children.data:
            recursive_append_node_and_children(child.data)

    recursive_append_node_and_children(mdb.root_node)

    return flat_nodes


def get_all_materials(mdb: Mdb) -> Material:
    nodes = get_all_nodes(mdb)

    materials = []

    for node in nodes:
        material = Material(node.node_data.material.data, node)
        if not material.is_empty():
            materials.append(material)

    return materials


def get_all_bones(mdb: Mdb) -> List[Mdb.Node]:

    bones: List[Mdb.Node] = []
    nodes = get_all_nodes(mdb)

    skins = [node for node in get_all_nodes(mdb) if node.node_type == Mdb.NodeType.skin]
    for skin in skins:
        for bone in skin.node_data.bones.data:
            if bone.bone_name.string not in [node.node_name.string for node in bones]:
                nodes_matched_by_bone_name = [node for node in nodes if node.node_name.string == bone.bone_name.string]
                if len(nodes_matched_by_bone_name) != 1:
                    raise Exception('found zero or >1 nodes matching the bone name')
                bones.append(nodes_matched_by_bone_name[0])

    return bones


def get_all_animated_nodes(mdb: Mdb) -> List[Mdb.Node]:

    def get_animation_nodes(animation: Mdb.Animation) -> List[Mdb.AnimationNode]:

        animation_nodes: List[Mdb.AnimationNode] = []

        def add_animation_nodes_recursive(anim_node: Mdb.AnimationNode):
            animation_nodes.append(anim_node)
            for anim_child_node in anim_node.children.data:
                add_animation_nodes_recursive(anim_child_node.data)

        add_animation_nodes_recursive(animation.root_animation_node.data)

        return animation_nodes

    nodes = get_all_nodes(mdb)
    animations = mdb.animations.animation_array_pointer.data

    animated_nodes: List[Mdb.Node] = []

    for animation in animations:
        animation_nodes = get_animation_nodes(animation.data)
        for animation_node in animation_nodes:
            nodes_matching_by_animated_node_name = [node for node in nodes if node.node_name.string == animation_node.name.string]
            if len(nodes_matching_by_animated_node_name) != 1:
                raise Exception('found 0 or >1 nodes matching animated node by name')
            animated_nodes.append(nodes_matching_by_animated_node_name[0])

    return animated_nodes
