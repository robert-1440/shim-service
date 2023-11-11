import 'dart:collection';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:uuid/uuid.dart';

bool exitMode = true;

int maxColumnWidth = 190;

class Pair<L, R> {
  final L left;

  final R right;

  Pair._$(this.left, this.right);

  static Pair<L, R> of<L, R>(L left, R right) {
    return Pair._$(left, right);
  }
}

abstract class Mappable {
  Map<String, dynamic> toMap();

  @override
  String toString() {
    return JsonEncoder.withIndent("  ").convert(toMap());
  }

  String toJson() {
    return jsonEncode(toMap());
  }
}

final lineSplitter = LineSplitter();

class StringBuilder {
  final StringBuffer _sb = StringBuffer();

  StringBuilder([String? initialString]) {
    if (initialString != null) {
      _sb.write(initialString);
    }
  }

  StringBuilder appendLine(dynamic object) {
    return append(object).lineFeed();
  }

  int get length => _sb.length;

  bool get isNotEmpty => _sb.isNotEmpty;

  bool get isEmpty => _sb.isEmpty;

  StringBuilder append(dynamic object) {
    var v = toStringValue(object);
    if (v.isNotEmpty) {
      _sb.write(v);
    }
    return this;
  }

  StringBuilder lineFeed() {
    _sb.writeln();
    return this;
  }

  @override
  String toString() => _sb.toString();
}

class StringIndentWriter {
  final StringBuffer _sb = StringBuffer();

  final String _indentChars;

  String _indent = "";

  int _indentCount = 0;

  bool _needLf = false;

  int _lineLength = 0;

  StringIndentWriter([String? indentChars]) : _indentChars = indentChars ?? "    ";

  void _writeIndent() {
    if (_indentCount > 0) {
      _sb.write(_indent);
    }
  }

  void indent([int count = 1]) {
    if (count > 0) {
      _adjustIndent(count);
    }
  }

  void unIndent([int count = 1]) {
    if (count > 0) {
      _adjustIndent(-count);
    }
  }

  void _adjustIndent(int count) {
    _indentCount = max(0, _indentCount + count);
    if (_indentCount > 0) {
      _indent = _indentChars * _indentCount;
    } else {
      _indent = "";
    }
  }

  void _writeWithLf(String text) {
    if (text.isNotEmpty) {
      _sb.write(text);
    }
    addLf();
  }

  StringIndentWriter addLineFromCurrent(String text) {
    if (_needLf && _lineLength > 0) {
      var current = _indent;
      var count = _indentCount;
      try {
        _indentCount = _lineLength;
        _indent = ' ' * _indentCount;
        addLine(text);
        return this;
      } finally {
        _indent = current;
        _indentCount = count;
      }
    }
    addLine(text);
    return this;
  }

  StringIndentWriter addLine(String text) {
    add("$text\n");
    return this;
  }

  StringIndentWriter addLf() {
    _sb.write('\n');
    _needLf = false;
    return this;
  }

  StringIndentWriter add(String text) {
    var lines = lineSplitter.convert(text);
    var lastLine = lines.removeLast();

    for (var line in lines) {
      if (!_needLf && line.isNotEmpty) {
        _writeIndent();
      }
      _writeWithLf(line);
    }
    if (!_needLf && lastLine.isNotEmpty) {
      _writeIndent();
    }
    if (text.endsWith("\n")) {
      _writeWithLf(lastLine);
    } else {
      _sb.write(lastLine);
      _needLf = true;
      _lineLength = lastLine.length;
    }
    return this;
  }

  @override
  String toString() {
    return _sb.toString();
  }
}

String toJson(Object thing, {bool pretty = false}) {
  if (pretty) {
    return JsonEncoder.withIndent("  ").convert(thing);
  }
  return jsonEncode(thing);
}

