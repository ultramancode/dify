import io
import zipfile
from unittest.mock import Mock, patch

import pandas as pd
import pytest
from docx.oxml.text.paragraph import CT_P

from core.file import File, FileTransferMethod
from core.variables import ArrayFileSegment
from core.variables.segments import ArrayStringSegment
from core.variables.variables import StringVariable
from core.workflow.entities.node_entities import NodeRunResult
from core.workflow.entities.workflow_node_execution import WorkflowNodeExecutionStatus
from core.workflow.nodes.document_extractor import DocumentExtractorNode, DocumentExtractorNodeData
from core.workflow.nodes.document_extractor.node import (
    _extract_text_from_docx,
    _extract_text_from_excel,
    _extract_text_from_pdf,
    _extract_text_from_plain_text,
    _extract_text_from_hwpx,
)
from core.file.hwpx_extractor import TextExtractionError
from core.workflow.nodes.enums import NodeType


@pytest.fixture
def document_extractor_node():
    node_data = DocumentExtractorNodeData(
        title="Test Document Extractor",
        variable_selector=["node_id", "variable_name"],
    )
    return DocumentExtractorNode(
        id="test_node_id",
        config={"id": "test_node_id", "data": node_data.model_dump()},
        graph_init_params=Mock(),
        graph=Mock(),
        graph_runtime_state=Mock(),
    )


@pytest.fixture
def mock_graph_runtime_state():
    return Mock()


def test_run_variable_not_found(document_extractor_node, mock_graph_runtime_state):
    document_extractor_node.graph_runtime_state = mock_graph_runtime_state
    mock_graph_runtime_state.variable_pool.get.return_value = None

    result = document_extractor_node._run()

    assert isinstance(result, NodeRunResult)
    assert result.status == WorkflowNodeExecutionStatus.FAILED
    assert result.error is not None
    assert "File variable not found" in result.error


def test_run_invalid_variable_type(document_extractor_node, mock_graph_runtime_state):
    document_extractor_node.graph_runtime_state = mock_graph_runtime_state
    mock_graph_runtime_state.variable_pool.get.return_value = StringVariable(
        value="Not an ArrayFileSegment", name="test"
    )

    result = document_extractor_node._run()

    assert isinstance(result, NodeRunResult)
    assert result.status == WorkflowNodeExecutionStatus.FAILED
    assert result.error is not None
    assert "is not an ArrayFileSegment" in result.error


