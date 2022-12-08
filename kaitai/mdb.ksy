meta:
  id: mdb
  file-extension: mdb
  endian: le
  bit-endian: le
seq:
  - id: header
    type: header
instances:
  root_node:
    pos: header.offset_root_node + 32
    type: node
  animations:
    pos: header.offset_tex_data_dummy + 32
    type: animations
types:
  unknown_type:
    seq:
      - id: none 
        size: 0
  # pointer types
  ptr:
    params:
      - id: dtype
        type: str
      - id: additional_offset
        type: u4
    seq:
      - id: offset
        type: u4
    instances:
      data:
        pos: offset + additional_offset
        type:
          switch-on: dtype
          cases:
            '"material"': material
            '"node"': node
            '"animation"': animation
            '"animation_node"': animation_node
            _: unknown_type
      archtype:
        value: '"pointer"'
  array_ptr:
    params:
      - id: dtype
        type: str
      - id: additional_offset
        type: u4
    seq:
      - id: first_element_offset
        type: u4
      - id: size
        type: u4
      - id: allocated_size
        type: u4
    instances:
      data:
        pos: first_element_offset + additional_offset
        type:
          switch-on: dtype
          cases:
            '"vertex"': vertex
            '"normal"': normal
            '"vector3ofs2"': vector3ofs2
            '"face"': face
            '"uv"': uv
            '"f4"': f4
            '"controller_def"': controller_def 
            '"bone"': bone 
            '"animation_node"': animation_node
            _: unknown_type  
        repeat: expr
        repeat-expr: size
      data_type:
        value: dtype
      archtype:
        value: '"pointer"'
  ptr_array_ptr:
    params:
      - id: dtype
        type: str
      - id: additional_array_offset
        type: u4
      - id: additional_ptr_offset
        type: u4
    seq:
      - id: first_element_offset
        type: u4
      - id: size
        type: u4
      - id: allocated_size
        type: u4
    instances:
      data:
        pos: first_element_offset + additional_array_offset
        type: ptr(dtype, additional_ptr_offset)
        repeat: expr
        repeat-expr: size
      archtype:
        value: '"pointer"'
  # object types
  uv: 
    seq:
      - id: u
        type: f4
      - id: v
        type: f4
  vertex: 
    seq:
      - id: x
        type: f4
      - id: y
        type: f4
      - id: z
        type: f4
  vector3ofs2:
    seq:
      - id: x
        type: s2
      - id: y
        type: s2
      - id: z
        type: s2
  normal:
    seq:
      - id: x
        type: s2
      - id: y
        type: s2
      - id: z
        type: s2
  face:
    seq:
      - id: unknown
        type: u4
        repeat: expr
        repeat-expr: 5
      - id: vert1
        type: u4
      - id: vert2
        type: u4
      - id: vert3
        type: u4
  strl:
    params:
      - id: length
        type: u4
    seq:
      - id: string
        type: str
        encoding: utf8
        size: length
        terminator: 0
  material:
    seq:
      - id: material_spec_lines_count
        type: u4
      - id: texture_offset
        type: u4
      - id: material_spec
        type: strz
        encoding: utf8
        repeat: expr
        repeat-expr: material_spec_lines_count
  bone:
    seq:
      - id: bone_id
        type: u4
      - id: bone_name
        type: strl(92)
  header:
    seq:
      - id: binary_file_signature
        contents: [0, 0, 0, 0]
      - id: file_version
        contents: [0x88]
        doc: File version, should be normally 136, 133 seems to be an exceptional or non-existant case.
      - id: unknown_1
        size: 3
      - id: model_count
        type: u4
        doc: The model count attribute seems to be always equal to 1.
      - id: unknown_2
        size: 4
      - id: size_model_data
        type: u4
        doc: TODO Size of the area where node-hierarchical scene data is stored.
      - id: unknown_3
        size: 4
      - id: offset_tex_data_dummy
        type: u4
        doc: Specifies offset (when added 32) where non-scene data like bones, materials, and animations is stored.
      - id: size_tex_data
        type: u4
        doc: Specifies the size of the area where non-scene data like bones, material, and animations is stored.
      - id: unknown_4
        size: 8
      - id: model_name
        type: strl(64)
      - id: offset_root_node
        type: u4
        doc: This offset + 32 gives the offset at which the root node of the binary model is located.
      - id: unknown_5
        size: 32
      - id: some_type
        type: u1
      - id: unknown_6
        size: 51
      - id: first_lod
        type: f4
      - id: last_lod
        type: f4
      - id: unknown_7
        size: 16
      - id: detail_map
        type: strl(64)
      - id: unknown_8
        size: 4
      - id: model_scale
        type: f4
      - id: super_model
        type: strl(60)
      - id: animation_scale
        type: f4
  node:
    seq:
      - id: function_pointers
        size: 24
      - id: inherit_color_flag
        size: 4
      - id: node_id
        type: u4
      - id: node_name
        type: strl(64)
      - id: parent_geometry_parent_node
        size: 8
      - id: children
        type: ptr_array_ptr('node', 32, 32)
      - id: controller_defs
        type: array_ptr('controller_def', 32)
      - id: controller_data
        type: array_ptr('f4', 32)
      - id: flags_type
        size: 4
      - id: fixed_rot_impostor_group
        size: 8
      - id: min_lod
        type: s4
      - id: max_lod
        type: s4
      - id: node_type
        type: u4
        enum: node_type
      - id: node_data
        type:
          switch-on: node_type
          cases:
            'node_type::trimesh': trimesh
            'node_type::skin': trimesh
  controller_def:
    seq:
      - id: controller_type
        type: u4
        enum: controller_type
      - id: key_count
        type: u2
      - id: times_start
        type: u2
      - id: values_start
        type: u2
      - id: channel_count
        type: u1
      - id: pad
        type: u1
  animation_node:
    seq:
      - id: function_pointers
        size: 24
      - id: inherit_color_flag
        size: 4
      - id: node_id
        type: u4
      - id: name
        type: strl(64)
      - id: parent_geom_parent_node
        size: 8
      - id: children
        type: ptr_array_ptr('animation_node', 32, 32)
      - id: controller_defs
        type: array_ptr('controller_def', 32)
      - id: controller_data
        type: array_ptr('f4', 32)
      - id: node_flags_type
        size: 4
      - id: fixed_rot_imposter_group
        size: 8
      - id: min_max_lod
        size: 8
      - id: node_type 
        type: u4
        enum: node_type
  animation:
    seq:
      - id: unknown
        size: 8
      - id: animation_name
        type: strl(64)
      - id: root_animation_node
        type: ptr('animation_node', 32)
      - id: unknown2
        size: 32
      - id: geometry_type
        type: u1
      - id: unknown3
        size: 3
      - id: animation_length
        type: f4
      - id: transition_time
        type: f4
      - id: animation_root_name
        type: strl(64)
      - id: animation_events
        type: array_ptr('unknown', 32)
      - id: anim_box
        size: 24
      - id: anim_sphere
        size: 16
      - id: unknown4
        size: 4
  animations:
    seq:
      - id: unknown
        size: 4
      - id: animation_array_pointer
        type: ptr_array_ptr('animation', _root.header.offset_tex_data_dummy + 32, 32)
  trimesh:
    seq:
      - id: function_pointer
        size: 8
      - id: offset_mesh_data
        type: u4
      - id: unknown_0
        size: 4
      - id: bbox
        size: 24
      - id: unknown_1
        size: 28
      - id: fog_scale
        size: 4
      - id: unknown_2
        size: 16
      - id: diffuse_amb_spec_color
        size: 36
      - id: render_settings_0
        size: 16
      - id: transparency_hint
        type: u4
      - id: unknown_3
        size: 4
      - id: texture_strings
        type: strl(64)
        repeat: expr
        repeat-expr: 4
      - id: render_settings_1
        size: 7
      - id: unknown_4
        size: 1
      - id: transparency_shift
        type: f4
      - id: render_settings_2
        size: 12
      - id: unknown_5
        size: 4
      - id: render_settings_3
        size: 13
      - id: unknown_6
        size: 20
      - id: day_night_transition_string
        type: strl(200)
      - id: unknown_7
        size: 23
      - id: light_map_name
        type: strl(64)
      - id: unknwon_8
        size: 8
      - id: material
        type: ptr('material', _root.header.offset_tex_data_dummy + 32)
      - id: unknown_9
        size: 4
        if: is_skin
      - id: bones
        type: array_ptr('bone', _root.header.offset_tex_data_dummy + 32)
        if: is_skin
      - id: unknown_11
        size: 4
      - id: vertices
        type: array_ptr('vertex', 32)
      - id: normals
        type: array_ptr('normal', 32)
      - id: tangents
        type: array_ptr('vector3ofs2', 32)
      - id: binormals
        type: array_ptr('vector3ofs2', 32)
      - id: uvs
        type: array_ptr('uv', 32)
        repeat: expr
        repeat-expr: 4
      - id: unknown_array
        type: array_ptr('unknown', 32)
      - id: faces
        type: array_ptr('face', 32)
      - id: unknown_10
        size: 36
        if: is_skin
      - id: weights
        type: array_ptr('f4', 32)
        if: is_skin
      - id: bones_something_ptr
        type: array_ptr('unknown', 32)
        if: is_skin
    instances:
      is_skin:
        value: _parent.node_type == node_type::skin
enums:
  controller_type:
    84: position
    96: orientation
    184: scale
    276: self_illum
    292: alpha
  node_type:
    1: node
    3: light
    5: emitter
    9: camera
    17: reference
    33: trimesh
    97: skin
    545: aabb
    1057: trigger
    4097: sector_info
    8193: walk_mesh
    16385: dangly_node
    32769: texture_paint
    65537: speed_tree
    131073: chain
    262145: cloth