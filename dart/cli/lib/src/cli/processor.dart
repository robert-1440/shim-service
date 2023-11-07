import 'dart:collection';
import 'dart:io';

import '../cli/mapper.dart';
import '../cli/util.dart';

bool exitMode = true;

class PropertySet {
  final Map<String, String> _source;

  final void Function([String?]) _usageFunc;

  PropertySet._$(this._source, this._usageFunc);

  bool get isEmpty => _source.isEmpty;

  String getRequired(String key, {bool trim = true, bool emptyOk = false}) {
    var v = _source[key];
    if (v == null) {
      _usageFunc("$key is required.");
      // Note that we should not get here.
      throw StateError("Failed");
    }
    if (trim) {
      v = v.trim();
    }
    if (!emptyOk && v.isEmpty) {
      _usageFunc("$key cannot be empty.");
      // Note that we should not get here.
      throw StateError("Failed");
    }
    return v;
  }

  List<String>? getCsv(String key, {bool trim = true}) {
    var v = _source[key];
    if (v == null) {
      return null;
    }
    return splitAndTrim(v);
  }

  int getRequiredInt(String key) {
    var v = getRequired(key);
    try {
      return int.parse(v);
    } catch (e) {
      throw StateError(("$key: '$v' is not a valid integer."));
    }
  }

  Map<String, String> toMap() {
    var map = <String, String>{};
    map.addAll(_source);
    return map;
  }

  String? operator [](String key) {
    return _source[key];
  }
}

class CommandLineProcessor {
  final List<String> _arguments;

  dynamic _usage;

  final bool _exitMode;

  final Map<String, dynamic> _properties = {};

  int _index = 0;

  ///
  /// Constructs a new processor.<p>
  /// [args] => command line arguments.
  /// [usage] => optional usage function that returns text, or text to display when there are errors.
  /// [exitMode] => set to false when testing.
  CommandLineProcessor(List<String> args, {dynamic usage, bool? exitMode})
      : _usage = usage,
        _arguments = List.of(args),
        _exitMode = exitMode ?? true;

  ///
  /// Used to set a user property.<p>
  /// [key] => name of the property.<p>
  /// [value] => value<p>
  /// [returns] => the previous property setting.
  ///
  dynamic setProperty(String key, dynamic value) {
    var current = _properties[key];
    _properties[key] = value;
    return current;
  }

  operator []=(String key, dynamic value) {
    setProperty(key, value);
  }

  operator [](String key) {
    return getProperty(key);
  }

  bool isExitMode() => _exitMode;

  ///
  /// Used to get a property set by [setProperty].<p>
  /// [key] => name of the property.<p>
  /// [returns] => the property value (null if it does not exist).
  ///
  dynamic getProperty(String key) {
    return _properties[key];
  }

  ///
  /// [returns] Whether there are more arguments.
  ///
  bool hasMore() {
    return _index < _arguments.length;
  }

  ///
  /// Sets a new usage function or text.
  ///
  void setUsage(dynamic usage) {
    _usage = usage;
  }

  ///
  /// [returns] true if the given optional argument is specified.  It is also removed from the argument list.<br>
  ///
  bool hasOptionalArg(String name) {
    for (int i = _index; i < _arguments.length; i++) {
      if (_arguments[i] == name) {
        _arguments.removeAt(i);
        return true;
      }
    }
    return false;
  }

  String? findOptionalArgPlusOne(String name) {
    var result = findOptionalArgs(name);
    return result == null ? null : result[0];
  }

  int? findOptionalArgPlusOneInt(String name) {
    var result = findOptionalArgs(name);
    if (result == null) {
      return null;
    }
    int? v = int.tryParse(result[0]);
    if (v != null) {
      return v;
    }
    fatalError("$name: '${result[0]}' is not a valid integer.");
    throw StateError("Not good");
  }

