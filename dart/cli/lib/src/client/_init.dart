import 'dart:io';

import 'package:cli/src/cli/processor.dart';
import 'package:cli/src/client/manager.dart';

import 'profile.dart';

final f40ParentFolder = Directory("${getHomePath()}/.1440/configuration-service");

File getHomeFile(String file) {
  return File("${f40ParentFolder.path}${Platform.pathSeparator}$file");
}

abstract class DataFormatter {
  void format(List<Map<String, dynamic>> rows, StringSink sink);

  void formatSingle(Map<String, dynamic> data, StringSink sink);

  bool isDefault() => false;
}

class ShimException {
  final String message;

  ShimException(this.message);
}

final _clientManagerKey = ".cm";

final profileKey = "profile";

ClientManager getClientManager(CommandLineProcessor cli) {
  var prop = cli.getProperty(_clientManagerKey);
  if (prop == null) {
    String profileName = getProfileName(cli);
    prop = ClientManager(loadProfile(profileName));
    cli.setProperty(_clientManagerKey, prop);
  }
  return prop as ClientManager;
}

Profile getProfile(CommandLineProcessor cli) {
  return getClientManager(cli).profile;
}

String getProfileName(CommandLineProcessor cli) {
  return cli.getProperty(profileKey);
}
