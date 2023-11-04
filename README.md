# Shim Service

The Shim Service is service that transparently intercepts API calls and transforms the arguments passed to
interface with 3rd part routing and messaging platforms such as Salesforce (immediate term) and Amazon Connect (longer
term). Clients of the Shim Service will include the 1440 mobile app and 1440 Lightning Web Components (LWCs) designed to
run in the Salesforce mobile app and the Field Service mobile app. The service should enable these clients to login to
Salesforce Omni, set the user presence status, accept/decline/transfer/end Omni work items, as well as send/receive text
messages and images.

# Infrastructure

We are going to attempt to deploy the service as a series of AWS Lambda functions.

* [shim-service](python/shim-service)
    * Represents the web tier
* shim-live-agent-poller
    * Polls SFDC LiveAgent for events
    * There will be an invocation for each user session
* shim-sfdc-pubsub
    * There will be an invocation for each org

For the worker lambda functions, since they are long-running, we will invoke the function again as time is running out (
around the 14.5 minute mark)




