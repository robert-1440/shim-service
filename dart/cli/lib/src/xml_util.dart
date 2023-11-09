import 'package:xml/xml.dart';

class ElementNotFoundException {
  final String element;

  ElementNotFoundException(this.element);

  @override
  String toString() {
    return "Unable to find element: $element";
  }
}

XmlElement? _findTag(XmlElement source, String tag) {
  for (var node in source.descendantElements) {
    if (node.name.local == tag) {
      return node;
    }
  }
  return null;
}

String? findChildString(XmlElement source, String tag) {
  var n = findChild(source, tag);
  if (n == null) {
    return null;
  }
  if (n.children.isEmpty) {
    return null;
  }
  var child = n.children[0];
  if (child is XmlText) {
    return child.value;
  }

  return null;
}

String getChildString(XmlElement source, String tag) {
  var v = findChildString(source, tag);
  if (v == null) {
    throw ElementNotFoundException(tag);
  }
  return v;
}

XmlElement getChild(XmlElement source, String tag) {
  var e = findChild(source, tag);
  if (e == null) {
    throw ElementNotFoundException(tag);
  }
  return e;
}

XmlElement? findChild(XmlElement source, String tag) {
  var parts = tag.split("/");
  XmlElement? node = source;
  for (var part in parts) {
    var elem = _findTag(node!, part);
    if (elem == null) {
      return null;
    }
    node = elem;
  }
  return node;
}
