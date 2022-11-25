import yaml


class Settings:

    """
    this is a utility class for settings
    usage: TODO
    """

    class PropertyPath:

        @classmethod
        def from_string(cls, str_path):
            if str_path.startswith('.') or str_path.endswith('.'):
                raise Exception('invalid property path {}'.format(str_path))
            return cls(str_path.split('.'))

        def __init__(self, parts):
            if parts is None:
                raise Exception('property path cannot be empty')
            self.parts = parts

        def __str__(self):
            return self.parts.join('.')

        def __hash__(self):
            return hash(str(self))

        def __add__(self, other):
            if not isinstance(other, type(self)):
                raise Exception('cannot add path to a non-path')
            return type(self)(self.parts + other.parts)

        def is_superpath_of(self, path):
            if not isinstance(path, type(self)):
                raise Exception('expected argument of type path')
            if len(self.parts) > len(path.parts):
                return False
            else:
                return all([path.parts[i] == self.parts[i] for i in range(0, len(self.parts))])

    def accept_tree(self, tree: dict):

        def flatten(dict_):

            props = {}

            def recursive_tree_flatten(presumably_dict, cumulative_path):
                if isinstance(presumably_dict, dict):
                    certainly_dict = presumably_dict
                    for key in certainly_dict:
                        recursive_tree_flatten(certainly_dict[key], cumulative_path + [key])
                else:
                    not_a_dict = presumably_dict
                    props[self.PropertyPath(cumulative_path)] = not_a_dict

            for key in dict_:
                recursive_tree_flatten(dict_[key], key)

            return props

        return self.accept_props(flatten(tree))

    def accept_props(self, props: dict):
        [self.set(prop_name, prop_val) for prop_name, prop_val in props.items()]
        return self

    def accept_yaml(self, path: str):
        return self.accept_tree(yaml.load(path))

    def accept_cmd_args(self, cmd_args: list):
        for cmd_arg in cmd_args:
            key_and_val = cmd_arg.split('=')
            if len(key_and_val) != 2:
                raise Exception('invalid command line setting: "{}"'.format(cmd_arg))

            key = key_and_val[0]
            while key.startswith('-'):
                key = key[1:]

            val = key_and_val[1]

            self.set(key, val)

        return self

    def __init__(self, type_hint=None):
        self._type_hint = type_hint
        self._props = {}

    def has(self, property_name):
        return property_name in self._props

    def get(self, property_name):

        property_path = self.PropertyPath(property_name)
        if property_path in self._props:
            return self._props[property_name]
        else:
            # try to return nested settings
            nested_props = {nested_property_path: nested_property_value for
                            nested_property_path, nested_property_value in self._props if
                            property_path.is_superpath_of(nested_property_path)}
            if len(nested_props) == 0:
                raise Exception('missing required property "{}"'.format(property_name))

            nested_type_hint_props = None
            if self._type_hint is not None:
                nested_type_hint_props = {
                    nested_property_path: nested_property_value for
                    nested_property_path, nested_property_value in self._type_hint._props
                    if nested_property_path in nested_props
                }

            return Settings(nested_type_hint_props).accept_props(nested_props)

    def set(self, property_name, property_value):

        property_path = self.PropertyPath(property_name)

        if type(property_value) is Settings:
            [self.set(property_path + nested_property_path, nested_property_value) for
             nested_property_path, nested_property_value in property_value._props.items()]

            if property_value._type_hint is not None:
                if self._type_hint is None:
                    self._type_hint = Settings()
                [self._type_hint.set(property_path + nested_property_path, nested_property_value) for
                 nested_property_path, nested_property_value in property_value._type_hint._props.items()]

        if self._type_hint is None \
                or self._type_hint._props.get(property_path, None) is None \
                or self._type_hint._props[property_path] is type(property_value):  # < is already of desired type
            self._props[property_path] = property_value
            return

        # discrepancy in hinted type and type of supplied value --> try to convert to hinted type
        _hint_type = self._type_hint._props[property_path]

        '''
        special handling required for the following types:
        - bool
        - set (enum values are specified)
        - list
        '''

        # only a set of values allowed
        if isinstance(_hint_type, set):
            if property_value not in _hint_type:
                raise Exception('value "{}" is not allowed for property "{}". '.format(property_value, property_path) +
                                'allowed values: {}'.format(_hint_type))
            else:
                self._props[property_path] = property_value

        # boolean also needs special handling
        elif _hint_type is bool:
            if type(property_value) is str:
                if property_value.lower() in ['yes', 'y', '1', 'true', 't']:
                    self._props[property_path] = True
                elif property_value.lower() in ['no', 'n', '0', 'false', 'f']:
                    self._props[property_path] = False
                else:
                    raise Exception('cannot parse boolean value "{}" for property "{}"'.format(
                        property_value,
                        property_path
                    ))
            else:
                self._props[property_path] = bool(property_value)

        # some other combination of types that are not equal
        else:
            try:
                self._props[property_path] = _hint_type(property_value)
            except Exception as e:
                raise Exception('could not convert property value "{}" to type required "{}" for property "{}"'.format(
                    property_value,
                    _hint_type,
                    property_path
                ))

        return self
