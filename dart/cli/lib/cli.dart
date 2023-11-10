import 'dart:io';

import 'package:cli/src/cli/cli.dart';
import 'package:cli/src/cli/processor.dart';
import 'package:cli/src/client/_init.dart';
import 'package:cli/src/modules/main.dart';

final _modules = [MainModule()];

class MyApp extends App {
  @override
  String usage() {
    return "[--profile profile] shim-test <command>";
  }

  String determineProfile() {
    var p = Platform.environment["SHIM_TEST_PROFILE"];
    if (p != null) {
      stderr.writeln("Test profile is $p.");
      return p;
    }
    return "default";
  }

  @override
  List<Module> modules() {
    return _modules;
  }

  @override
  void setup(CommandLineProcessor processor) {
    var profile = processor.findOptionalArgPlusOne("--profile") ?? determineProfile();
    processor.assertHasMore();
    processor[profileKey] = profile;
  }
}

void execute(List<String> args) {
  args = ["main", ...args];
  init(args, MyApp());
}
