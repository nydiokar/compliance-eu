"""Test CKAN client functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.core.publish.ckan import CKANClient, CKANPublisher, CKANError, CKANClientError


class TestCKANClient:
    """Test CKAN client basic functionality."""
    
    def test_client_initialization(self):
        """Test client initialization with proper parameters."""
        client = CKANClient(
            base_url="http://test.ckan.org",
            api_key="test-key",
            timeout=15,
            max_retries=2
        )
        
        assert client.base_url == "http://test.ckan.org"
        assert client.api_key == "test-key"
        assert client.timeout == 15
        assert "Authorization" in client.session.headers
        assert client.session.headers["Authorization"] == "test-key"
    
    @patch('src.core.publish.ckan.requests.Session')
    def test_successful_request(self, mock_session_class):
        """Test successful API request."""
        # Setup mock
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'success': True,
            'result': {'id': 'test-package', 'name': 'test'}
        }
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        # Test client
        client = CKANClient("http://test.ckan.org", "test-key")
        client.session = mock_session  # Override session
        
        result = client._make_request('GET', 'package_show', params={'id': 'test'})
        
        assert result == {'id': 'test-package', 'name': 'test'}
        mock_session.request.assert_called_once()
    
    @patch('src.core.publish.ckan.requests.Session')
    def test_client_error_handling(self, mock_session_class):
        """Test client error handling."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = CKANClient("http://test.ckan.org", "test-key")
        client.session = mock_session
        
        with pytest.raises(CKANClientError):
            client._make_request('GET', 'package_show', params={'id': 'nonexistent'})
    
    @patch('src.core.publish.ckan.requests.Session')
    def test_ckan_api_error_handling(self, mock_session_class):
        """Test CKAN API error handling."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'success': False,
            'error': {'message': 'Invalid package name'}
        }
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = CKANClient("http://test.ckan.org", "test-key")
        client.session = mock_session
        
        with pytest.raises(CKANError):
            client._make_request('POST', 'package_create', data={'name': 'invalid name'})


class TestCKANPublisher:
    """Test CKAN publisher functionality."""
    
    def test_package_name_generation(self):
        """Test CKAN package name generation."""
        mock_client = Mock()
        publisher = CKANPublisher(mock_client)
        
        # Test normal case
        name = publisher._generate_package_name("municipality-sofia", "budget-2025")
        assert name == "municipality-sofia-budget-2025"
        
        # Test with special characters
        name = publisher._generate_package_name("Test Org!!!", "Dataset#123")
        assert name == "test-org-dataset-123"
        
        # Test very long names
        long_org = "a" * 50
        long_dataset = "b" * 50
        name = publisher._generate_package_name(long_org, long_dataset)
        assert len(name) <= 90  # Should be truncated
        assert "-" in name[-10:]  # Should contain hash at the end
    
    def test_prepare_package_data(self):
        """Test package metadata preparation."""
        mock_client = Mock()
        publisher = CKANPublisher(mock_client)
        
        metadata = {
            'title': 'Test Dataset',
            'description': 'Test description',
            'profile': 'budget_execution_v1',
            'tags': ['budget', 'test']
        }
        
        package_data = publisher._prepare_package_data(
            metadata, "test-package", "test-org"
        )
        
        assert package_data['name'] == "test-package"
        assert package_data['title'] == 'Test Dataset'
        assert package_data['owner_org'] == "test-org"
        assert len(package_data['tags']) > 0
        assert len(package_data['extras']) > 0
    
    @patch('src.core.publish.ckan.Path')
    def test_prepare_resource_data(self, mock_path):
        """Test resource metadata preparation."""
        mock_client = Mock()
        publisher = CKANPublisher(mock_client)
        
        # Mock file stats
        mock_file_path = Mock()
        mock_stat = Mock()
        mock_stat.st_size = 1024
        mock_stat.st_mtime = 1640995200  # 2022-01-01
        mock_file_path.stat.return_value = mock_stat
        
        resource_data = publisher._prepare_resource_data(
            mock_file_path, "Test CSV", "csv", "text/csv", "package-123"
        )
        
        assert resource_data['name'] == "Test CSV"
        assert resource_data['format'] == "CSV"
        assert resource_data['mimetype'] == "text/csv"
        assert resource_data['package_id'] == "package-123"
        assert resource_data['size'] == 1024


@pytest.fixture
def temp_files(tmp_path):
    """Create temporary files for testing."""
    csv_file = tmp_path / "test.csv"
    json_file = tmp_path / "test.json"
    metadata_file = tmp_path / "metadata.json"
    
    csv_file.write_text("col1,col2\nval1,val2")
    json_file.write_text('{"data": [{"col1": "val1", "col2": "val2"}]}')
    metadata_file.write_text('{"title": "Test Dataset"}')
    
    return {
        'csv': csv_file,
        'json': json_file,
        'metadata': metadata_file
    }


@patch('src.core.publish.ckan.create_ckan_client_from_settings')
def test_ckan_client_from_settings(mock_create_client):
    """Test CKAN client creation from settings."""
    from src.core.publish.ckan import create_ckan_client_from_settings
    
    # Mock settings
    with patch('src.core.publish.ckan.settings') as mock_settings:
        mock_settings.ckan_url = "http://test.ckan.org"
        mock_settings.ckan_api_key = "test-key"
        mock_settings.ckan_timeout = 45
        mock_settings.ckan_max_retries = 5
        mock_settings.ckan_backoff_factor = 2.0
        
        # Should not raise an exception
        mock_create_client.return_value = Mock()
        client = create_ckan_client_from_settings()
        
        # Verify it was called
        mock_create_client.assert_called_once()