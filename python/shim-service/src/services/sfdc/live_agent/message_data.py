import json
from typing import Dict, Any, List, Optional

MESSAGE_TYPE_LIVE_AGENT_KIT_SHUTDOWN = "LiveAgentKitShutdown"


class Message:
    message_text: str
    message_record: Optional[Dict[str, Any]]

    def __init__(self, message_type: str, message: Any):
        self.type = message_type
        if type(message) is dict:
            self.message_record = message
            self.message_text = json.dumps(message)
        else:
            self.message_text = message
            self.message_record = None

    @classmethod
    def from_record(cls, record: Dict[str, Any]) -> 'Message':
        return cls(message_type=record['type'], message=record['message'])

    def to_record(self) -> Dict[str, Any]:
        return {
            'type': self.type,
            'message': self.message_record if self.message_record is not None else self.message_text
        }

    def __eq__(self, other):
        if isinstance(other, Message):
            return (self.type == other.type and
                    self.message_text == other.message_text and
                    self.message_record == other.message_record)
        return False

    def __hash__(self):
        return hash(self.type) ^ hash(self.message_text)


class MessageData:
    def __init__(self, messages: List[Message], sequence: int, offset: Optional[int]):
        self.messages = messages
        self.sequence = sequence
        self.offset = offset

    def is_shutdown_message(self):
        return len(self.messages) == 1 and self.messages[0].type == MESSAGE_TYPE_LIVE_AGENT_KIT_SHUTDOWN

    def matches_ack(self, ack: int):
        return ack + len(self.messages) == self.sequence

    @classmethod
    def from_record(cls, record: Dict[str, Any]) -> 'MessageData':
        messages_from_json = record['messages']
        messages_list = [Message.from_record(i) for i in messages_from_json]
        sequence = record['sequence']
        offset = record.get('offset')
        return cls(messages=messages_list, sequence=sequence, offset=offset)

    def to_record(self) -> Dict[str, Any]:
        record = {
            'messages': [m.to_record() for m in self.messages],
            'sequence': self.sequence
        }
        if self.offset is not None:
            record['offset'] = self.offset
        return record

    @classmethod
    def create_live_agent_kit_shutdown_data(cls, sequence: int):
        return MessageData([
            Message(
                message_type=MESSAGE_TYPE_LIVE_AGENT_KIT_SHUTDOWN,
                message={'content': 'LiveAgentKit timeout'}
            )
        ], sequence,
            None)
