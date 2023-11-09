

import 'package:cli/src/xml_util.dart';
import 'package:xml/xml.dart';

import 'utils_for_tests.dart';

class XmlSuite {

  @Test("Basic")
  void basic() {
    var xmlText = "<root><name>Frank</name></root>";
    var doc = XmlDocument.parse(xmlText);
    assertThat(findChildString(doc.rootElement, "name")).isEqualTo("Frank");
  }
}

void main() {
  executeTestSuite(XmlSuite);
}