String _fixLinesLength(String text) {
  var lines = lineSplitter.convert(text);
  String result = "";
  for (int i = 0; i < lines.length; i++) {
    if (i > 0) {
      result += '\n';
    }
    var line = lines[i];
    if (line.length > maxColumnWidth) {
      line = "${line.substring(0, maxColumnWidth)}...";
    }
    result += line;
  }
  return result;
}

class LayoutBuilder {
  int _maxLen = 0;

  final bool _rightJustifyKeys;

  final String? _separator;

  LayoutBuilder({bool rightJustifyKeys = false, String? separator})
      : _rightJustifyKeys = rightJustifyKeys,
        _separator = separator;

  final List<List<String>> _rows = [];

  void add(String key, dynamic value) {
    if (value == null) {
      value = "null";
    } else if (value is! String) {
      if (value is MapMixin || value is ListMixin) {
        value = toJson(value, pretty: true);
      } else {
        value = value.toString();
      }
    }

    value = _fixLinesLength(value);

    _maxLen = max(key.length, _maxLen);
    _rows.add([key, value]);
  }

  static String formatMap<T>(Map<String, T> map, {bool rightJustifyKeys = false}) {
    var lb = LayoutBuilder();
    for (var entry in map.entries) {
      lb.add(entry.key, entry.value);
    }
    return lb.toString();
  }

  String _pad(String value, int width) {
    return _rightJustifyKeys ? '${value.padLeft(width)} ' : value.padRight(width);
  }

  StringIndentWriter _addKey(String key, StringIndentWriter sw) {
    var maxLen = _maxLen;
    if (_separator != null) {
      maxLen += _separator!.length;
    }

    if (_rightJustifyKeys) {
      key = key.padLeft(maxLen);
      if (_separator != null) {
        key += _separator!;
      }
    } else {
      if (_separator != null) {
        key += _separator!;
      }
      key = key.padRight(maxLen);
    }
    sw.add("$key ");
    return sw;
  }

  @override
  String toString({int indentCount = 0, String? indentChars}) {
    var sw = StringIndentWriter(indentChars);
    if (indentCount > 0) {
      sw.indent(indentCount);
    }
    for (var row in _rows) {
      var key = row[0];
      var value = row[1];
      _addKey(key, sw).addLineFromCurrent(value);
    }
    return sw.toString();
  }
}

String lowerCamelCaseToTitle(String name) {
  if (name.isEmpty) {
    return name;
  }
  var sb = StringBuffer();
  sb.write(name[0].toUpperCase());
  for (int i = 1; i < name.length; i++) {
    String c = name[i];
    if (c.toUpperCase() == c) {
      sb.write(' ');
    }
    sb.write(c);
  }
  return sb.toString();
}

class _Column {
  final String key;

  final String dispayValue;

  _Column(this.key, this.dispayValue);
}

String toStringValue(dynamic value) {
  if (value == null) {
    return "";
  }
  if (value is! String) {
    value = value.toString();
  }
  return value;
}

String _truncate(String value) {
  if (value.length > maxColumnWidth) {
    return "${value.substring(0, maxColumnWidth - 3)}...";
  }
  return value;
}

_Cell _toCell(dynamic value) {
  var stringValue = _truncate(toStringValue(value));
  return _Cell(stringValue, value is int || value is double);
}

class _Cell {
  final String value;

  final bool numeric;

  final int length;

  _Cell(this.value, this.numeric) : length = value.length;

  void format(StringBuffer sb, int width) {
    if (numeric) {
      sb.write(value.padLeft(width));
    } else {
      sb.write(value.padRight(width));
    }
  }
}

class TableBuilder {
  final List<_Column> _columns = [];

  final List<int> _columnLengths = [];

  final List<Map<String, dynamic>> _rows = [];

  late int _cellPadding;

  late String _cellSpacer;

  TableBuilder({int cellPadding = 2}) {
    _cellPadding = max(0, cellPadding);
    if (_cellPadding > 0) {
      _cellSpacer = ' ' * _cellPadding;
    } else {
      _cellSpacer = "";
    }
  }

