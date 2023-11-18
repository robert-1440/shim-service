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
    {StreamController<PushNotificationEvent>? eventStream}) async {
  var response = await sqs.receiveMessage(queueUrl: queueUrl, attributeNames: atts, maxNumberOfMessages: 1, waitTimeSeconds: 0);
  if (response.messages == null || response.messages!.isEmpty) {
    return Pair.of(state, false);
  }
  var message = response.messages!.first;
  var groupId = message.attributes![MessageSystemAttributeName.messageGroupId];
  if (groupId == null || groupId != user) {
    await sqs.changeMessageVisibility(queueUrl: queueUrl, receiptHandle: message.receiptHandle!, visibilityTimeout: 10);
  } else {
    state = state.processMessage(message.body!, eventStream: eventStream);
    await sqs.deleteMessage(queueUrl: queueUrl, receiptHandle: message.receiptHandle!);
  }
  return Pair.of(state, true);
}

class Poller {
  final String user;

  final Sqs sqs;

  SessionState state;

  late StreamController<SessionState> _stateController;

  late StreamController<PushNotificationEvent> _eventController;

  Poller(this.user, this.sqs, this.state) {
    _stateController = StreamController.broadcast();
    _eventController = StreamController.broadcast();
  }

  Future<void> start() async {
    sqs.getQueueUrl(queueName: queueName).then((value) => _start(value.queueUrl!));
  }

  Future<void> _start(String url) async {
    _stateController.add(state);
    for (;;) {
      print("Checking for messages ...");
      var result = await _pollQueue(user, sqs, url, state, eventStream: _eventController);
      state = result.left;
      _stateController.add(state);
      if (!result.right) {
        await Future.delayed(Duration(seconds: 5));
      }
    }
  }

  Stream<SessionState> get stateStream => _stateController.stream;

  Stream<PushNotificationEvent> get eventStream => _eventController.stream;
}
