import 'dart:io';

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