  TableBuilder addColumn(String key, {String? displayName, bool convertToTitle = false}) {
    displayName ??= key;
    if (convertToTitle) {
      displayName = lowerCamelCaseToTitle(displayName);
    }
    var col = _Column(key, displayName);
    _columnLengths.add(displayName.length);
    _columns.add(col);
    return this;
  }

  TableBuilder addRow(Map<String, dynamic> value) {
    _rows.add(value);
    return this;
  }

  List<Map<String, _Cell>> _generateOutputRows() {
    List<Map<String, _Cell>> outputRows = [];
    for (var row in _rows) {
      int columnIndex = 0;
      Map<String, _Cell> outputRow = {};
      for (var col in _columns) {
        var value = _toCell(row[col.key]);
        outputRow[col.key] = value;
        _columnLengths[columnIndex] = max(_columnLengths[columnIndex], value.length);
        columnIndex++;
      }
      outputRows.add(outputRow);
    }
    return outputRows;
  }

  void _formatHeader(StringBuffer sb) {
    StringBuffer div = StringBuffer();
    int index = 0;
    for (var col in _columns) {
      int width = _columnLengths[index];
      if (index++ > 0) {
        sb.write(_cellSpacer);
        div.write(_cellSpacer);
      }

      sb.write(col.dispayValue.padRight(width));
      div.write('-' * width);
    }
    sb.writeln();
    sb.writeln(div.toString());
  }

  void _formatRow(Map<String, _Cell> row, StringBuffer sb) {
    int index = 0;
    for (var col in _columns) {
      int width = _columnLengths[index];
      if (index++ > 0) {
        sb.write(_cellSpacer);
      }
      var cell = row[col.key];
      if (cell != null) {
        cell.format(sb, width);
      } else {
        sb.write(" " * width);
      }
    }
    sb.writeln();
  }

  String build() {
    if (_columns.isEmpty || _rows.isEmpty) {
      return "";
    }
    var outputRows = _generateOutputRows();
    var sb = StringBuffer();
    _formatHeader(sb);
    for (var row in outputRows) {
      _formatRow(row, sb);
    }
    return sb.toString();
  }
}

String buildTable(List<Map<String, dynamic>> rows) {
  if (rows.isEmpty) {
    return "";
  }
  var didColumns = false;
  var tb = TableBuilder();
  for (var row in rows) {
    if (!didColumns) {
      for (var key in row.keys) {
        tb.addColumn(key, convertToTitle: true);
      }
      didColumns = true;
      tb.addRow(row);
    } else {
      tb.addRow(row);
    }
  }
  return tb.build();
}

void showMappableTable(List<Mappable> rows) {
  showTable(rows.map((e) => e.toMap()).toList());
}

void showTable(List<Map<String, dynamic>> rows, {StringSink? sink}) {
  sink ??= stdout;
  sink.writeln("\n${buildTable(rows)}\n");
}

void showMap<T>(Map<String, T> map,
    {bool rightJustifyKeys = false, String? separator = ":", int lineFeedsBefore = 1, int lineFeedsAfter = 1, StringSink? sink}) {
  sink ??= stdout;
  var lb = LayoutBuilder(rightJustifyKeys: rightJustifyKeys, separator: separator);
  for (var entry in map.entries) {
    lb.add(entry.key, entry.value);
  }
  if (lineFeedsBefore > 0) {
    sink.write('\n' * lineFeedsBefore);
  }

  print(lb.toString());
  if (lineFeedsAfter > 0) {
    sink.write('\n' * lineFeedsAfter);
  }
}

List<String> splitInTwo(String text, Pattern delimiter) {
  var index = text.indexOf(delimiter);
  if (index > 1) {
    var key = text.substring(0, index).trim();
    var value = text.substring(index + 1).trim();
    return [key, value];
  }
  return [text];
}

String explodeMap(Map<String, dynamic> map, {int indent = 0, bool sort = false}) {
  var lb = LayoutBuilder();
  dynamic keys;
  if (sort) {
    keys = map.keys.toList();
    keys.sort();
  } else {
    keys = map.keys;
  }
  for (var key in keys) {
    lb.add(key, map[key] ?? "");
  }
  return lb.toString(indentCount: indent, indentChars: ' ');
}

