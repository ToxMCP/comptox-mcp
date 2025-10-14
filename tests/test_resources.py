import sys
import os
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import unittest
from unittest.mock import patch, MagicMock

# Now we can import our modules
from epacomp_tox.resources.base import BaseResource
from epacomp_tox.resources.chemical import ChemicalResource
from epacomp_tox.resources.exposure import ExposureResource
from epacomp_tox.resources.hazard import HazardResource
from epacomp_tox.resources.chemical_list import ChemicalListResource
from epacomp_tox.resources.cheminformatics import CheminformaticsResource

class TestChemicalResource(unittest.TestCase):
    """Test cases for the Chemical resource implementation."""
    
    def setUp(self):
        """Set up test environment."""
        self.api_key = "test_key"
        with patch('ctxpy.Chemical') as mock_chemical:
            self.mock_client = MagicMock()
            mock_chemical.return_value = self.mock_client
            self.resource = ChemicalResource(api_key=self.api_key)
    
    def test_search_chemical(self):
        """Test searching for chemicals."""
        # Set up mock return value
        expected_result = [{"dtxsid": "DTXSID1234567", "preferredName": "Test Chemical"}]
        self.mock_client.search.return_value = expected_result
        
        # Call the method
        result = self.resource.search_chemical(query="test", search_type="equals")
        
        # Verify the result
        self.assertEqual(result, expected_result)
        self.mock_client.search.assert_called_once_with(by="equals", word="test")
    
    def test_get_chemical_details(self):
        """Test getting chemical details."""
        # Set up mock return value
        expected_result = {"dtxsid": "DTXSID1234567", "preferredName": "Test Chemical"}
        self.mock_client.details.return_value = expected_result
        
        # Call the method
        result = self.resource.get_chemical_details(id="DTXSID1234567", id_type="dtxsid")
        
        # Verify the result
        self.assertEqual(result, expected_result)
        self.mock_client.details.assert_called_once_with(by="dtxsid", word="DTXSID1234567")

class TestExposureResource(unittest.TestCase):
    """Test cases for the Exposure resource implementation."""
    
    def setUp(self):
        """Set up test environment."""
        self.api_key = "test_key"
        with patch('ctxpy.Exposure') as mock_exposure:
            self.mock_client = MagicMock()
            mock_exposure.return_value = self.mock_client
            self.resource = ExposureResource(api_key=self.api_key)
    
    def test_search_cpdat(self):
        """Test searching for CPDat data."""
        # Set up mock return value
        expected_result = [{"dtxsid": "DTXSID1234567", "function": "Test Function"}]
        self.mock_client.search_cpdat.return_value = expected_result
        
        # Call the method
        result = self.resource.search_cpdat(vocab_name="fc", dtxsid="DTXSID1234567")
        
        # Verify the result
        self.assertEqual(result, expected_result)
        self.mock_client.search_cpdat.assert_called_once_with(vocab_name="fc", dtxsid="DTXSID1234567")

class TestHazardResource(unittest.TestCase):
    """Test cases for the Hazard resource implementation."""
    
    def setUp(self):
        """Set up test environment."""
        self.api_key = "test_key"
        with patch('ctxpy.Hazard') as mock_hazard:
            self.mock_client = MagicMock()
            mock_hazard.return_value = self.mock_client
            self.resource = HazardResource(api_key=self.api_key)
    
    def test_search_hazard(self):
        """Test searching for hazard data."""
        # Set up mock return value
        expected_result = [{"dtxsid": "DTXSID1234567", "hazard_data": "Test Hazard"}]
        self.mock_client.search.return_value = expected_result
        
        # Call the method
        result = self.resource.search_hazard(data_type="human", dtxsid="DTXSID1234567")
        
        # Verify the result
        self.assertEqual(result, expected_result)
        self.mock_client.search.assert_called_once_with(by="human", dtxsid="DTXSID1234567", summary=True)

class TestChemicalListResource(unittest.TestCase):
    """Test cases for the ChemicalList resource implementation."""
    
    def setUp(self):
        """Set up test environment."""
        self.api_key = "test_key"
        with patch('ctxpy.ChemicalList') as mock_chemical_list:
            self.mock_client = MagicMock()
            mock_chemical_list.return_value = self.mock_client
            self.resource = ChemicalListResource(api_key=self.api_key)
    
    def test_get_public_list_names(self):
        """Test getting public list names."""
        # Set up mock return value
        expected_result = ["List1", "List2"]
        self.mock_client.public_list_names.return_value = expected_result
        
        # Call the method
        result = self.resource.get_public_list_names()
        
        # Verify the result
        self.assertEqual(result, expected_result)
        self.mock_client.public_list_names.assert_called_once()

class TestCheminformaticsResource(unittest.TestCase):
    """Test cases for the Cheminformatics resource implementation."""
    
    def setUp(self):
        """Set up test environment."""
        self.api_key = "test_key"
        self.resource = CheminformaticsResource(api_key=self.api_key)
    
    @patch('ctxpy.search_toxprints')
    def test_search_toxprints(self, mock_search_toxprints):
        """Test searching for ToxPrint chemotypes."""
        # Set up mock return value
        mock_df = MagicMock()
        mock_df.to_dict.return_value = {"column1": {"row1": 1}}
        mock_search_toxprints.return_value = mock_df
        
        # Call the method
        result = self.resource.search_toxprints(chemical="DTXSID1234567")
        
        # Verify the result
        self.assertEqual(result, {"column1": {"row1": 1}})
        mock_search_toxprints.assert_called_once_with(chemical="DTXSID1234567")

if __name__ == "__main__":
    unittest.main()
