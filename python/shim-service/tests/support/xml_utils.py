import xml.etree.ElementTree as ET
from typing import Optional, Tuple, Any, List
from xml.etree.ElementTree import Element
from xml.sax.saxutils import escape


def parse_xml(file_name: str) -> Element:
    tree = ET.parse(file_name)
    return tree.getroot()


def parse_xml_string(xml: str) -> Element:
    tree = ET.fromstring(xml)
    return tree


def get_child_text(element: Element, name: str) -> Optional[str]:
    child = get_child(element, name)
    if child is not None:
        if child.text is None:
            return ""
        return child.text
    return None


def get_child_int(element: Element, name: str) -> Optional[int]:
    v = get_child_text(element, name)
    if v is None:
        return None
    return int(v)


def get_child(element: Element, tag: str):
    if "/" in tag:
        result = resolve_parent(element, tag)
        if result is None:
            return None
        tag = result[0]
        element = result[1]

    for child in element:
        if to_short_tag(child.tag) == tag:
            return child

    return None


def resolve_parent(element: Element, tag: str) -> Optional[Tuple[str, Element]]:
    index = tag.find("/")
    while index > 0:
        parent = tag[0:index:]
        element = get_child(element, parent)
        tag = tag[index + 1::]
        if element is None:
            return None
        index = tag.find("/")

    return tag, element


def get_attribute_int(element: Element, name: str) -> Optional[int]:
    v = get_attribute(element, name)
    if v is None:
        return None
    return int(v)


def get_attribute(element: Element, name: str) -> Optional[str]:
    return element.attrib.get(name)


def find_child_with_attribute(element: Element, tag: str, attribute_name: str, attribute_value: str) -> Optional[Any]:
    result = resolve_parent(element, tag)
    if result is None:
        return None
    tag = result[0]
    element = result[1]

    for child in element:
        if child.tag == tag:
            v = get_attribute(child, attribute_name)
            if v is not None and v == attribute_value:
                return child
    return None


def get_children_as_ints(element: Element, tag: str) -> Optional[List[int]]:
    result = resolve_parent(element, tag)
    if result is None:
        return None
    tag = result[0]
    element = result[1]

    int_values = []
    for child in element:
        if child.tag == tag:
            int_values.append(int(child.text))

    return int_values


def escape_value(value: Any) -> Any:
    if value is not None:
        if not isinstance(value, str):
            if type(value) is bool:
                value = str(value).lower()
            else:
                value = str(value)
        else:
            value = escape(value)
    return value


def to_short_tag(tag: str):
    if tag.startswith('{'):
        index = tag.rfind("}")
        if index > 0:
            tag = tag[index + 1::]

    return tag
