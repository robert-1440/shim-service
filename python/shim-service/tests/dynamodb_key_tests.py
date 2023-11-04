from repos.aws.aws_tenants import AwsTenantsRepo
from repos.tenants import TenantConfiguration

from aws.dynamodb import DynamoDb
from aws.dynamodb_keys import CompositeKeyPart, Key, CompoundKey, CompositeKey
from better_test_case import BetterTestCase
from botomocks.dynamodb_mock import MockDynamoDbClient, KeyDefinition, KeyPart


class DynamoDbRepoTests(BetterTestCase):

    def test_key_parts(self):
        part = CompositeKeyPart('tenantId', (int, 10))
        self.assertEqual("0000000100", part.build(100))

        part = CompositeKeyPart('tenantId', int)
        self.assertEqual("100", part.build(100))

        part = CompositeKeyPart('externalId', str)
        self.assertEqual("external", part.build('external'))

        part = CompositeKeyPart('externalId', (str, 10))
        self.assertEqual("external~~", part.build('external'))

    def test_simple_keys(self):
        hash_key = Key('hashKey')
        item = {'hashKey': 'MyKey'}
        keys = {}
        hash_key.populate_key(item, keys, False)
        self.assertEqual('MyKey', keys['hashKey'])
        self.assertEqual('MyKey', item['hashKey'])

        # Remove parameter is ignored for simple keys
        hash_key.populate_key(item, keys, True)
        self.assertEqual('MyKey', keys['hashKey'])
        self.assertEqual('MyKey', item['hashKey'])

        # Test serialization .. nothing should be done
        compound_key = CompoundKey(hash_key)

        item = {'hashKey': 'MyKey', 'other': 1}
        compound_key.prep_for_serialization(item)
        self.assertEqual({'hashKey': 'MyKey', 'other': 1}, item)

        # Same with deserialization
        compound_key.prep_for_deserialization(item)
        self.assertEqual({'hashKey': 'MyKey', 'other': 1}, item)

        item = {'hashKey': 'MyKey', 'rangeKey': 'RangeKey', 'other': 1}
        full_key = compound_key.build_key_as_dict(item)
        self.assertEqual({'hashKey': 'MyKey'}, full_key)
        self.assertEqual({'hashKey': 'NewKey'}, compound_key.build_key_from_args('NewKey')[0])

        range_key = Key('rangeKey')
        compound_key = CompoundKey(hash_key, range_key)

        full_key = compound_key.build_key_as_dict(item)
        self.assertEqual({'hashKey': 'MyKey', 'rangeKey': 'RangeKey'}, full_key)

        self.assertEqual({'hashKey': 'NewKey', 'rangeKey': 'NewRange'},
                         compound_key.build_key_from_args('NewKey', 'NewRange')[0])

    def test_composite_keys(self):
        item = {
            'tenantId': 1,
            'recordType': 'A',
            'eventId': '912312',
            'seqNo': 100,
            'data': "This is some data."

        }
        save_item = item.copy()

        ck_hash = CompositeKey('hashKey',
                               {
                                   'recordType': str,
                                   'tenantId': int
                               })
        ck_range = CompositeKey('rangeKey',
                                {
                                    'eventId': str,
                                    'seqNo': (int, 10)
                                })
        hash_key = Key(key=ck_hash)
        range_key = Key(key=ck_range)

        primary_key = CompoundKey(hash_key, range_key)

        result = primary_key.build_key_as_dict(item)
        self.assertEqual({'hashKey': 'A:1', 'rangeKey': '912312:0000000100'}, result)

        primary_key.prep_for_serialization(item)
        self.assertEqual({'data': 'This is some data.', 'hashKey': 'A:1', 'rangeKey': '912312:0000000100'},
                         item)

        primary_key.prep_for_deserialization(item)
        self.assertEqual(save_item, item)

    def test_tenant_repo(self):
        mock = MockDynamoDbClient()
        ddb = DynamoDb(mock)
        repo = AwsTenantsRepo(ddb)
        config = TenantConfiguration(
            True,
            True,
            'endpoint',
            'consumer-key',
            'consumer-secret'
        )
        mock.add_manual_table("ShimServiceTenant",
                              KeyDefinition([KeyPart('tenantId', 'N')]))

        repo.replace_tenant(900, config)

        self.assertEqual(config, repo.find_tenant(900))
