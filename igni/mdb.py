# This is a generated file! Please edit source .ksy file and use kaitai-struct-compiler to rebuild

import kaitaistruct
from kaitaistruct import KaitaiStruct, KaitaiStream, BytesIO
from enum import Enum


if getattr(kaitaistruct, 'API_VERSION', (0, 9)) < (0, 9):
    raise Exception("Incompatible Kaitai Struct Python API: 0.9 or later is required, but you have %s" % (kaitaistruct.__version__))

class Mdb(KaitaiStruct):

    class ControllerType(Enum):
        position = 84
        orientation = 96
        scale = 184
        self_illum = 276
        alpha = 292

    class NodeType(Enum):
        node = 1
        light = 3
        emitter = 5
        camera = 9
        reference = 17
        trimesh = 33
        skin = 97
        aabb = 545
        trigger = 1057
        sector_info = 4097
        walk_mesh = 8193
        dangly_node = 16385
        texture_paint = 32769
        speed_tree = 65537
        chain = 131073
        cloth = 262145
    def __init__(self, _io, _parent=None, _root=None):
        self._io = _io
        self._parent = _parent
        self._root = _root if _root else self
        self._read()

    def _read(self):
        self.header = Mdb.Header(self._io, self, self._root)
        self.root_node = Mdb.Node(self._io, self, self._root)

    class Uv(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.u = self._io.read_f4le()
            self.v = self._io.read_f4le()


    class Vertex(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.x = self._io.read_f4le()
            self.y = self._io.read_f4le()
            self.z = self._io.read_f4le()


    class PtrArrayPtr(KaitaiStruct):
        def __init__(self, dtype, additional_array_offset, additional_ptr_offset, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self.dtype = dtype
            self.additional_array_offset = additional_array_offset
            self.additional_ptr_offset = additional_ptr_offset
            self._read()

        def _read(self):
            self.first_element_offset = self._io.read_u4le()
            self.size = self._io.read_u4le()
            self.allocated_size = self._io.read_u4le()

        @property
        def data(self):
            if hasattr(self, '_m_data'):
                return self._m_data

            _pos = self._io.pos()
            self._io.seek((self.first_element_offset + self.additional_array_offset))
            self._m_data = []
            for i in range(self.size):
                self._m_data.append(Mdb.Ptr(self.dtype, self.additional_ptr_offset, self._io, self, self._root))

            self._io.seek(_pos)
            return getattr(self, '_m_data', None)

        @property
        def archtype(self):
            if hasattr(self, '_m_archtype'):
                return self._m_archtype

            self._m_archtype = u"pointer"
            return getattr(self, '_m_archtype', None)


    class ControllerDef(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.controller_type = KaitaiStream.resolve_enum(Mdb.ControllerType, self._io.read_u4le())
            self.key_count = self._io.read_u2le()
            self.times_start = self._io.read_u2le()
            self.values_start = self._io.read_u2le()
            self.channel_count = self._io.read_u1()
            self.pad = self._io.read_u1()


    class Normal(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.x = self._io.read_s2le()
            self.y = self._io.read_s2le()
            self.z = self._io.read_s2le()


    class UnknownType(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.none = self._io.read_bytes(0)


    class Bone(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.bone_id = self._io.read_u4le()
            self.bone_name = Mdb.Strl(92, self._io, self, self._root)


    class Face(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.a1 = self._io.read_u4le()
            self.a2 = self._io.read_u4le()
            self.a3 = self._io.read_u4le()
            self.a4 = self._io.read_u4le()
            self.a5 = self._io.read_u4le()
            self.c1 = self._io.read_u4le()
            self.c2 = self._io.read_u4le()
            self.c3 = self._io.read_u4le()


    class NodeDataTrimesh(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.function_pointer = self._io.read_bytes(8)
            self.offset_mesh_data = self._io.read_u4le()
            self.unknown_0 = self._io.read_bytes(4)
            self.bbox = self._io.read_bytes(24)
            self.unknown_1 = self._io.read_bytes(28)
            self.fog_scale = self._io.read_bytes(4)
            self.unknown_2 = self._io.read_bytes(16)
            self.diffuse_amb_spec_color = self._io.read_bytes(36)
            self.render_settings_0 = self._io.read_bytes(16)
            self.transparency_hint = self._io.read_u4le()
            self.unknown_3 = self._io.read_bytes(4)
            self.textures = []
            for i in range(4):
                self.textures.append(Mdb.Strl(64, self._io, self, self._root))

            self.render_settings_1 = self._io.read_bytes(7)
            self.unknown_4 = self._io.read_bytes(1)
            self.transparency_shift = self._io.read_f4le()
            self.render_settings_2 = self._io.read_bytes(12)
            self.unknown_5 = self._io.read_bytes(4)
            self.render_settings_3 = self._io.read_bytes(13)
            self.unknown_6 = self._io.read_bytes(20)
            self.day_night_transition = Mdb.Strl(200, self._io, self, self._root)
            self.unknown_7 = self._io.read_bytes(23)
            self.light_map_name = Mdb.Strl(64, self._io, self, self._root)
            self.unknown_8 = self._io.read_bytes(8)
            self.material = Mdb.Ptr(u"material", (self._root.header.offset_tex_data_dummy + 32), self._io, self, self._root)

        @property
        def mesh_data(self):
            if hasattr(self, '_m_mesh_data'):
                return self._m_mesh_data

            _pos = self._io.pos()
            self._io.seek((self.offset_mesh_data + 32))
            self._m_mesh_data = Mdb.MeshData(self._io, self, self._root)
            self._io.seek(_pos)
            return getattr(self, '_m_mesh_data', None)

        @property
        def face_count(self):
            if hasattr(self, '_m_face_count'):
                return self._m_face_count

            self._m_face_count = self.mesh_data.faces_array_pointer.size
            return getattr(self, '_m_face_count', None)


    class Animation(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.unknown = self._io.read_bytes(8)
            self.animation_name = Mdb.Strl(64, self._io, self, self._root)
            self.root_animation_node = Mdb.Ptr(u"animation_node", 32, self._io, self, self._root)
            self.unknown2 = self._io.read_bytes(32)
            self.geometry_type = self._io.read_u1()
            self.unknown3 = self._io.read_bytes(3)
            self.animation_length = self._io.read_f4le()
            self.transition_time = self._io.read_f4le()
            self.animation_root_name = Mdb.Strl(64, self._io, self, self._root)
            self.animation_events = Mdb.ArrayPtr(u"unknown", 32, self._io, self, self._root)
            self.anim_box = self._io.read_bytes(24)
            self.anim_sphere = self._io.read_bytes(16)
            self.unknown4 = self._io.read_bytes(4)


    class Strl(KaitaiStruct):
        def __init__(self, length, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self.length = length
            self._read()

        def _read(self):
            self.string = (KaitaiStream.bytes_terminate(self._io.read_bytes(self.length), 0, False)).decode(u"utf8")


    class NodeDataSkin(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.function_pointer = self._io.read_bytes(8)
            self.offset_mesh_data = self._io.read_u4le()
            self.unknown_0 = self._io.read_bytes(4)
            self.bbox = self._io.read_bytes(24)
            self.unknown_1 = self._io.read_bytes(28)
            self.fog_scale = self._io.read_bytes(4)
            self.unknown_2 = self._io.read_bytes(16)
            self.diffuse_amb_spec_color = self._io.read_bytes(36)
            self.render_settings_0 = self._io.read_bytes(16)
            self.transparency_hint = self._io.read_u4le()
            self.unknown_3 = self._io.read_bytes(4)
            self.texture_strings = []
            for i in range(4):
                self.texture_strings.append(Mdb.Strl(64, self._io, self, self._root))

            self.render_settings_1 = self._io.read_bytes(7)
            self.unknown_4 = self._io.read_bytes(1)
            self.transparency_shift = self._io.read_f4le()
            self.render_settings_2 = self._io.read_bytes(12)
            self.unknown_5 = self._io.read_bytes(4)
            self.render_settings_3 = self._io.read_bytes(13)
            self.unknown_6 = self._io.read_bytes(20)
            self.day_night_transition_string = Mdb.Strl(200, self._io, self, self._root)
            self.unknown_7 = self._io.read_bytes(23)
            self.light_map_name = Mdb.Strl(64, self._io, self, self._root)
            self.unknwon_8 = self._io.read_bytes(8)
            self.material = Mdb.Ptr(u"material", (self._root.header.offset_tex_data_dummy + 32), self._io, self, self._root)
            self.unknown_9 = self._io.read_bytes(4)
            self.bones = Mdb.ArrayPtr(u"bone", (self._root.header.offset_tex_data_dummy + 32), self._io, self, self._root)
            self.unknown_11 = self._io.read_bytes(4)
            self.vertices = Mdb.ArrayPtr(u"vertex", 32, self._io, self, self._root)
            self.normals = Mdb.ArrayPtr(u"normal", 32, self._io, self, self._root)
            self.tangents = Mdb.ArrayPtr(u"tangent", 32, self._io, self, self._root)
            self.binormals = Mdb.ArrayPtr(u"binormals", 32, self._io, self, self._root)
            self.uvs = []
            for i in range(4):
                self.uvs.append(Mdb.ArrayPtr(u"uv", 32, self._io, self, self._root))

            self.unknown_array = Mdb.ArrayPtr(u"unknown", 32, self._io, self, self._root)
            self.faces = Mdb.ArrayPtr(u"face", 32, self._io, self, self._root)
            self.unknown_10 = self._io.read_bytes(36)
            self.weights = Mdb.ArrayPtr(u"f4", 32, self._io, self, self._root)
            self.bones_something_ptr = Mdb.ArrayPtr(u"unknown", 32, self._io, self, self._root)


    class AnimationNode(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.function_pointers = self._io.read_bytes(24)
            self.inherit_color_flag = self._io.read_bytes(4)
            self.node_id = self._io.read_u4le()
            self.name = Mdb.Strl(64, self._io, self, self._root)
            self.parent_geom_parent_node = self._io.read_bytes(8)
            self.children = Mdb.PtrArrayPtr(u"animation_node", 32, 32, self._io, self, self._root)
            self.controller_defs = Mdb.ArrayPtr(u"controller_def", 32, self._io, self, self._root)
            self.controller_data = Mdb.ArrayPtr(u"f4", 32, self._io, self, self._root)
            self.node_flags_type = self._io.read_bytes(4)
            self.fixed_rot_imposter_group = self._io.read_bytes(8)
            self.min_max_lod = self._io.read_bytes(8)
            self.node_type = KaitaiStream.resolve_enum(Mdb.NodeType, self._io.read_u4le())


    class Animations(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.unknown = self._io.read_bytes(4)
            self.animation_array_pointer = Mdb.PtrArrayPtr(u"animation", (self._root.header.offset_tex_data_dummy + 32), 32, self._io, self, self._root)


    class Header(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.binary_file_signature = self._io.read_bytes(4)
            if not self.binary_file_signature == b"\x00\x00\x00\x00":
                raise kaitaistruct.ValidationNotEqualError(b"\x00\x00\x00\x00", self.binary_file_signature, self._io, u"/types/header/seq/0")
            self.file_version = self._io.read_u1()
            self.unknown_1 = self._io.read_bytes(3)
            self.model_count = self._io.read_u4le()
            self.unknown_2 = self._io.read_bytes(4)
            self.size_model_data = self._io.read_u4le()
            self.unknown_3 = self._io.read_bytes(4)
            self.offset_tex_data_dummy = self._io.read_u4le()
            self.size_tex_data = self._io.read_u4le()
            self.unknown_4 = self._io.read_bytes(8)
            self.model_name = (KaitaiStream.bytes_terminate(self._io.read_bytes(64), 0, False)).decode(u"utf8")
            self.offset_root_node = self._io.read_u4le()
            self.unknown_5 = self._io.read_bytes(32)
            self.some_type = self._io.read_u1()
            self.unknown_6 = self._io.read_bytes(51)
            self.first_lod = self._io.read_f4le()
            self.last_lod = self._io.read_f4le()
            self.unknown_7 = self._io.read_bytes(16)
            self.detail_map = (KaitaiStream.bytes_terminate(self._io.read_bytes(64), 0, False)).decode(u"utf8")
            self.unknown_8 = self._io.read_bytes(4)
            self.model_scale = self._io.read_f4le()
            self.super_model = (KaitaiStream.bytes_terminate(self._io.read_bytes(60), 0, False)).decode(u"utf8")
            self.animation_scale = self._io.read_f4le()
            self.unknown_9 = []
            for i in range(((self.offset_root_node + 32) - 352)):
                self.unknown_9.append(self._io.read_bytes(1))



    class Material(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.texture_count = self._io.read_u4le()
            self.texture_offset = self._io.read_u4le()
            self.material_string = []
            for i in range(self.texture_count):
                self.material_string.append((self._io.read_bytes_term(0, False, True, True)).decode(u"utf8"))



    class Node(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.function_pointers = self._io.read_bytes(24)
            self.inherit_color_flag = self._io.read_bytes(4)
            self.node_id = self._io.read_u4le()
            self.node_name = (KaitaiStream.bytes_terminate(self._io.read_bytes(64), 0, False)).decode(u"utf8")
            self.parent_geometry_parent_node = self._io.read_bytes(8)
            self.children = Mdb.PtrArrayPtr(u"node", 32, 32, self._io, self, self._root)
            self.controller_defs = Mdb.ArrayPtr(u"controller_def", 32, self._io, self, self._root)
            self.controller_data = Mdb.ArrayPtr(u"f4", 32, self._io, self, self._root)
            self.flags_type = self._io.read_bytes(4)
            self.fixed_rot_impostor_group = self._io.read_bytes(8)
            self.min_lod = self._io.read_s4le()
            self.max_lod = self._io.read_s4le()
            self.node_type = KaitaiStream.resolve_enum(Mdb.NodeType, self._io.read_u4le())
            _on = self.node_type
            if _on == Mdb.NodeType.trimesh:
                self.node_data = Mdb.NodeDataTrimesh(self._io, self, self._root)
            elif _on == Mdb.NodeType.skin:
                self.node_data = Mdb.NodeDataSkin(self._io, self, self._root)


    class Ptr(KaitaiStruct):
        def __init__(self, dtype, additional_offset, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self.dtype = dtype
            self.additional_offset = additional_offset
            self._read()

        def _read(self):
            self.offset = self._io.read_u4le()

        @property
        def data(self):
            if hasattr(self, '_m_data'):
                return self._m_data

            _pos = self._io.pos()
            self._io.seek((self.offset + self.additional_offset))
            _on = self.dtype
            if _on == u"animation":
                self._m_data = Mdb.Animation(self._io, self, self._root)
            elif _on == u"node":
                self._m_data = Mdb.Node(self._io, self, self._root)
            elif _on == u"animation_node":
                self._m_data = Mdb.AnimationNode(self._io, self, self._root)
            elif _on == u"material":
                self._m_data = Mdb.Material(self._io, self, self._root)
            else:
                self._m_data = Mdb.UnknownType(self._io, self, self._root)
            self._io.seek(_pos)
            return getattr(self, '_m_data', None)

        @property
        def archtype(self):
            if hasattr(self, '_m_archtype'):
                return self._m_archtype

            self._m_archtype = u"pointer"
            return getattr(self, '_m_archtype', None)


    class MeshData(KaitaiStruct):
        def __init__(self, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self._read()

        def _read(self):
            self.unknown_0 = self._io.read_bytes(4)
            self.vertices = Mdb.ArrayPtr(u"vertex", 32, self._io, self, self._root)
            self.normals_array_pointer = Mdb.ArrayPtr(u"normal", 32, self._io, self, self._root)
            self.tangents_array_pointer = Mdb.ArrayPtr(u"tangent", 32, self._io, self, self._root)
            self.binormals_array_pointer = Mdb.ArrayPtr(u"normal", 32, self._io, self, self._root)
            self.texture_vertex_array_pointers = []
            for i in range(4):
                self.texture_vertex_array_pointers.append(Mdb.ArrayPtr(u"uv", 32, self._io, self, self._root))

            self.unknown_data_array_pointer = Mdb.ArrayPtr(u"unknown", 32, self._io, self, self._root)
            self.faces_array_pointer = Mdb.ArrayPtr(u"face", 32, self._io, self, self._root)
            if self._root.header.file_version == 133:
                self.offset_tex_data = self._io.read_u4le()



    class ArrayPtr(KaitaiStruct):
        def __init__(self, dtype, additional_offset, _io, _parent=None, _root=None):
            self._io = _io
            self._parent = _parent
            self._root = _root if _root else self
            self.dtype = dtype
            self.additional_offset = additional_offset
            self._read()

        def _read(self):
            self.first_element_offset = self._io.read_u4le()
            self.size = self._io.read_u4le()
            self.allocated_size = self._io.read_u4le()

        @property
        def data(self):
            if hasattr(self, '_m_data'):
                return self._m_data

            _pos = self._io.pos()
            self._io.seek((self.first_element_offset + self.additional_offset))
            self._m_data = []
            for i in range(self.size):
                _on = self.dtype
                if _on == u"controller_def":
                    self._m_data.append(Mdb.ControllerDef(self._io, self, self._root))
                elif _on == u"animation_node":
                    self._m_data.append(Mdb.AnimationNode(self._io, self, self._root))
                elif _on == u"normal":
                    self._m_data.append(Mdb.Normal(self._io, self, self._root))
                elif _on == u"f4":
                    self._m_data.append(self._io.read_f4le())
                elif _on == u"vertex":
                    self._m_data.append(Mdb.Vertex(self._io, self, self._root))
                elif _on == u"bone":
                    self._m_data.append(Mdb.Bone(self._io, self, self._root))
                elif _on == u"uv":
                    self._m_data.append(Mdb.Uv(self._io, self, self._root))
                elif _on == u"face":
                    self._m_data.append(Mdb.Face(self._io, self, self._root))
                else:
                    self._m_data.append(Mdb.UnknownType(self._io, self, self._root))

            self._io.seek(_pos)
            return getattr(self, '_m_data', None)

        @property
        def data_type(self):
            if hasattr(self, '_m_data_type'):
                return self._m_data_type

            self._m_data_type = self.dtype
            return getattr(self, '_m_data_type', None)

        @property
        def archtype(self):
            if hasattr(self, '_m_archtype'):
                return self._m_archtype

            self._m_archtype = u"pointer"
            return getattr(self, '_m_archtype', None)


    @property
    def animations(self):
        if hasattr(self, '_m_animations'):
            return self._m_animations

        _pos = self._io.pos()
        self._io.seek((self.header.offset_tex_data_dummy + 32))
        self._m_animations = Mdb.Animations(self._io, self, self._root)
        self._io.seek(_pos)
        return getattr(self, '_m_animations', None)


