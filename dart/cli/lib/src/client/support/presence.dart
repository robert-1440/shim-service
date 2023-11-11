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

  bool get isOnline => statusOption == StatusOption.online;

  bool get isBusy => statusOption == StatusOption.busy;

  bool get isOffline => statusOption == StatusOption.offline;

  @override
  String toString() {
    return "$label = ${statusOption.name} (id=$id)";
  }

  static List<PresenceStatus> listFromNode(List<dynamic>? list) {
    if (list == null) {
      return [];
    }
    return list.map((e) => fromMap(e)).toList();
  }

  static PresenceStatus fromMap(Map<String, dynamic> map) {
    return PresenceStatus(map['id'], map['label'], StatusOption.valueOf(map['statusOption']));
  }
}
