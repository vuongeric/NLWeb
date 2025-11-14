import datetime
import logging
import os

logger = logging.getLogger("credentials")
logger.setLevel(logging.DEBUG)

if os.getenv("ENVIRONMENT", "").lower() == "development":

    def get_refreshing_credentials():
        raise RuntimeError("Refreshing credentials not used in development.")

else:
    import boto3
    from botocore.credentials import RefreshableCredentials
    from botocore.session import get_session

    def refresh():
        logger.info("Refreshing AWS credentials via Boto3 session...")
        session = boto3.Session()
        creds = session.get_credentials()
        if creds is None:
            logger.error("No credentials found in Boto3 session.")
            raise RuntimeError("No AWS credentials available")
        frozen = creds.get_frozen_credentials()
        expiry_time = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=55)
        logger.debug("Fetched credentials. Expires at: %s", expiry_time.isoformat())
        return {
            "access_key": frozen.access_key,
            "secret_key": frozen.secret_key,
            "token": frozen.token,
            "expiry_time": expiry_time.isoformat()
        }

    _session = get_session()
    logger.info("Initializing RefreshableCredentials...")
    _refreshing_creds = RefreshableCredentials.create_from_metadata(
        metadata=refresh(),
        refresh_using=refresh,
        method="sts-assume-role"
    )
    _session._credentials = _refreshing_creds
    autorefresh_session = boto3.Session(botocore_session=_session)

    def get_refreshing_credentials():
        logger.debug("Returning auto-refreshing credentials...")
        return autorefresh_session.get_credentials()

