"""CKAN client for publishing datasets to CKAN instances."""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urljoin
import hashlib

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.logging_conf import get_logger
from src.settings import settings

logger = get_logger("ckan")


class CKANError(Exception):
    """Base exception for CKAN client errors."""
    pass


class CKANValidationError(CKANError):
    """Exception raised when CKAN API returns validation errors."""
    pass


class CKANClientError(CKANError):
    """Exception raised for client-side errors."""
    pass


class CKANServerError(CKANError):
    """Exception raised for server-side errors.""" 
    pass


class CKANClient:
    """CKAN API client with retry logic and error handling."""
    
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 1.0
    ):
        """Initialize CKAN client.
        
        Args:
            base_url: CKAN instance base URL
            api_key: API key for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
            backoff_factor: Backoff factor for retries
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        
        # Setup session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set default headers
        self.session.headers.update({
            'Authorization': api_key,
            'Content-Type': 'application/json',
            'User-Agent': 'ComplianceAutomationKit/1.0'
        })
        
        logger.info("CKAN client initialized", base_url=base_url)
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make authenticated request to CKAN API.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            data: JSON data payload
            files: Files to upload
            params: Query parameters
            
        Returns:
            API response data
            
        Raises:
            CKANError: For various API errors
        """
        url = urljoin(self.base_url, f'/api/3/action/{endpoint}')
        
        try:
            # Prepare request
            kwargs = {
                'timeout': self.timeout,
                'params': params
            }
            
            if files:
                # For file uploads, remove content-type header
                headers = self.session.headers.copy()
                if 'Content-Type' in headers:
                    del headers['Content-Type']
                kwargs['headers'] = headers
                kwargs['files'] = files
                if data:
                    kwargs['data'] = data
            elif data:
                kwargs['json'] = data
            
            logger.debug(f"CKAN API request", method=method, url=url)
            
            # Make request with retries
            response = self.session.request(method, url, **kwargs)
            
            # Log response
            logger.debug(
                f"CKAN API response",
                status_code=response.status_code,
                content_type=response.headers.get('content-type', '')
            )
            
            # Handle HTTP errors
            if response.status_code >= 400:
                if response.status_code < 500:
                    raise CKANClientError(
                        f"Client error {response.status_code}: {response.text}"
                    )
                else:
                    raise CKANServerError(
                        f"Server error {response.status_code}: {response.text}"
                    )
            
            # Parse JSON response
            try:
                response_data = response.json()
            except json.JSONDecodeError as e:
                raise CKANError(f"Invalid JSON response: {e}")
            
            # Check CKAN success status
            if not response_data.get('success', False):
                error_msg = response_data.get('error', {})
                if isinstance(error_msg, dict):
                    # Validation errors
                    if '__type' in error_msg and error_msg['__type'] == 'Validation Error':
                        raise CKANValidationError(f"Validation error: {error_msg}")
                    else:
                        raise CKANError(f"API error: {error_msg}")
                else:
                    raise CKANError(f"API error: {error_msg}")
            
            return response_data.get('result', {})
            
        except requests.exceptions.Timeout:
            raise CKANError(f"Request timeout after {self.timeout}s")
        except requests.exceptions.ConnectionError as e:
            raise CKANError(f"Connection error: {e}")
        except requests.exceptions.RequestException as e:
            raise CKANError(f"Request error: {e}")
    
    def get_package(self, package_id: str) -> Optional[Dict[str, Any]]:
        """Get package by ID or name.
        
        Args:
            package_id: Package ID or name
            
        Returns:
            Package data or None if not found
        """
        try:
            return self._make_request('GET', 'package_show', params={'id': package_id})
        except (CKANClientError, CKANError) as e:
            msg = str(e)
            if "Not Found" in msg or "Not found" in msg:
                return None
            raise
    
    def create_package(self, package_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new package.
        
        Args:
            package_data: Package metadata
            
        Returns:
            Created package data
        """
        logger.info("Creating CKAN package", name=package_data.get('name'))
        return self._make_request('POST', 'package_create', data=package_data)
    
    def update_package(self, package_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing package.
        
        Args:
            package_data: Package metadata
            
        Returns:
            Updated package data
        """
        logger.info("Updating CKAN package", id=package_data.get('id'))
        return self._make_request('POST', 'package_update', data=package_data)
    
    def get_resource(self, resource_id: str) -> Optional[Dict[str, Any]]:
        """Get resource by ID.
        
        Args:
            resource_id: Resource ID
            
        Returns:
            Resource data or None if not found
        """
        try:
            return self._make_request('GET', 'resource_show', params={'id': resource_id})
        except (CKANClientError, CKANError) as e:
            msg = str(e)
            if "Not Found" in msg or "Not found" in msg:
                return None
            raise
    
    def create_resource(self, resource_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new resource.
        
        Args:
            resource_data: Resource metadata
            
        Returns:
            Created resource data
        """
        logger.info("Creating CKAN resource", package_id=resource_data.get('package_id'))
        return self._make_request('POST', 'resource_create', data=resource_data)
    
    def update_resource(self, resource_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing resource.
        
        Args:
            resource_data: Resource metadata
            
        Returns:
            Updated resource data
        """
        logger.info("Updating CKAN resource", id=resource_data.get('id'))
        return self._make_request('POST', 'resource_update', data=resource_data)
    
    def upload_resource_file(
        self,
        resource_data: Dict[str, Any],
        file_path: Path
    ) -> Dict[str, Any]:
        """Upload a file for a resource.
        
        Args:
            resource_data: Resource metadata
            file_path: Path to file to upload
            
        Returns:
            Created/updated resource data
        """
        logger.info("Uploading file to CKAN resource", file=str(file_path))
        
        with open(file_path, 'rb') as f:
            files = {'upload': (file_path.name, f, 'application/octet-stream')}
            
            # Use resource_create or resource_update depending on whether ID is present
            if 'id' in resource_data:
                endpoint = 'resource_update'
            else:
                endpoint = 'resource_create'
                
            return self._make_request('POST', endpoint, data=resource_data, files=files)
    
    def test_connection(self) -> bool:
        """Test connection to CKAN instance.
        
        Returns:
            True if connection successful
        """
        try:
            result = self._make_request('GET', 'site_read')
            logger.info("CKAN connection test successful")
            return True
        except Exception as e:
            logger.error("CKAN connection test failed", error=str(e))
            return False


class CKANPublisher:
    """High-level publisher for datasets to CKAN."""
    
    def __init__(self, client: CKANClient):
        """Initialize publisher with CKAN client."""
        self.client = client
        self.logger = get_logger("ckan.publisher")
    
    def publish_dataset(
        self,
        dataset_metadata: Dict[str, Any],
        csv_file: Path,
        json_file: Path,
        metadata_file: Path,
        org_id: str,
        dataset_id: str
    ) -> Dict[str, Any]:
        """Publish a complete dataset to CKAN.
        
        Args:
            dataset_metadata: Dataset metadata
            csv_file: CSV data file
            json_file: JSON data file
            metadata_file: Metadata JSON file
            org_id: Organization ID
            dataset_id: Local dataset ID
            
        Returns:
            Publishing result with package and resource IDs
        """
        self.logger.info("Publishing dataset to CKAN", dataset_id=dataset_id, org_id=org_id)
        
        # Generate CKAN package name (must be lowercase, alphanumeric + dashes)
        package_name = self._generate_package_name(org_id, dataset_id)
        
        # Check if package exists
        existing_package = self.client.get_package(package_name)
        
        # Prepare package data
        package_data = self._prepare_package_data(
            dataset_metadata, package_name, org_id, existing_package
        )
        
        # Create or update package
        if existing_package:
            package_data['id'] = existing_package['id']
            package = self.client.update_package(package_data)
            self.logger.info("Updated existing CKAN package", id=package['id'])
        else:
            package = self.client.create_package(package_data)
            self.logger.info("Created new CKAN package", id=package['id'])
        
        # Upload resources
        resources = {}
        
        # CSV resource
        csv_resource = self._prepare_resource_data(
            csv_file, "CSV Data", "csv", "text/csv", package['id']
        )
        resources['csv'] = self._upsert_resource(package, csv_resource, csv_file)
        
        # JSON resource
        json_resource = self._prepare_resource_data(
            json_file, "JSON Data", "json", "application/json", package['id']
        )
        resources['json'] = self._upsert_resource(package, json_resource, json_file)
        
        # Metadata resource
        metadata_resource = self._prepare_resource_data(
            metadata_file, "Processing Metadata", "json", "application/json", package['id']
        )
        resources['metadata'] = self._upsert_resource(package, metadata_resource, metadata_file)
        
        result = {
            'package_id': package['id'],
            'package_name': package['name'],
            'resources': resources,
            'url': f"{self.client.base_url}/dataset/{package['name']}",
            'published_at': datetime.now().isoformat()
        }
        
        self.logger.info("Dataset published successfully", 
                        package_id=package['id'],
                        resources_count=len(resources))
        
        return result
    
    def _generate_package_name(self, org_id: str, dataset_id: str) -> str:
        """Generate CKAN-compatible package name."""
        # Clean and combine org_id and dataset_id
        clean_org = ''.join(c.lower() if c.isalnum() else '-' for c in org_id)
        clean_dataset = ''.join(c.lower() if c.isalnum() else '-' for c in dataset_id)
        
        # Remove consecutive dashes and leading/trailing dashes
        name = f"{clean_org}-{clean_dataset}"
        name = '-'.join(part for part in name.split('-') if part)
        
        # Ensure it's not too long (CKAN limit is typically 100 chars)
        if len(name) > 90:
            # Use hash suffix to ensure uniqueness
            hash_suffix = hashlib.md5(f"{org_id}-{dataset_id}".encode()).hexdigest()[:8]
            name = f"{name[:80]}-{hash_suffix}"
        
        return name
    
    def _prepare_package_data(
        self,
        metadata: Dict[str, Any],
        package_name: str,
        org_id: str,
        existing_package: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Prepare CKAN package metadata."""
        now = datetime.now().isoformat()
        
        package_data = {
            'name': package_name,
            'title': metadata.get('title', f'Dataset {package_name}'),
            'notes': metadata.get('description', 'Automated data publication'),
            'author': metadata.get('author', 'Compliance Automation Kit'),
            'author_email': metadata.get('author_email', ''),
            'maintainer': metadata.get('maintainer', org_id),
            'maintainer_email': metadata.get('maintainer_email', ''),
            'license_id': metadata.get('license', 'cc-by'),
            'owner_org': org_id,
            'private': metadata.get('private', False),
            'state': 'active',
            'extras': [
                {'key': 'profile', 'value': metadata.get('profile', '')},
                {'key': 'processing_date', 'value': metadata.get('processing_date', now)},
                {'key': 'data_quality_score', 'value': str(metadata.get('quality_score', ''))},
                {'key': 'validation_status', 'value': metadata.get('validation_status', '')},
                {'key': 'generated_by', 'value': 'ComplianceAutomationKit'},
                {'key': 'last_updated', 'value': now}
            ]
        }
        
        # Add tags
        tags = metadata.get('tags', [])
        if metadata.get('profile'):
            tags.append(metadata['profile'])
        tags.extend(['budget', 'government', 'automated'])
        
        package_data['tags'] = [{'name': tag} for tag in set(tags)]
        
        # If updating, preserve some fields
        if existing_package:
            package_data['id'] = existing_package['id']
            # Preserve creation date if it exists
            for extra in existing_package.get('extras', []):
                if extra['key'] == 'created_date':
                    package_data['extras'].append(extra)
                    break
            else:
                # Add creation date if this is the first time we're tracking it
                package_data['extras'].append({'key': 'created_date', 'value': now})
        else:
            package_data['extras'].append({'key': 'created_date', 'value': now})
        
        return package_data
    
    def _prepare_resource_data(
        self,
        file_path: Path,
        name: str,
        format_type: str,
        mimetype: str,
        package_id: str
    ) -> Dict[str, Any]:
        """Prepare CKAN resource metadata."""
        return {
            'package_id': package_id,
            'name': name,
            'description': f'{name} generated by Compliance Automation Kit',
            'format': format_type.upper(),
            'mimetype': mimetype,
            'size': file_path.stat().st_size,
            'last_modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
        }
    
    def _upsert_resource(
        self,
        package: Dict[str, Any],
        resource_data: Dict[str, Any],
        file_path: Path
    ) -> Dict[str, Any]:
        """Create or update a resource with file upload."""
        # Look for existing resource with same name
        existing_resource = None
        for resource in package.get('resources', []):
            if resource.get('name') == resource_data['name']:
                existing_resource = resource
                break
        
        if existing_resource:
            # Update existing resource
            resource_data['id'] = existing_resource['id']
            result = self.client.upload_resource_file(resource_data, file_path)
            self.logger.info("Updated existing resource", 
                           id=result['id'], name=resource_data['name'])
        else:
            # Create new resource
            result = self.client.upload_resource_file(resource_data, file_path)
            self.logger.info("Created new resource", 
                           id=result['id'], name=resource_data['name'])
        
        return result


def create_ckan_client_from_settings() -> CKANClient:
    """Create CKAN client from application settings."""
    if not settings.ckan_url or not settings.ckan_api_key:
        raise CKANError("CKAN URL and API key must be configured in settings")
    
    return CKANClient(
        base_url=settings.ckan_url,
        api_key=settings.ckan_api_key,
        timeout=settings.ckan_timeout,
        max_retries=settings.ckan_max_retries,
        backoff_factor=settings.ckan_backoff_factor
    )
