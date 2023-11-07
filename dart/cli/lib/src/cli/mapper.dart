import 'dart:collection';
import 'dart:collection' as collection;
import 'dart:io';

import '../cli/util.dart';
import 'package:yaml/yaml.dart';

class MapWrapper {
  final Map<String, dynamic> _source;

  MapWrapper._$(this._source);

  String getString(String key) {
    return get(key) as String;
  }

  ///
  /// Convenience method to ensure the value returns as a csv, in the event that it happens to be a list of strings.
  String getStringAsCsv(String key) {
    var v = get(key);
    if (v is List) {
      v = v.join(",");
    }
    return v as String;
  }

  List<String>? findCsv(String key) {
    return splitAndTrimIfNotNull(_source[key]);
  }

  List<String>? findStringList(String key) {
    var v = _source[key];
    if (v == null) {
      return null;
    }
    return List.castFrom(v);
  }

  String? findStringAsCsv(String key) {
    var v = _source[key];
    if (v == null) {
      return null;
    }
    if (v is List) {
      v = v.join(",");
    }
    return v as String;
  }

  String? findString(String key) {
    return _source[key] as String?;
  }

  Object get(String key) {
    var v = _source[key];
    if (v == null) {
      throw ArgumentError("$key does not exist.");
    }
    return v!;
  }

  dynamic operator [](String name) {
    return _source[name];
  }

  static MapWrapper of(Map<String, dynamic> map) {
    return MapWrapper._$(map);
  }

  int getInt(String key) {
    return get(key) as int;
  }

  int? findInt(String key) {
    var v = this[key];
    if (v == null) {
      return null;
    }
    return v;
  }

  Map<String, dynamic>? findMap(String key) {
    var v = this[key];
    if (v == null) {
      return null;
    }
    return v;
  }
}

Set<T> toTreeSet<T>(Iterable<T> values) {
  var set = SplayTreeSet<T>();
  set.addAll(values);
  return set;
}

abstract class MapperException implements Exception {
  final String message;

  MapperException(this.message);

  @override
  String toString() {
    return message;
  }
}

class MissingPropertyException extends MapperException {
  MissingPropertyException(String propertyName) : super("Missing required property: '$propertyName'");
}

class NullPropertyException extends MapperException {
  NullPropertyException(String propertyName) : super("'$propertyName' cannot be null.");
}

class EmptyPropertyException extends MapperException {
  EmptyPropertyException(String propertyName) : super("'$propertyName' cannot be empty.");
}

class UnexpectedPropertiesException extends MapperException {
  UnexpectedPropertiesException(String prefix, Iterable<String> propertyNames)
      : super("${prefix}The following properties are unexpected: ${propertyNames.join(', ')}");
}

class WrongTypeException extends MapperException {
  WrongTypeException(String propertyName, Object value, String expectedType)
      : super("For property '$propertyName', '$value' is not a valid $expectedType.");
}

T castIt<T>(String key, String expectedType, Object value) {
  try {
    T result = value as T;
    return result;
  } catch (ex) {
    throw WrongTypeException(key, value, expectedType);
  }
}

List<T> castList<T>(String key, String expectedType, dynamic value) {
  try {
    return castIt(key, expectedType, value);
  } on WrongTypeException {
    // try manually
  }
  List<T> results = [];
  for (var e in value) {
    try {
      results.add(e as T);
    } catch (ex) {
      throw WrongTypeException(key, e, expectedType);
    }
  }
  return results;
}

String toStringValue(dynamic value) {
  if (value == null) {
    return "";
  }
  if (value is! String) {
    if (value is int || value is double || value is bool) {
      value = value.toString();
    } else {
      throw ArgumentError("$value cannot be safely transformed to a string.");
    }
  }
  return value;
}

class MapNode {
  final Map<String, dynamic> _source;

  final String? _name;

  final MapNode? _parent;

  String? _fullName;

  MapNode._$(this._source, {String? name, MapNode? parent})
      : _name = name,
        _parent = parent;

  Iterable<String> get keys => _source.keys;

  Iterable<MapEntry<String, dynamic>> get entries => _source.entries;

  String get name => _name ?? "";

  operator []=(String key, dynamic value) {
    if (value is Map) {
      value = createMapMode(value);
    }
    _source[key] = value;
  }

