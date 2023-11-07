import 'dart:convert';
import 'dart:typed_data';

class DataInputBuffer {
  final ByteData _data;

  final List<int> _bytes;

  DataInputBuffer(this._bytes) : _data = ByteData.sublistView(Int8List.fromList(_bytes));

  int _offset = 0;

  int readInt() {
    int v = _data.getInt32(_offset);
    _offset += 4;
    return v;
  }

  int readByte() {
    var v = _data.getUint8(_offset);
    _offset++;
    return v;
  }

  int readSize([bool zeroOk = true]) {
    int size = readInt();
    if (size < 0 || (size == 0 && !zeroOk)) {
      throw RangeError.value(size);
    }
    return size;
  }

  List<int> readBytes([int? size]) {
    size ??= readSize();

    if (size < 1) {
      if (size == 0) {
        return List.empty(growable: false);
      }
      throw RangeError.value(size);
    }
    var v = _bytes.sublist(_offset, _offset + size);
    _offset += size;
    return v;
  }

  String readString() {
    var bytes = readBytes();
    return utf8.decode(bytes);
  }
}

class DataOutputBuffer {
  final BytesBuilder _builder = BytesBuilder();

  int get length => _builder.length;

  void writeInt(int value) {
    _setInt(value);
  }

  void writeString(String value) {
    var encoded = utf8.encode(value);
    writeInt(encoded.length);
    _builder.add(encoded);
  }

  void writeByte(int value) {
    _builder.addByte(value);
  }

  void writeBytes(List<int> bytes, [bool includeSize = true]) {
    if (includeSize) {
      writeInt(bytes.length);
    }
    _builder.add(bytes);
  }

  void _setInt(int v, [int size = 4]) {
    int shift = ((size - 1) * 8);

    for (var i = 0; i < size; i++, shift -= 8) {
      _builder.addByte((v >> shift & 0xff));
    }
  }

  Uint8List toByteArray() {
    return _builder.toBytes();
  }
}