  ///
  /// Used to find optional arguments, such as <code>--print hello</code>.<p>
  /// [name] => the name of the argument to look for (i.e. --print)<p>
  /// [extraArgCount] => number of arguments to return after the given name (in this case [['hello']] would be returned).<p>
  ///
  List<String>? findOptionalArgs(String name, [int extraArgCount = 1]) {
    for (int i = _index; i < _arguments.length; i++) {
      if (_arguments[i] == name) {
        if (i < _arguments.length - extraArgCount) {
          var returnArgs = _arguments.sublist(i + 1, i + 1 + extraArgCount);
          for (int x = 0; x <= extraArgCount; x++) {
            _arguments.removeAt(i);
          }
          return returnArgs;
        } else {
          invokeUsage();
        }
      }
    }
    return null;
  }

  ///
  /// Returns the next argument.<p>
  /// [argName] => optional argument name to be printed if there are no more arguments.
  ///
  String next([String? argName]) {
    if (!hasMore()) {
      argName ??= "argument";
      invokeUsage("Expected $argName to be passed to the command line.");
    }
    var arg = _arguments[_index++];
    if (arg.startsWith("-")) {
      _index--;
      if (arg == "-h") {
        invokeUsage();
      } else {
        invokeUsage("Unexpected command line switch: $arg");
      }
    }
    return arg;
  }

  ///
  /// Returns the next argument as an int.<p>
  /// [argName] => optional argument name to be printed if there are no more arguments.
  ///
  int nextInt([String? argName]) {
    var v = next(argName);
    try {
      return int.parse(v);
    } catch (e) {
      invokeUsage("$v is not a valid integer.");
      exit(2);
    }
  }

  ///
  /// If the next argument matches the given name, return true and increment the argument position.
  ///
  /// [name] name to match.
  /// returns true if it matched.
  ///
  bool nextMatches(String name) {
    if (hasMore() && peekNext() == name) {
      _index++;
      return true;
    }
    return false;
  }

  ///
  /// Peek the next argument.  Returns null if there are no more.
  ///
  String? peekNext() {
    if (hasMore()) {
      return _arguments[_index];
    }
    return null;
  }

  ///
  /// Ensure there are no more arguments, otherwise invoke usage.
  ///
  void assertNoMore() {
    if (hasMore()) {
      invokeUsage("Unrecognized command line argument: ${peekNext()}");
    }
  }

  ///
  /// Ensure there are more arguments, otherwise invoke usage.
  ///
  void assertHasMore() {
    if (!hasMore()) {
      invokeUsage();
    }
  }

  ///
  /// Constructs the usage string.<p>
  /// [message] additional message to include before the usage<p>
  /// Returns the usage string.
  String getUsage([String? message]) {
    String outputMessage = "";

    if (message != null) {
      outputMessage += '\n>> $message\n\n';
    }
    if (_usage != null) {
      if (_usage is Function) {
        outputMessage += "${_usage()}";
      } else {
        outputMessage += '$_usage';
      }
    }
    return outputMessage;
  }

  ///
  /// Invoke the usage for this processor and exit (or throw if [exitMode] is false).
  ///
  void invokeUsage([String? message]) {
    _exit(getUsage(message));
  }

  PropertySet getPropertySet(Iterable<String> validProperties) {
    var propMap = SplayTreeMap<String, String>();
    for (var key in validProperties) {
      propMap[key.toLowerCase()] = key;
    }

    var set = toTreeSet(validProperties);
    Map<String, String> map = {};
    while (hasMore()) {
      var entry = next();
      var values = splitInTwo(entry, "=");
      if (values.length == 2) {
        var key = values[0];
        var value = values[1];
        if (key.isNotEmpty) {
          var lowerKey = key.toLowerCase();
          var actualKey = propMap[lowerKey];
          if (actualKey != null) {
            map[actualKey] = value;
            continue;
          }
          invokeUsage("Invalid argument: $entry. Must be one of $set");
        }
      }
      invokeUsage("Invalid command-line argument: $entry. Expecting key=value.");
    }
    return PropertySet._$(map, invokeUsage);
  }

  void _exit(String outputMessage) {
    if (outputMessage.isNotEmpty && _exitMode) {
      stderr.writeln(outputMessage);
    }
    if (_exitMode) {
      exit(2);
    }
    throw ArgumentError(outputMessage);
  }
}

String getOurExecutableName() {
  return Platform.executable.split(Platform.pathSeparator).last;
}