  dynamic removeRequired(String key, {bool nullOk = true}) {
    return remove(key, required: true, nullOk: nullOk);
  }

  dynamic remove(String key, {bool required = false, bool nullOk = true}) {
    return _get(key, required: required, nullOk: nullOk, remove: true);
  }

  MapNode removeRequiredMapNode(String key) {
    return removeMapNode(key, required: true)!;
  }

  MapNode? removeMapNode(String key, {bool required = false}) {
    var v = remove(key, required: required);
    return v == null ? null : castIt(getName(key), "map", v);
  }

  void add(MapNode node) {
    for (var entry in node.entries) {
      _source[entry.key] = entry.value;
    }
  }

  Map<String, dynamic>? findMap(String key) {
    MapNode? m = castIt(getName(key), "map", get(key));
    return m?.toMap();
  }

  Map<String, V> removeAndConvertMap<V>(String key, V Function(MapNode) mapper, {bool required = false}) {
    var result = <String, V>{};
    var v = remove(key, required: required);
    if (v != null) {
      MapNode node = castIt(getName(key), "map", v);
      for (var key in node.keys.toList(growable: false)) {
        result[key] = mapper(node.removeRequiredMapNode(key));
      }
    }
    return result;
  }

  Map<String, dynamic> toMap() {
    Map<String, dynamic> map = {};
    for (var entry in _source.entries) {
      map[entry.key] = _resolve(entry.value);
    }
    return map;
  }

  dynamic _resolve(dynamic v) {
    if (v == null) {
      return null;
    }
    if (v is MapNode) {
      v = v.toMap();
    } else if (v is List) {
      var results = [];
      for (var e in v) {
        results.add(_resolve(e));
      }
      v = results;
    }
    return v;
  }

  dynamic resolveValue(String key) {
    return _resolve(this[key]);
  }

  bool? removeBool(String key, {bool required = false}) {
    var v = remove(key, required: required);
    return v == null ? null : castIt(getName(key), "boolean", v);
  }

  String? removeString(String key, {bool required = false, bool nullOk = true, bool emptyOk = true}) {
    return _getString(key, required: required, nullOk: nullOk, remove: true);
  }

  int? removeInt(String key, {bool required = false, int? minValue}) {
    var v = remove(key, required: required);
    if (v == null) {
      return null;
    }
    if (v is! int) {
      throw WrongTypeException(getName(key), v, "integer");
    }
    if (minValue != null) {
      if (v < minValue) {
        throw Exception("${getName()}: $key value of $v is less then the minimum value of $minValue");
      }
    }
    return v;
  }

  MapNode removeRequiredMap(String key) {
    var n = removeRequired(key, nullOk: false);
    if (n is! MapNode) {
      throw WrongTypeException(getName(key), n, "map");
    }
    return n;
  }

  List<MapNode> removeMapList(String key, {bool required = false}) {
    var n = remove(key, required: required);
    if (n == null) {
      return List.empty(growable: false);
    }
    return castList(getName(key), "List of maps vs $n", n);
  }

  List<String>? findCsv(String key) {
    String? v = this[key];
    if (v == null) {
      return null;
    }
    return splitAndTrim(v);
  }

  List<String> getRequiredStringList(String key) {
    var v = getRequired(key);
    List<String> results = [];
    if (v != null) {
      for (var s in v) {
        results.add(s);
      }
    }
    return results;
  }

  List<String> removeRequiredStringList(String key) {
    var v = removeRequired(key);
    List<String> results = [];
    if (v != null) {
      for (var s in v) {
        results.add(s);
      }
    }
    return results;
  }

  List<String> removeStringList(String key) {
    var v = remove(key);
    List<String> results = [];
    if (v != null) {
      for (var s in v) {
        results.add(s);
      }
    }
    return results;
  }

  List<String>? findStringList(String key) {
    var v = get(key);
    if (v == null) {
      return null;
    }
    List<String> results = [];
    for (var s in v) {
      results.add(s);
    }
    return results;
  }

  dynamic _get(String key, {bool required = false, bool nullOk = true, bool remove = false}) {
    bool keyExists = _source.containsKey(key);
    var v = keyExists
        ? remove
            ? _source.remove(key)
            : _source[key]
        : null;
    if (v == null) {
      if (required && !keyExists) {
        throw MissingPropertyException(getName(key));
      }
      if (!nullOk && keyExists) {
        throw NullPropertyException(getName(key));
      }
    }
    return v;
  }

