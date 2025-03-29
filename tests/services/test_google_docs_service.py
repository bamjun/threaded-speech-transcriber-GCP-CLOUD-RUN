import os
import pytest
from unittest.mock import Mock, patch

from services.google_docs_service import GoogleDocsService

from dotenv import load_dotenv

load_dotenv()




@pytest.fixture
def google_drive_folder_id():
    return os.getenv("GOOGLE_DRIVE_FOLDER_ID_FOR_DEV")


@pytest.fixture(params=[
    {
        "title": "Test Docs",
        "content": "test content",
        "expected_success": True
    }
])
def case_for_create_docs(request):
    return request.param

def test_create_docs(google_drive_folder_id, case_for_create_docs):
    # Given
    google_docs_service = GoogleDocsService()
    
    # When
    result = google_docs_service.create_document(
        title=case_for_create_docs["title"],
        parent_folder_id=google_drive_folder_id,
        content={"text": case_for_create_docs["content"]}
    )
    
    # Then
    assert result is not None
    assert "documentId" in result
    assert result["title"] == case_for_create_docs["title"]


@pytest.fixture(params=[
    {
        "title": "Test Sheet",
        "content": {"values": [["Header1"], ["Data1"]]},
        "expected_success": True
    }
])
def case_for_create_sheets(request):
    return request.param

def test_create_sheets(google_drive_folder_id, case_for_create_sheets):
    # Given
    google_docs_service = GoogleDocsService()
    
    # When
    result = google_docs_service.create_spreadsheet(
        title=case_for_create_sheets["title"],
        parent_folder_id=google_drive_folder_id,
        content=case_for_create_sheets["content"]
    )
    
    # Then
    assert result is not None
    assert "spreadsheetId" in result
    assert result["title"] == case_for_create_sheets["title"]

def test_create_sheets_failure():
    # Given
    google_docs_service = GoogleDocsService()
    invalid_folder_id = "invalid_folder_id"

    # When/Then
    with pytest.raises(Exception):
        google_docs_service.create_spreadsheet(
            title="Failed Sheet",
            parent_folder_id=invalid_folder_id,
            content={"values": [["Header1"], ["Data1"]]}
        )
