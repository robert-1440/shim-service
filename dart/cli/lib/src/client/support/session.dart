import 'package:cli/src/cli/util.dart';
import 'package:cli/src/client/_init.dart';
import 'package:cli/src/client/support/channel.dart';
import 'package:cli/src/client/support/presence.dart';


class StartSessionRequest extends Mappable {
  final String orgId;

  final String userId;

  final String instanceUrl;

  final String fcmDeviceToken;

  final String accessToken;

  final List<ChannelPlatformType> channelPlatformTypes;

  StartSessionRequest(this.orgId, this.userId, this.instanceUrl, this.fcmDeviceToken, this.accessToken, this.channelPlatformTypes) {
    if (channelPlatformTypes.isEmpty) {
      throw ArgumentError("channelPlatformTypes must not be empty");
    }
  }

  @override
  Map<String, dynamic> toMap() {
    return {
      'userId': userId,
      'instanceUrl': instanceUrl,
      'fcmDeviceToken': fcmDeviceToken,
      'accessToken': accessToken,
      'channelPlatformTypes': channelPlatformTypes.map((type) => type.name).toList(),
    };
  }
}

class StartSessionResponse {
  final bool newSession;

  final bool pending;

  final String sessionToken;

  final DateTime expirationTime;

  final List<PresenceStatus> presenceStatuses;

  StartSessionResponse(this.newSession,this.pending, this.sessionToken, this.expirationTime, this.presenceStatuses);

  static StartSessionResponse fromMap(bool newSession, bool pending, Map<String, dynamic> map) {
    return StartSessionResponse(newSession, pending, map['sessionToken'], DateTime.fromMillisecondsSinceEpoch(map['expirationTime'] * 1000),
        PresenceStatus.listFromNode(map['presenceStatuses']));
  }
}

class KeepAliveResponse {
  final DateTime expirationTime;

  KeepAliveResponse(this.expirationTime);

  static KeepAliveResponse fromMap(Map<String, dynamic> map) {
    return KeepAliveResponse(DateTime.fromMillisecondsSinceEpoch(map['expirationTime'] * 1000));
  }
}
