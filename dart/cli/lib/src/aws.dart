import 'package:aws_client/sqs_2012_11_05.dart';
import 'package:cli/src/client/_init.dart';
import 'package:cli/src/client/ini_parser.dart';
import 'package:cli/src/client/profile.dart' as p;

String getRegion(String profile) {
  var iniFile = loadIniFile(getRootHomeFile(".aws/config").path);
  var section = iniFile.getSection("profile $profile");
  return section.getRequired("region");
}

AwsClientCredentials getCredentials(String profile) {
  var iniFile = loadIniFile(getRootHomeFile(".aws/credentials").path);
  var section = iniFile.getSection(profile);
  return AwsClientCredentials(
      accessKey: section.getRequired("aws_access_key_id"), secretKey: section.getRequired("aws_secret_access_key"));
}

Sqs getSqs(p.Profile profile) {
  return Sqs(region: getRegion(profile.awsProfile), credentials: getCredentials(profile.awsProfile));
}
