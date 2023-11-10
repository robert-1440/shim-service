import 'package:cli/src/cli/util.dart';

enum StatusOption {
  online,
  busy,
  offline;

  static StatusOption valueOf(String value) {
    switch (value) {
      case 'online':
        return StatusOption.online;
      case 'busy':
        return StatusOption.busy;
      case 'offline':
        return StatusOption.offline;
      default:
        throw ArgumentError('Unknown value: $value');
    }
  }
}

class PresenceStatus extends Mappable {
  final String id;

  final String label;

  final StatusOption statusOption;

  PresenceStatus(this.id, this.label, this.statusOption);

  @override
  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'label': label,
      'statusOption': statusOption.name,
    };
  }

  static PresenceStatus fromMap(Map<String, dynamic> map) {
    return PresenceStatus(map['id'], map['label'], StatusOption.valueOf(map['statusOption']));
  }
}
