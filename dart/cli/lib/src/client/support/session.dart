import 'package:cli/src/cli/util.dart';
import 'package:cli/src/client/_init.dart';
import 'package:cli/src/client/support/channel.dart';
import 'package:cli/src/client/support/presence.dart';

class UserAlreadyLoggedInException extends ShimException {
  final String token;

  UserAlreadyLoggedInException(this.token) : super("User already logged in");
}

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

  final String sessionToken;

  final DateTime expirationTime;

  final List<PresenceStatus> presenceStatuses;

  StartSessionResponse(this.newSession, this.sessionToken, this.expirationTime, this.presenceStatuses);

  static StartSessionResponse fromMap(bool newSession, Map<String, dynamic> map) {
    return StartSessionResponse(newSession, map['sessionToken'], DateTime.fromMillisecondsSinceEpoch(map['expirationTime'] * 1000),
        map['presenceStatuses'].map((status) => PresenceStatus.fromMap(status)).toList());
  }
}

class KeepAliveResponse {
  final DateTime expirationTime;

  KeepAliveResponse(this.expirationTime);

  static KeepAliveResponse fromMap(Map<String, dynamic> map) {
    return KeepAliveResponse(DateTime.fromMillisecondsSinceEpoch(map['expirationTime'] * 1000));
  }
}
