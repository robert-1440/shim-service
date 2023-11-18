from copy import deepcopy
from typing import Mapping, Union, Callable, Any, Dict, List

VariableFilter = Callable[[str], bool]


class EasyException(Exception):
    """
    Exception that makes it easy to get the message out.
    """

    def __init__(self, message: str, cause: Exception = None):
        super(EasyException, self).__init__(message)
        if cause is not None and (isinstance(cause, TypeError) or isinstance(cause, AttributeError) or \
                                  isinstance(cause, AssertionError)):
            raise cause
        self.message = message
        self.cause = cause


class ValidationException(EasyException):
    """
    General validation exception. Can be used to catch when there is no need for a stack trace to be shown.
    """

    def __init__(self, message: str):
        super(ValidationException, self).__init__(message)


class UnresolvedPropertyException(Exception):
    def __init__(self, property_name: str):
        super(UnresolvedPropertyException, self).__init__(f"Cannot resolve property '{property_name}'")
        self.property_name = property_name


def replace_properties(properties: Union[Mapping, Callable[[str], Any]],
                       text: Union[str, List[str]],
                       fail_on_error: bool = False,
                       ignore_default=False,
                       variable_exclude_filter: VariableFilter = None,
                       process_replaced_variables: bool = True,
                       brace_types: str = None) -> Union[str, List[str]]:
    """
    Replaces properties/variables found in the given text, of the format *${variable-name}*.

    Default values are supported by supplying it as a : suffix. i.e: ``${value:default_value}``.

    :param properties: the mapping (dict, etc.) of property names and values, or the callable to call to get values.
    :param text: the text.
    :param fail_on_error: True to fail if any variables cannot be resolved.
    :param ignore_default: Do not treat ':' in property name as a default value specifier.
    :param variable_exclude_filter: optional function to use to indicate variables that should be ignored.
    :param process_replaced_variables: Set to False to not evaluate variables found in replaced values.
    :param brace_types: the brace types for the variables. Default is {}.
    :return: the text with variables replaced.
    :raise UnresolvedPropertyException: if fail_on_error is True and a property cannot be resolved.
    """

    if text is None:
        return None

    if brace_types is None:
        brace_types = "{}"

    if type(text) is list:
        values = text
        for i in range(len(values)):
            text = values[i]
            new_line = replace_properties(properties, text, fail_on_error=fail_on_error,
                                          ignore_default=ignore_default,
                                          variable_exclude_filter=variable_exclude_filter,
                                          process_replaced_variables=process_replaced_variables,
                                          brace_types=brace_types)
            if new_line != text:
                values[i] = new_line
        return values

    mapper = properties if callable(properties) else lambda k: properties.get(k)

    def get_var(name: str):
        v = mapper(name)
        if v is not None:
            if type(v) is not str:
                v = str(v)
        return v

    start_index = 0
    any_empty = False
    start_pattern = f"${brace_types[0]}"
    end_pattern = brace_types[1]
    while True:
        index = text.find(start_pattern, start_index)
        if index < 0:
            break
        if index > start_index and text[index - 1] == "$":
            left = text[0:index]
            right = text[index + 1::]
            text = left + right
            start_index = index + 1
            continue
        end_index = text.find(end_pattern, index)
        if end_index < 0:
            break
        full_var = text[index:end_index + 1:]
        var_part = full_var[2:end_index - index:]
        if var_part.startswith("~"):
            trim_if_empty = True
            var_part = var_part[1::]
        else:
            trim_if_empty = False

        if ignore_default:
            default_value = None
            var_name = var_part
        else:
            parts = var_part.split(":")
            var_name = parts[0]
            if len(parts) > 1:
                default_value = parts[1]
            else:
                default_value = None

        if variable_exclude_filter is not None and variable_exclude_filter(var_name):
            start_index = end_index
            continue
        value = get_var(var_name)
        if value is None and default_value is not None:
            value = default_value
        if value is None:
            if fail_on_error:
                raise UnresolvedPropertyException(var_name)
            start_index = end_index
        else:
            if full_var in value:
                raise ValidationException(f"Circular reference for property {var_name}.")
            if trim_if_empty:
                if value.isspace():
                    value = "<<remove>>"
                else:
                    value += "<<remove>>"
                any_empty = True
            text = text.replace(full_var, value)
            if process_replaced_variables:
                start_index = index
            else:
                start_index = index + len(value)
    if any_empty:
        text = text.replace("<<remove>>\n", "")
        text = text.replace("<<remove>>", "")
    return text


def replace_properties_in_dict(source: Union[dict, Mapping],
                               properties: Mapping,
                               in_place: bool = False,
                               fail_on_error: bool = False,
                               variable_exclude_filter: VariableFilter = None,
                               brace_types: str = None,
                               validate_keys: bool = None) -> dict:
    """
    Replaces all property values in the given dictionary whose values containthe format *${variable-name}*
    :param source: the dictionary to replace
    :param properties: the properties to get values from.
    :param in_place: True to modify the source directly vs copying.
    :param fail_on_error: True to fail in cases where properties cannot be found.
    :param variable_exclude_filter: optional function to use to indicate variables that should be ignored.  It
    :param brace_types: brace types to use, default is "{}"
    should return True on variable names that should be ignored.
    :param validate_keys: True to ensure that no property references exists in the keys.
    :return: the resolved dictionary.
    """

    if not in_place:
        source = deepcopy(source)

    def visitor(source_dict: dict, key: str, value: Any):
        if validate_keys and type(key) is str:
            replace_properties({}, key, fail_on_error=True)
        if value is not None:
            if type(value) is str:
                value: str
                new_value = replace_properties(properties, value, fail_on_error=fail_on_error,
                                               variable_exclude_filter=variable_exclude_filter,
                                               brace_types=brace_types)
                if new_value != value:
                    source_dict[key] = new_value

    visit_dictionary(source, visitor)

    return source


def visit_dictionary(source: dict, visitor: Callable[[dict, str, Any], None],
                     visit_list_elements: bool = True):
    """
    Visits all values in the given dictionary.  The visitor needs to accept dict, key and value.

    :param source: the dictionary.
    :param visitor: the visitor to call for each item in the dictionary.
    :param visit_list_elements: True to visit each element of list values.
    :return: None
    """
    for key, value in source.items():
        __visit_value(source, key, value, visitor, visit_list_elements)


def visit_all_dict_values(source: Union[dict, list], visitor: Callable[[dict, str, Dict[str, Any]], None]):
    """
    Visits all values that are dictionaries in the given dictionary.  The visitor needs to accept dict, key and value.

    :param source: the dictionary.
    :param visitor: the visitor to call for each dict item in the dictionary.
    :return: None
    """
    if type(source) is list:
        source = {"main": source}
    for key, value in source.items():
        __visit_dict_values(source, key, value, visitor)


def __visit_dict_values(source: dict, key: str, value: Any, visitor: Callable[[dict, str, Dict[str, Any]], None]):
    if type(value) is dict:
        visitor(source, key, value)
        visit_all_dict_values(value, visitor)
    elif type(value) is list:
        for v in value:
            __visit_dict_values(source, key, v, visitor)


def __visit_value(source: dict, key: str, value: Any, visitor: Callable[[dict, str, Any], None],
                  visit_list_elements: bool):
    if type(value) is dict:
        visit_dictionary(value, visitor, visit_list_elements=visit_list_elements)
    elif visit_list_elements and type(value) is list:
        for v in value:
            __visit_value(source, key, v, visitor, True)
    else:
        visitor(source, key, value)
