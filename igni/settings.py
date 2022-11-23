import yaml


class Settings:

    """
    this is a utility class for settings
    usage: TODO
    """

    def accept_tree(self, tree: dict):

        def flatten(dict_):

            props = {}

            def recursive_tree_flatten(presumably_dict, cumulative_name):
                if isinstance(presumably_dict, dict):
                    certainly_dict = presumably_dict
                    for key in certainly_dict:
                        recursive_tree_flatten(certainly_dict[key], cumulative_name + '.' + key)
                else:
                    not_a_dict = presumably_dict
                    props[cumulative_name] = not_a_dict

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
        if property_name in self._props:
            return self._props[property_name]
        else:
            raise Exception('missing required property "{}"'.format(property_name))

    def set(self, property_name, property_value):
        if self._type_hint is None \
                or self._type_hint._props.get(property_name, None) is None \
                or self._type_hint._props[property_name] is type(property_value):
            self._props[property_name] = property_value
            return

        # discrepancy in hinted type and type of supplied value --> try to convert to hinted type
        _hint_type = self._type_hint._props[property_name]

        # only a set of values allowed
        if isinstance(_hint_type, set):
            if property_value not in _hint_type:
                raise Exception('value "{}" is not allowed for property "{}"'.format(property_value, property_name))
            else:
                self._props[property_name] = property_value

        # boolean also needs special handling
        elif _hint_type is bool:
            if type(property_value) is str:
                if property_value.lower() in ['yes', 'y', '1', 'true', 't']:
                    self._props[property_name] = True
                elif property_value.lower() in ['no', 'n', '0', 'false', 'f']:
                    self._props[property_name] = False
                else:
                    raise Exception('cannot parse boolean value "{}" for property "{}"'.format(
                        property_value,
                        property_name
                    ))
            else:
                self._props[property_name] = bool(property_value)

        # some other combination of types that are not equal
        else:
            try:
                self._props[property_name] = _hint_type(property_value)
            except Exception as e:
                raise Exception('could not convert property value "{}" to type required "{}" for property "{}"'.format(
                    property_value,
                    _hint_type,
                    property_name
                ))
