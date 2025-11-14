# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
AWS-specific OpenSearch client that reuses the base OpenSearch implementation.
"""

import base64
import os
from typing import Dict, Optional

from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
from urllib.parse import urljoin

from core.config import CONFIG
from misc.logger.logging_config_helper import get_configured_logger
from auth.opensearch_credentials import get_refreshing_credentials  # adjust path as needed
from .opensearch_client import OpenSearchClient

logger = get_configured_logger("opensearch_aws_client")


def sigv4_signed_headers(method, url, region, service, body=None):
    creds = get_refreshing_credentials().get_frozen_credentials()
    credentials = Credentials(
        access_key=creds.access_key,
        secret_key=creds.secret_key,
        token=creds.token
    )

    aws_request = AWSRequest(
        method=method.upper(),
        url=url,
        data=body or b"",
        headers={"Host": url.split('/')[2]}
    )
    SigV4Auth(credentials, service, region).add_auth(aws_request)
    return dict(aws_request.headers)


class OpenSearchAWSClient(OpenSearchClient):
    """
    AWS OpenSearch client that adds SigV4 auth on top of the standard client behaviour.
    """

    def _requires_credentials(self) -> bool:
        """SigV4 uses AWS credentials instead of API keys from config."""
        return False

    def _get_endpoint_config(self):
        endpoint_config = CONFIG.retrieval_endpoints.get(self.endpoint_name)

        if not endpoint_config:
            error_msg = f"No configuration found for endpoint {self.endpoint_name}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        if endpoint_config.db_type != "opensearch_aws":
            error_msg = f"Endpoint {self.endpoint_name} is not an AWS OpenSearch endpoint (type: {endpoint_config.db_type})"
            logger.error(error_msg)
            raise ValueError(error_msg)

        return endpoint_config

    def _get_auth_headers(self, method: str = "GET", path: str = "/", body: Optional[bytes] = None) -> Dict[str, str]:
        """
        Use SigV4 signing outside of development; fall back to API key/basic auth when available for local work.
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        if os.getenv("ENVIRONMENT", "").lower() == "development":
            if self.credentials:
                if ':' in self.credentials:
                    encoded_credentials = base64.b64encode(self.credentials.encode()).decode()
                    headers["Authorization"] = f"Basic {encoded_credentials}"
                else:
                    headers["Authorization"] = f"Bearer {self.credentials}"
            return headers

        region = getattr(self.endpoint_config, "region", "us-west-2")
        service = getattr(self.endpoint_config, "aws_service", "es")
        url = urljoin(self.api_endpoint + "/", path.lstrip("/"))
        signed = sigv4_signed_headers(method, url, region=region, service=service, body=body)
        headers.update(signed)
        return headers

