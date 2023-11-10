import 'dart:io';

import 'package:cli/src/cli/processor.dart';

late DateTime targetTime;

late File targetFile;

void process(String path, [String ext = ".dart"]) {
  Directory dir = Directory(path);
  var list = dir.listSync(recursive: true);
  for (var entry in list) {
    if (entry is File && entry.path.endsWith(ext)) {
      checkFile(entry);
    }
  }
}

void checkFileName(String fileName) {
  File f = File(fileName);
  if (f.existsSync()) {
    checkFile(f);
  }
}

void checkFile(File entry) {
  var time = entry.lastModifiedSync();
  if (time.isAfter(targetTime)) {
    print("${entry.path} has been modified.");
    setTime();
  }
}

void setTime() {
  targetFile.setLastModifiedSync(DateTime.now());
  exit(0);
}



void main(List<String> arguments) {
  var cli = CommandLineProcessor(arguments, usage: "target-file");
  var targetFileName = cli.next("target-file");
  cli.assertNoMore();

  targetFile = File(targetFileName);
  if (!targetFile.existsSync()) {
    targetFile.createSync();
    exit(0);
  }
  targetTime = targetFile.lastModifiedSync();
  process("lib");
  process("bin");
}