def create_test_hwpx_content() -> bytes:
    """Create a test HWPX file content with proper ZIP structure"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 필수 파일들 추가
        zf.writestr('mimetype', b'application/hwp+zip')
        zf.writestr('META-INF/container.xml', b'''<?xml version="1.0" encoding="UTF-8"?>
        <container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
            <rootfiles>
                <rootfile full-path="Contents/content.hpf" media-type="application/hwp+zip"/>
            </rootfiles>
        </container>''')
        
        # 실제 내용이 있는 section0.xml
        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <sec xmlns="http://www.hancom.co.kr/hwpml/2011/section">
            <p>test content</p>
        </sec>'''
        zf.writestr('Contents/section0.xml', content.encode('utf-8'))
        
        # 메타데이터 파일
        zf.writestr('Contents/content.hpf', b'''<?xml version="1.0" encoding="UTF-8"?>
        <package>
            <metadata>
                <title>Test Document</title>
            </metadata>
            <manifest>
                <item id="section0" href="Contents/section0.xml" media-type="application/xml"/>
            </manifest>
        </package>''')
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("mime_type", "file_content", "expected_text", "transfer_method", "extension"),
    [
        (
            "text/plain",
            b"Hello, world!",
            ["Hello, world!"],
            FileTransferMethod.LOCAL_FILE,
            ".txt",
        ),
        (
            "application/pdf",
            b"%PDF-1.5\n%Test PDF content",
            ["Mocked PDF content"],
            FileTransferMethod.LOCAL_FILE,
            ".pdf",
        ),
        (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            b"PK\x03\x04",
            ["Mocked DOCX content"],
            FileTransferMethod.REMOTE_URL,
            "",
        ),
        (
            "text/plain",
            b"Remote content",
            ["Remote content"],
            FileTransferMethod.REMOTE_URL,
            None,
        ),
        (
            "application/hwp+zip",
            create_test_hwpx_content(),
            ["test content"],
            FileTransferMethod.LOCAL_FILE,
            ".hwpx"
        ),
    ],
)
def test_run_extract_text(
    document_extractor_node,
    mock_graph_runtime_state,
    mime_type,
    file_content,
    expected_text,
    transfer_method,
    extension,
    monkeypatch,
):
    document_extractor_node.graph_runtime_state = mock_graph_runtime_state

    mock_file = Mock(spec=File)
    mock_file.mime_type = mime_type
    mock_file.transfer_method = transfer_method
    mock_file.related_id = "test_file_id" if transfer_method == FileTransferMethod.LOCAL_FILE else None
    mock_file.remote_url = "https://example.com/file.txt" if transfer_method == FileTransferMethod.REMOTE_URL else None
    mock_file.extension = extension

    mock_array_file_segment = Mock(spec=ArrayFileSegment)
    mock_array_file_segment.value = [mock_file]

    mock_graph_runtime_state.variable_pool.get.return_value = mock_array_file_segment

    mock_download = Mock(return_value=file_content)
    mock_ssrf_proxy_get = Mock()
    mock_ssrf_proxy_get.return_value.content = file_content
    mock_ssrf_proxy_get.return_value.raise_for_status = Mock()

    monkeypatch.setattr("core.file.file_manager.download", mock_download)
    monkeypatch.setattr("core.helper.ssrf_proxy.get", mock_ssrf_proxy_get)

    if mime_type == "application/pdf":
        mock_pdf_extract = Mock(return_value=expected_text[0])
        monkeypatch.setattr("core.workflow.nodes.document_extractor.node._extract_text_from_pdf", mock_pdf_extract)
    elif mime_type.startswith("application/vnd.openxmlformats"):
        mock_docx_extract = Mock(return_value=expected_text[0])
        monkeypatch.setattr("core.workflow.nodes.document_extractor.node._extract_text_from_docx", mock_docx_extract)
    elif mime_type == "application/hwp+zip":
        mock_hwpx_extract = Mock(return_value=expected_text[0])
        monkeypatch.setattr("core.workflow.nodes.document_extractor.node._extract_text_from_hwpx", mock_hwpx_extract)

    result = document_extractor_node._run()

    assert isinstance(result, NodeRunResult)
    assert result.status == WorkflowNodeExecutionStatus.SUCCEEDED, result.error
    assert result.outputs is not None
    assert result.outputs["text"] == ArrayStringSegment(value=expected_text)

    if transfer_method == FileTransferMethod.REMOTE_URL:
        mock_ssrf_proxy_get.assert_called_once_with("https://example.com/file.txt")
    elif transfer_method == FileTransferMethod.LOCAL_FILE:
        mock_download.assert_called_once_with(mock_file)


def test_extract_text_from_plain_text():
    text = _extract_text_from_plain_text(b"Hello, world!")
    assert text == "Hello, world!"


def test_extract_text_from_plain_text_non_utf8():
    import tempfile

    non_utf8_content = b"Hello, world\xa9."  # \xA9 represents © in Latin-1
    with tempfile.NamedTemporaryFile(delete=True) as temp_file:
        temp_file.write(non_utf8_content)
        temp_file.seek(0)
        text = _extract_text_from_plain_text(temp_file.read())
    assert text == "Hello, world©."


@patch("pypdfium2.PdfDocument")
def test_extract_text_from_pdf(mock_pdf_document):
    mock_page = Mock()
    mock_text_page = Mock()
    mock_text_page.get_text_range.return_value = "PDF content"
    mock_page.get_textpage.return_value = mock_text_page
    mock_pdf_document.return_value = [mock_page]
    text = _extract_text_from_pdf(b"%PDF-1.5\n%Test PDF content")
    assert text == "PDF content"


@patch("docx.Document")
def test_extract_text_from_docx(mock_document):
    mock_paragraph1 = Mock()
    mock_paragraph1.text = "Paragraph 1"
    mock_paragraph2 = Mock()
    mock_paragraph2.text = "Paragraph 2"
    mock_document.return_value.paragraphs = [mock_paragraph1, mock_paragraph2]
    mock_ct_p1 = Mock(spec=CT_P)
    mock_ct_p1.text = "Paragraph 1"
    mock_ct_p2 = Mock(spec=CT_P)
    mock_ct_p2.text = "Paragraph 2"
    mock_element = Mock(body=[mock_ct_p1, mock_ct_p2])
    mock_document.return_value.element = mock_element
    text = _extract_text_from_docx(b"PK\x03\x04")
    assert text == "Paragraph 1\nParagraph 2"


def test_node_type(document_extractor_node):
    assert document_extractor_node._node_type == NodeType.DOCUMENT_EXTRACTOR


@patch("pandas.ExcelFile")
def test_extract_text_from_excel_single_sheet(mock_excel_file):
    """Test extracting text from Excel file with single sheet and multiline content."""

    # Test multi-line cell
    data = {"Name\nwith\nnewline": ["John\nDoe", "Jane\nSmith"], "Age": [25, 30]}

    df = pd.DataFrame(data)

    # Mock ExcelFile
    mock_excel_instance = Mock()
    mock_excel_instance.sheet_names = ["Sheet1"]
    mock_excel_instance.parse.return_value = df
    mock_excel_file.return_value = mock_excel_instance

    file_content = b"fake_excel_content"
    result = _extract_text_from_excel(file_content)
    expected_manual = "| Name with newline | Age |\n| ----------------- | --- |\n\
| John Doe | 25 |\n| Jane Smith | 30 |\n\n"

    assert expected_manual == result
    mock_excel_instance.parse.assert_called_once_with(sheet_name="Sheet1")


@patch("pandas.ExcelFile")
def test_extract_text_from_excel_multiple_sheets(mock_excel_file):
    """Test extracting text from Excel file with multiple sheets and multiline content."""

    # Test multi-line cell
    data1 = {"Product\nName": ["Apple\nRed", "Banana\nYellow"], "Price": [1.50, 0.99]}
    df1 = pd.DataFrame(data1)

    data2 = {"City\nName": ["New\nYork", "Los\nAngeles"], "Population": [8000000, 3900000]}
    df2 = pd.DataFrame(data2)

    # Mock ExcelFile
    mock_excel_instance = Mock()
    mock_excel_instance.sheet_names = ["Products", "Cities"]
    mock_excel_instance.parse.side_effect = [df1, df2]
    mock_excel_file.return_value = mock_excel_instance

    file_content = b"fake_excel_content_multiple_sheets"
    result = _extract_text_from_excel(file_content)

    expected_manual1 = "| Product Name | Price |\n| ------------ | ----- |\n\
| Apple Red | 1.5 |\n| Banana Yellow | 0.99 |\n\n"
    expected_manual2 = "| City Name | Population |\n| --------- | ---------- |\n\
| New York | 8000000 |\n| Los Angeles | 3900000 |\n\n"

    assert expected_manual1 in result
    assert expected_manual2 in result

    assert mock_excel_instance.parse.call_count == 2


@patch("pandas.ExcelFile")
def test_extract_text_from_excel_empty_sheets(mock_excel_file):
    """Test extracting text from Excel file with empty sheets."""

    # Empty excel
    df = pd.DataFrame()

    # Mock ExcelFile
    mock_excel_instance = Mock()
    mock_excel_instance.sheet_names = ["EmptySheet"]
    mock_excel_instance.parse.return_value = df
    mock_excel_file.return_value = mock_excel_instance

    file_content = b"fake_excel_empty_content"
    result = _extract_text_from_excel(file_content)

    expected = "|  |\n|  |\n\n"
    assert result == expected

    mock_excel_instance.parse.assert_called_once_with(sheet_name="EmptySheet")


@patch("pandas.ExcelFile")
def test_extract_text_from_excel_sheet_parse_error(mock_excel_file):
    """Test handling of sheet parsing errors - should continue with other sheets."""

    # Test error
    data = {"Data": ["Test"], "Value": [123]}
    df = pd.DataFrame(data)

    # Mock ExcelFile
    mock_excel_instance = Mock()
    mock_excel_instance.sheet_names = ["GoodSheet", "BadSheet"]
    mock_excel_instance.parse.side_effect = [df, Exception("Parse error")]
    mock_excel_file.return_value = mock_excel_instance

    file_content = b"fake_excel_mixed_content"
    result = _extract_text_from_excel(file_content)

    expected_manual = "| Data | Value |\n| ---- | ----- |\n| Test | 123 |\n\n"

    assert expected_manual == result

    assert mock_excel_instance.parse.call_count == 2


@patch("pandas.ExcelFile")
def test_extract_text_from_excel_io_bytesio_usage(mock_excel_file):
    """Test that BytesIO is properly used with the file content."""

    # Test bytesio
    data = {"Test": [1], "Data": ["A"]}
    df = pd.DataFrame(data)

    # Mock ExcelFile
    mock_excel_instance = Mock()
    mock_excel_instance.sheet_names = ["TestSheet"]
    mock_excel_instance.parse.return_value = df
    mock_excel_file.return_value = mock_excel_instance

    file_content = b"test_excel_bytes"
    result = _extract_text_from_excel(file_content)

    mock_excel_file.assert_called_once()
    call_arg = mock_excel_file.call_args[0][0]
    assert isinstance(call_arg, io.BytesIO)

    expected_manual = "| Test | Data |\n| ---- | ---- |\n| 1 | A |\n\n"
    assert expected_manual == result


@patch("pandas.ExcelFile")
def test_extract_text_from_excel_all_sheets_fail(mock_excel_file):
    """Test when all sheets fail to parse - should return empty string."""

    # Mock ExcelFile
    mock_excel_instance = Mock()
    mock_excel_instance.sheet_names = ["BadSheet1", "BadSheet2"]
    mock_excel_instance.parse.side_effect = [Exception("Error 1"), Exception("Error 2")]
    mock_excel_file.return_value = mock_excel_instance

    file_content = b"fake_excel_all_bad_sheets"
    result = _extract_text_from_excel(file_content)

    assert result == ""

    assert mock_excel_instance.parse.call_count == 2


@patch("pandas.ExcelFile")
def test_extract_text_from_excel_numeric_type_column(mock_excel_file):
    """Test extracting text from Excel file with numeric column names."""

    # Test numeric type column
    data = {1: ["Test"], 1.1: ["Test"]}

    df = pd.DataFrame(data)

    # Mock ExcelFile
    mock_excel_instance = Mock()
    mock_excel_instance.sheet_names = ["Sheet1"]
    mock_excel_instance.parse.return_value = df
    mock_excel_file.return_value = mock_excel_instance

    file_content = b"fake_excel_content"
    result = _extract_text_from_excel(file_content)

    expected_manual = "| 1.0 | 1.1 |\n| --- | --- |\n| Test | Test |\n\n"

    assert expected_manual == result


def test_analyze_test_hwpx_structure():
    """테스트용 HWPX 파일의 구조를 분석"""
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    # 테스트용 HWPX 파일 생성
    content = create_test_hwpx_content()
    
    # ZIP 파일 구조 분석
    import zipfile
    import io
    
    buffer = io.BytesIO(content)
    with zipfile.ZipFile(buffer) as zf:
        # 모든 파일 목록 출력
        print("\nFiles in test HWPX:")
        for name in zf.namelist():
            print(f"- {name}")
            # 각 파일의 내용도 출력
            with zf.open(name) as f:
                content = f.read().decode('utf-8', errors='ignore')
                print(f"\nContents of {name}:")
                print(content)
                print("-" * 50)


def test_extract_text_from_hwpx():
    """Test extracting text from HWPX file"""
    from core.file.hwpx_extractor import create_test_hwpx_content
    
    # 테스트용 HWPX 파일 생성 (한컴 표준 문서 기반)
    test_content = create_test_hwpx_content("test content")
    
    # 노드 설정
    node = DocumentExtractorNode()
    node.validate_and_process({
        "file": {
            "content": test_content,
            "mime_type": "application/hwp+zip"
        }
    })
    
    # 결과 검증
    assert node.output == "test content"


def test_extract_text_from_invalid_hwpx():
    """Test extracting text from invalid HWPX file"""
    # 잘못된 HWPX 파일 내용
    invalid_content = b"This is not a valid HWPX file"
    
    # 노드 설정
    node = DocumentExtractorNode()
    
    # 예외 발생 확인
    with pytest.raises(Exception) as context:
        node.validate_and_process({
            "file": {
                "content": invalid_content,
                "mime_type": "application/hwp+zip"
            }
        })
    
    # 에러 메시지 확인
    assert "Invalid HWPX file" in str(context.exception)


def test_analyze_real_hwpx_structure():
    """실제 HWPX 파일의 구조를 분석하는 테스트"""
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    # 실제 HWPX 파일 읽기
    with open("path/to/real.hwpx", "rb") as f:
        content = f.read()
    
    # ZIP 파일 구조 분석
    import zipfile
    import io
    
    buffer = io.BytesIO(content)
    with zipfile.ZipFile(buffer) as zf:
        # 모든 파일 목록 출력
        print("\nFiles in HWPX:")
        for name in zf.namelist():
            print(f"- {name}")
        
        # section0.xml 내용 분석
        if "Contents/section0.xml" in zf.namelist():
            with zf.open("Contents/section0.xml") as f:
                content = f.read().decode('utf-8')
                print("\nContents of section0.xml:")
                print(content[:500])  # 처음 500자만 출력
        
        # content.hpf 내용 분석
        if "Contents/content.hpf" in zf.namelist():
            with zf.open("Contents/content.hpf") as f:
                content = f.read().decode('utf-8')
                print("\nContents of content.hpf:")
                print(content[:500])  # 처음 500자만 출력
