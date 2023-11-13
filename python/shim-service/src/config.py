# Minutes before expiring a session
# We expect a keep alive request in order to prevent expiration
DEFAULT_SESSION_MINUTES = 18

# Number of seconds before a worker session is considered orphaned
DEFAULT_WORKER_TIMEOUT_SECONDS = 30

# Max number of retries when creating a session
DEFAULT_MAX_SESSION_RETRIES = 10

# Default poller time allowed
# Keep it under 900 since that is the max time a Lambda instance can run
#
DEFAULT_MAX_POLLING_SECONDS = 890

#
# Default idle time before re-scheduling a polling session
#
DEFAULT_IDLE_POLLING_SECONDS = 300

#
# Number of sessions a single lambda instance can support for polling live agent
#
DEFAULT_SESSIONS_PER_LA_POLL_PROCESSOR = 20

#
# Max seconds we expect a poll to take for live agent
#
DEFAULT_LA_POLL_SESSION_TIME = 60

#
# Max seconds a work id map record should live
#
DEFAULT_MAX_WORK_ID_MAP_SECONDS = 3600 * 24 * 10


class Config:
    """
    Contains various global configuration values.
    """

    def __init__(self,
                 session_expiration_seconds: int = DEFAULT_SESSION_MINUTES * 60,
                 worker_timeout_seconds: int = DEFAULT_WORKER_TIMEOUT_SECONDS,
                 max_create_session_retries: int = DEFAULT_MAX_SESSION_RETRIES,
                 max_polling_seconds: int = DEFAULT_MAX_POLLING_SECONDS,
                 idle_polling_seconds: int = DEFAULT_IDLE_POLLING_SECONDS,
                 sessions_per_live_agent_poll_processor=DEFAULT_SESSIONS_PER_LA_POLL_PROCESSOR,
                 live_agent_poll_session_seconds=DEFAULT_LA_POLL_SESSION_TIME,
                 max_work_id_map_seconds=DEFAULT_MAX_WORK_ID_MAP_SECONDS
                 ):
        self.session_expiration_seconds = session_expiration_seconds
        self.worker_timeout_seconds = worker_timeout_seconds
        self.max_create_session_retries = max_create_session_retries
        self.max_polling_seconds = max_polling_seconds
        self.idle_polling_seconds = idle_polling_seconds
        self.sessions_per_live_agent_poll_processor = sessions_per_live_agent_poll_processor
        self.live_agent_poll_session_seconds = live_agent_poll_session_seconds
        self.max_work_id_map_seconds = max_work_id_map_seconds
