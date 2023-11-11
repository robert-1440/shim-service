import 'package:aws_client/sqs_2012_11_05.dart';
import 'package:cli/src/aws.dart';
import 'package:cli/src/cli/util.dart';
import 'package:cli/src/client/profile.dart';
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

Future<Pair<SessionState, bool>> _pollQueue(String user, Sqs sqs, String queueUrl, SessionState state) async {
  var response = await sqs.receiveMessage(queueUrl: queueUrl, attributeNames: atts, maxNumberOfMessages: 1, waitTimeSeconds: 0);
  if (response.messages == null || response.messages!.isEmpty) {
    return Pair.of(state, false);
  }
  var message = response.messages!.first;
  var groupId = message.attributes![MessageSystemAttributeName.messageGroupId];
  if (groupId == null || groupId != user) {
    await sqs.changeMessageVisibility(queueUrl: queueUrl, receiptHandle: message.receiptHandle!, visibilityTimeout: 10);
  } else {
    state = state.processMessage(message.body!);
    await sqs.deleteMessage(queueUrl: queueUrl, receiptHandle: message.receiptHandle!);
  }
  return Pair.of(state, true);
}
