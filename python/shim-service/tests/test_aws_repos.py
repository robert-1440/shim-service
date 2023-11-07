from aws.dynamodb import DynamoDb
from better_test_case import BetterTestCase
from botomocks.dynamodb_mock import MockDynamoDbClient
from events import Event
from events.event_types import EventType
from repos.aws.aws_events import AwsEventsRepo
from repos.aws.aws_user_sessions import AwsUserSessionsRepo
from session import UserSession


class RepoTest(BetterTestCase):
    ddb_mock: MockDynamoDbClient
    ddb: DynamoDb

    def test_user_sessions(self):
        repo = AwsUserSessionsRepo(self.ddb)
        user_session = UserSession(
            199,
            'user-id',
            'session-id',
            'device-token',
            999999
        )

        self.assertTrue(repo.create(user_session))
        found = repo.find(user_session.tenant_id, user_session.user_id)
        self.assertEqual(user_session, found)

    def test_events(self):
        repo = AwsEventsRepo(self.ddb, None)

        event = Event(
            tenant_id=1,
            seq_no=1,
            event_type=EventType.SESSION_CREATED,
            event_id='event1',
            data={'one': 1}
        )
        self.assertTrue(repo.create(event))

        ev = repo.find(1, 1)
        self.assertEqual(event, ev)

        event2 = Event(
            tenant_id=1,
            seq_no=2,
            event_type=EventType.SESSION_CREATED,
            event_id='event1',
            data={'one': 1}
        )

        self.assertTrue(repo.create(event2))

        result = repo.query_events(1, 1)
        self.assertEqual([event], result.rows)

    def test_query_events(self):
        repo = AwsEventsRepo(self.ddb, None)

        def add_event(seq_no: int):
            event = Event(
                tenant_id=1,
                seq_no=seq_no,
                event_type=EventType.SESSION_CREATED,
                event_id=f'event-{seq_no}',
                data={'seq': seq_no}
            )
            self.assertTrue(repo.create(event))
            return event

        all_events = list(map(add_event, range(1, 1001)))

        collected = []
        last_key = None
        while True:
            result = repo.query_events(1, 100, last_evaluated_key=last_key)
            collected.extend(result.rows)
            last_key = result.next_token
            if last_key is None:
                break

        self.assertEqual(all_events, collected)

        # Now try all sequence numbers > 500
        collected = []
        last_key = None
        while True:
            result = repo.query_events(1, 100, last_seq_no=500, last_evaluated_key=last_key)
            collected.extend(result.rows)
            last_key = result.next_token
            if last_key is None:
                break
        self.assertHasLength(500, collected)

    def setUp(self):
        self.ddb_mock = ddb_mock = MockDynamoDbClient()
        ddb_mock.add_manual_table_v2("ShimServiceEvent", {'tenantId': 'N'}, {'seqNo': 'N'})
        ddb_mock.add_manual_table_v2("ShimServiceVirtualRangeTable", {'hashKey': 'S'},
                                     {'rangeKey': 'S'})
        self.ddb = DynamoDb(ddb_mock)