  dynamic getRequired(String key, {bool nullOk = true}) {
    return get(key, required: true, nullOk: nullOk);
  }

  dynamic get(String key, {bool required = false, bool nullOk = true}) {
    return _get(key, required: required, nullOk: nullOk);
  }

  String getRequiredString(String key) {
    return _getString(key, nullOk: false, emptyOk: false)!;
  }

  int getRequiredInt(String key) {
    var v = getRequired(key);
    if (v is! int) {
      throw WrongTypeException(getName(key), v, "integer");
    }
    return v;
  }

  String removeRequiredString(String key) {
    return removeString(key, required: true, nullOk: false, emptyOk: false)!;
  }

  String? _getString(String key, {bool required = false, bool nullOk = true, bool emptyOk = true, bool remove = false}) {
    var v = _get(key, required: required, nullOk: nullOk, remove: remove);
    if (v != null) {
      String sv = v = toStringValue(v);
      if (!emptyOk && sv.isEmpty) {
        throw EmptyPropertyException(getName(key));
      }
    }
    return v;
  }

  void assertEmpty() {
    if (_source.isNotEmpty) {
      String name = getName();
      if (name.isNotEmpty) {
        name += ": ";
      }
      throw UnexpectedPropertiesException(name, _source.keys);
    }
  }

  String getName([String? withName]) {
    _fullName ??= _buildName();
    return withName == null
        ? _fullName!
        : _fullName!.isEmpty
            ? withName
            : "$_fullName/$withName";
  }

  String _buildName() {
    if (_name == null) {
      return "";
    }
    if (_parent == null) {
      return _name!;
    }
    return _parent!.getName(_name!);
  }

  operator [](String key) => get(key);
}

MapNode _buildMapNode(Map source, {String? name, MapNode? parent}) {
  Map<String, dynamic> map = {};
  var node = MapNode._$(map, name: name, parent: parent);
  for (var entry in source.entries) {
    map[entry.key] = _translateValue(entry.value, name: entry.key, parent: node);
  }
  return node;
}

dynamic _translateValue(dynamic value, {String? name, MapNode? parent}) {
  if (value != null) {
    if (value is MapBase) {
      value = _buildMapNode(value, name: name, parent: parent);
    } else if (value is List || value is collection.ListMixin) {
      var values = [];
      for (int i = 0; i < value.length; i++) {
        values.add(_translateValue(value[i], name: "$name[$i]", parent: parent));
      }
      value = values;
    }
  }
  return value;
}

MapNode createMapMode(Map source) {
  return _buildMapNode(source);
}

MapNode parseYaml(String yamlText) {
  return createMapMode(loadYaml(yamlText));
}

MapNode parseYamlFile(String fileName) {
  var f = File(fileName);
  if (!f.existsSync()) {
    fatalError("$fileName does not exist.");
  }
  return parseYaml(f.readAsStringSync());
}

class NonNullMap<K, V> extends MapBase<K, V> {
  final Map<K, V> _delegate = {};

  @override
  bool get isEmpty => _delegate.isEmpty;

  @override
  bool get isNotEmpty => _delegate.isNotEmpty;

  @override
  int get length => _delegate.length;

  @override
  V? operator [](Object? key) {
    return _delegate[key];
  }

  @override
  void operator []=(K key, V? value) {
    if (value != null) {
      _delegate[key] = value;
    }
  }

  @override
  void clear() {
    _delegate.clear();
  }

  @override
  Iterable<K> get keys => _delegate.keys;

  @override
  V? remove(Object? key) {
    return _delegate.remove(key);
  }

  static NonNullMap<String, dynamic> of(MapNode node) {
    var map = NonNullMap<String, dynamic>();
    for (var entry in node.entries.where((element) => element.value != null)) {
      map[entry.key] = entry.value;
    }
    return map;
  }
}

Map<String, dynamic> determinePatch(Map<String, dynamic> current, Map<String, dynamic> newMap) {
  Map<String, dynamic> patch = <String, dynamic>{};
  for (var entry in newMap.entries) {
    var currentValue = current[entry.key];
    if (currentValue != entry.value) {
      patch[entry.key] = entry.value;
    }
  }
  return patch;
}

void trimNullValues<K, V>(Map<K, V> source) {
  source.removeWhere((key, value) => value == null);
}
