import 'dart:async';

import 'package:aws_client/sqs_2012_11_05.dart';
import 'package:cli/src/aws.dart';
import 'package:cli/src/cli/util.dart';
import 'package:cli/src/client/profile.dart';
import 'package:cli/src/notification/base.dart';
import 'package:cli/src/state.dart';

const queueName = "mock-notification-queue.fifo";

Future<SessionState> poll(Profile profile, SessionState state) async {
  String user = getCurrentUser();
  var sqs = getSqs(profile);
  try {
    var queueUrl = await sqs.getQueueUrl(queueName: queueName);
    for (;;) {
      var result = await _pollQueue(user, sqs, queueUrl.queueUrl!, state);
      state = result.left;
      if (!result.right) {
        break;
      }
    }
  } finally {
    sqs.close();
  }

  return state;
}

const atts = [QueueAttributeName.all];

Future<Pair<SessionState, bool>> _pollQueue(String user, Sqs sqs, String queueUrl, SessionState state,
    {StreamController<Pair<SessionState, List<PushNotificationEvent>>>? stateChangeStream}) async {
  var response = await sqs.receiveMessage(queueUrl: queueUrl, attributeNames: atts, maxNumberOfMessages: 1, waitTimeSeconds: 0);
  if (response.messages == null || response.messages!.isEmpty) {
    return Pair.of(state, false);
  }
  var message = response.messages!.first;
  var groupId = message.attributes![MessageSystemAttributeName.messageGroupId];
  if (groupId == null || groupId != user) {
    await sqs.changeMessageVisibility(queueUrl: queueUrl, receiptHandle: message.receiptHandle!, visibilityTimeout: 10);
  } else {
    List<PushNotificationEvent> events = [];
    state = state.processMessage(message.body!, eventList: events);
    await sqs.deleteMessage(queueUrl: queueUrl, receiptHandle: message.receiptHandle!);
    if (stateChangeStream != null) {
      stateChangeStream.add(Pair.of(state, events));
    }
  }
  return Pair.of(state, true);
}

class Poller {
  final String user;

  final Sqs sqs;

  SessionState state;

  late StreamController<Pair<SessionState, List<PushNotificationEvent>>> _stateController;

  bool _end = false;

  void Function()? _endFunction;

  Poller(this.user, this.sqs, this.state) {
    _stateController = StreamController.broadcast();
  }

  Future<void> start() async {
    sqs.getQueueUrl(queueName: queueName).then((value) => _start(value.queueUrl!));
  }

  Future<void> _start(String url) async {
    _stateController.add(Pair.of(state, []));
    while(!_end) {
      var result = await _pollQueue(user, sqs, url, state, stateChangeStream: _stateController);
      state = result.left;
      if (!result.right) {
        await Future.delayed(Duration(seconds: 5));
      }
    }
    state = state.clearSession();
    state.save();
    if (_endFunction != null) {
      _endFunction!();
    }
  }

  Stream<Pair<SessionState, List<PushNotificationEvent>>> get stateStream => _stateController.stream;

  void close([void Function()? endFunction]) {
    _endFunction = endFunction;
    _end = true;
    _stateController.close();
  }
}