String uuid() {
  return Uuid().v4();
}

bool promptYes(String prompt, {int? exitCode}) {
  if (!prompt.contains("?")) {
    prompt += " (Yes)? ";
  } else if (!prompt.endsWith(" ")) {
    prompt += " ";
  }
  for (;;) {
    stderr.write(prompt);
    var input = stdin.readLineSync();
    if (input == null || input.isEmpty) {
      continue;
    }
    if (input.toLowerCase() == "yes") {
      stderr.writeln();
      return true;
    }
    if (exitCode != null) {
      stderr.writeln();
      exit(exitCode);
    }
    return false;
  }
}

///
/// Used to report a fatal error, and exit if [exitMode] is true
///
Exception fatalError(String message) {
  message += '\n';
  if (exitMode) {
    stderr.writeln(message);
    exit(2);
  }
  throw StateError(message);
}

class MemoizedSupplier<T> {
  T Function()? _supplier;

  bool _valueSet = false;

  late T _value;

  MemoizedSupplier(T Function() supplier) : _supplier = supplier;

  T get value {
    if (!_valueSet) {
      _value = _supplier!();
      _supplier = null;
      _valueSet = true;
    }
    return _value;
  }
}

Map<K, V> toMap<K, V>(Iterable<V> list, K Function(V) keyGetter) {
  var map = <K, V>{};
  for (var l in list) {
    var key = keyGetter(l);
    if (map.containsKey(key)) {
      throw StateError("Duplicate key $key");
    }
    map[key] = l;
  }
  return map;
}

bool xor(List<dynamic> argList) {
  var oneSet = false;
  for (var arg in argList) {
    if (arg != null && arg.isNotEmpty) {
      if (oneSet) {
        return false;
      }
      oneSet = true;
    }
  }
  return oneSet;
}

void assertXor(List<dynamic> argList, String message) {
  if (!xor(argList)) {
    fatalError(message);
  }
}

T? ifNotNull<T>(dynamic thing, T Function(dynamic) caller) {
  if (thing != null) {
    return caller(thing);
  }
  return null;
}

List<T>? castListIfNotNull<T>(List<dynamic>? inputList) {
  if (inputList == null) {
    return null;
  }
  return List.castFrom(inputList);
}

bool isNullOrEmpty(dynamic value) {
  return value == null || value.isEmpty;
}

List<String>? splitAndTrimIfNotNull(String? values, {String delimiter = ","}) {
  return values == null ? null : splitAndTrim(values, delimiter: delimiter);
}

List<String> splitAndTrim(String values, {String delimiter = ","}) {
  return values.split(delimiter).map((e) => e.trim()).toList();
}

List<String> splitAndTrimAndDeDup(String values, {String delimiter = ",", bool sort = false}) {
  var list = values.split(delimiter).map((e) => e.trim()).toSet().toList();
  if (sort && list.isNotEmpty) {
    list.sort();
  }
  return list;
}

String sortAndJoin(Iterable<String> collection, {String delimiter = ","}) {
  var list = collection.toList();
  list.sort();
  return list.join(delimiter);
}

String? sortAndJoinAndDeDup(Iterable<String>? collection, {String delimiter = ","}) {
  if (collection == null) {
    return null;
  }
  var list = collection.toSet().toList();
  list.sort();
  return list.join(delimiter);
}

int parseInt(String value, String parameter, {int? minValue}) {
  var v = int.tryParse(value);
  if (v == null) {
    throw fatalError("$parameter: $value is not a valid integer.");
  }
  if (minValue != null && v < minValue) {
    throw fatalError("$parameter value of $value is invalid; cannot be less than $minValue.");
  }
  return v;
}

String toPrettyJson(Map<String, dynamic> map) {
  return JsonEncoder.withIndent('  ').convert(map);
}
