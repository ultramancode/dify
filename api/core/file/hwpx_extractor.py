"""HWPX 파일에서 텍스트를 추출하는 모듈"""

import logging
from xml.etree import ElementTree as ET
import zipfile
import io
from typing import List, Optional

logger = logging.getLogger(__name__)

class HwpxError(Exception):
    """HWPX 처리 기본 예외"""
    pass

class UnsupportedFileTypeError(HwpxError):
    """지원되지 않는 파일 형식"""
    def __init__(self, stage: str, message: str):
        super().__init__(f"[{stage}] {message}")

class TextExtractionError(HwpxError):
    """텍스트 추출 실패"""
    def __init__(self, stage: str, message: str):
        super().__init__(f"[{stage}] {message}")

class HwpxExtractor:
    # XPath 패턴 정의 - 일반적인 태그 이름 기반
    XPATH_PATTERNS = {
        'section': ['.//{*}section', './/{*}sec', './/{*}body', './/{*}div'],
        'paragraph': ['.//{*}p', './/{*}para', './/{*}paragraph'],
        'text': ['.//{*}t', './/{*}text', './/{*}textBox'],
        'run': ['.//{*}run', './/{*}r', './/{*}span'],
        'table': ['.//{*}table', './/{*}tbl', './/{*}tableSection'],
        'table_head': ['.//{*}tblhead', './/{*}thead', './/{*}tblHead', './/{*}tableHeader'],
        'table_body': ['.//{*}tblbody', './/{*}tbody', './/{*}tblBody', './/{*}tableBody'],
        'row': ['.//{*}tr', './/{*}row', './/{*}tableRow'],
        'cell': ['.//{*}td', './/{*}tc', './/{*}cell', './/{*}tableCell'],
        'image': ['.//{*}img', './/{*}image', './/{*}pic', './/{*}picture'],
        'shape': ['.//{*}shape', './/{*}drawing', './/{*}object'],
        'header': ['.//{*}header', './/{*}hdr', './/{*}pageHeader'],
        'footer': ['.//{*}footer', './/{*}ftr', './/{*}pageFooter'],
        'footnote': ['.//{*}footnote', './/{*}note', './/{*}endnote']
    }

    CONTENT_PATHS = [
        'Contents/content.xml',
        'content.xml',
        'Contents/section0.xml'
    ]

    def __init__(self, file_content: bytes):
        """초기화"""
        self.bytes = file_content
        self.tree: Optional[ET.ElementTree] = None
        self.namelist: List[str] = []

    def _setup_parser(self) -> ET.XMLParser:
        """XML 파서 설정
        
        Note:
            xml.etree.ElementTree의 기본 파서는 보안을 위해 entity 해석을 기본적으로 비활성화함
        """
        try:
            # Python 3.7+ 방식 시도
            return ET.XMLParser(resolve_entities=False)
        except TypeError:
            # 이전 버전이거나 옵션을 지원하지 않는 경우
            return ET.XMLParser()

    def _load_tree(self) -> None:
        """HWPX 파일에서 XML 트리를 로드"""
        try:
            logger.info("Starting to load HWPX file")
            with zipfile.ZipFile(io.BytesIO(self.bytes)) as zf:
                self.namelist = zf.namelist()
                logger.info(f"Files in HWPX: {self.namelist}")
                
                content_path = next(
                    (path for path in self.CONTENT_PATHS if path in self.namelist),
                    None
                )
                
                if not content_path:
                    logger.error(f"HWPX content file not found. Available files: {self.namelist}")
                    raise UnsupportedFileTypeError("File Structure", "HWPX content not found")

                logger.info(f"Found content file at: {content_path}")
                with zf.open(content_path) as f:
                    parser = self._setup_parser()
                    content = f.read()
                    logger.info(f"Content file size: {len(content)} bytes")
                    try:
                        self.tree = ET.parse(io.BytesIO(content), parser=parser)
                        logger.info("Successfully parsed XML tree")
                    except ET.ParseError as e:
                        logger.error(f"XML parsing error: {e}")
                        logger.error(f"Content preview: {content[:200]}")  # Show first 200 bytes
                        raise
                    
        except zipfile.BadZipFile as e:
            logger.error(f"Invalid HWPX file format: {e}")
            logger.error(f"File content preview: {self.bytes[:50]}")  # Show first 50 bytes
            raise UnsupportedFileTypeError("ZIP Extraction", f"Invalid HWPX file: {e}")
        except ET.ParseError as e:
            logger.error(f"XML parsing error: {e}")
            raise TextExtractionError("XML Parsing", f"Failed to parse document: {e}")
        except Exception as e:
            logger.error(f"Unexpected error while loading tree: {str(e)}", exc_info=True)
            raise TextExtractionError("Tree Loading", f"Failed to load document tree: {str(e)}")

    def _find_all_elements(self, elem: ET.Element, pattern_key: str) -> List[ET.Element]:
        """주어진 패턴으로 모든 요소 찾기"""
        seen = set()
        unique_elements = []
        for pattern in self.XPATH_PATTERNS[pattern_key]:
            for element in elem.findall(pattern):
                if id(element) not in seen:
                    seen.add(id(element))
                    unique_elements.append(element)
        return unique_elements

    def _filter_text(self, text: str) -> str:
        """텍스트 정제
        - 공백 문자 정규화
        - 연속된 빈 줄 제거
        """
        if not text:
            return ""
        
        # 공백 문자 정규화
        text = self._normalize_text(text)
        if not text:
            return ""
        
        # 줄 단위로 처리
        lines = text.split('\n')
        processed_lines = []
        prev_empty = False
        
        for line in lines:
            line = line.strip()
            is_empty = not bool(line)
            
            # 빈 줄이 연속되지 않도록 처리
            if is_empty:
                if not prev_empty:
                    processed_lines.append('')
                prev_empty = True
            else:
                processed_lines.append(line)
                prev_empty = False
        
        # 시작과 끝의 빈 줄 제거
        while processed_lines and not processed_lines[0]:
            processed_lines.pop(0)
        while processed_lines and not processed_lines[-1]:
            processed_lines.pop()
        
        return '\n'.join(processed_lines)

    def _normalize_text(self, text: str) -> str:
        """텍스트 정규화 - 공백 문자 처리"""
        if not text:
            return ""
        # 여러 종류의 공백 문자를 일반 공백으로 변환
        text = ' '.join(text.split())
        return text

    def _get_tag_without_ns(self, tag: str) -> str:
        """태그에서 네임스페이스 제거"""
        return tag.split('}')[-1] if '}' in tag else tag

    def _is_tag_matching(self, element_tag: str, pattern_tags: list) -> bool:
        """태그 매칭 여부 확인"""
        element_tag = self._get_tag_without_ns(element_tag)
        for pattern in pattern_tags:
            pattern_tag = pattern.split('/')[-1].replace('{*}', '')
            if element_tag.lower() == pattern_tag.lower():
                return True
        return False

    def _parse_table(self, table: ET.Element) -> str:
        """테이블 내용 파싱"""
        try:
            rows = []
            max_cols = 0
            
            # 모든 행 찾기
            all_rows = (
                self._find_all_elements(table, 'table_head') +
                self._find_all_elements(table, 'table_body') +
                self._find_all_elements(table, 'row')
            )
            
            # 각 행의 셀 처리
            for row in all_rows:
                if self._is_tag_matching(row.tag, self.XPATH_PATTERNS['table_head']) or \
                   self._is_tag_matching(row.tag, self.XPATH_PATTERNS['table_body']):
                    # thead나 tbody인 경우 내부 행들을 처리
                    inner_rows = self._find_all_elements(row, 'row')
                    if inner_rows:
                        for inner_row in inner_rows:
                            cells = self._find_all_elements(inner_row, 'cell')
                            if cells:
                                row_texts = []
                                for cell in cells:
                                    # 셀 내용 정제
                                    cell_text = self._parse_text_block(cell).strip()
                                    # 줄바꿈을 공백으로 변환
                                    cell_text = ' '.join(cell_text.split())
                                    row_texts.append(cell_text)
                                if any(row_texts):  # 빈 행 제외
                                    max_cols = max(max_cols, len(row_texts))
                                    rows.append(row_texts)
                else:
                    # 일반 행인 경우 직접 처리
                    cells = self._find_all_elements(row, 'cell')
                    if cells:
                        row_texts = []
                        for cell in cells:
                            # 셀 내용 정제
                            cell_text = self._parse_text_block(cell).strip()
                            # 줄바꿈을 공백으로 변환
                            cell_text = ' '.join(cell_text.split())
                            row_texts.append(cell_text)
                        if any(row_texts):  # 빈 행 제외
                            max_cols = max(max_cols, len(row_texts))
                            rows.append(row_texts)
            
            if not rows:
                return ""
            
            # 각 행의 셀 수를 최대 열 수에 맞춤
            table_str = []
            for row in rows:
                # 빈 셀 채우기
                if len(row) < max_cols:
                    row.extend([''] * (max_cols - len(row)))
                # 실제 내용이 있는 셀만 포함
                cells = [cell for cell in row if cell.strip()]
                if cells:  # 빈 행 제외
                    table_str.append('\t'.join(cells))
            
            return '\n'.join(table_str)
            
        except Exception as e:
            logger.warning(f"Failed to parse table: {e}")
            return ""

    def _parse_text_block(self, node: ET.Element, prefix: str = "") -> str:
        """텍스트 블록 파싱"""
        try:
            texts = []
            
            # 직접 텍스트 노드 검색
            for text_elem in self._find_all_elements(node, 'text'):
                if text_elem.text:
                    text = self._filter_text(text_elem.text)
                    if text:
                        texts.append(text)
            
            # run 태그 내부 텍스트 검색
            for run in self._find_all_elements(node, 'run'):
                for text_elem in self._find_all_elements(run, 'text'):
                    if text_elem.text:
                        text = self._filter_text(text_elem.text)
                        if text:
                            texts.append(text)
                        
            return prefix + " ".join(filter(None, texts))
        except Exception as e:
            logger.warning(f"Failed to parse text block: {e}")
            return ""

    def _parse_image(self, image: ET.Element) -> str:
        """이미지 캡션 파싱"""
        try:
            caption = self._find_element(image, 'caption')
            if caption is not None:
                text = self._get_text_content(caption)
                logger.info(f"Found image caption: {text[:50]}...")
                return text
            return ""
        except Exception as e:
            # 캡션이 없는 것은 정상적인 케이스이므로 워닝 제거
            return ""

    def _parse_shape(self, shape: ET.Element) -> str:
        """도형 캡션 파싱"""
        try:
            caption = self._find_element(shape, 'caption')
            if caption is not None:
                text = self._get_text_content(caption)
                logger.info(f"Found shape caption: {text[:50]}...")
                return text
            return ""
        except Exception as e:
            logger.warning(f"Failed to parse shape: {e}")
            return ""

    def _find_element(self, elem: ET.Element, tag: str) -> Optional[ET.Element]:
        """주어진 태그를 가진 요소 찾기"""
        for pattern in self.XPATH_PATTERNS[tag]:
            for element in elem.findall(pattern):
                return element
        return None

    def _get_text_content(self, elem: ET.Element) -> str:
        """요소의 텍스트 내용 추출"""
        return ''.join(elem.itertext())

    def extract(self) -> str:
        """HWPX 문서에서 텍스트를 추출"""
        if self.tree is None:
            try:
                self._load_tree()
            except Exception as e:
                logger.error(f"Failed to load document tree: {e}")
                raise TextExtractionError("Tree Loading", "Failed to load document tree")
            
        root = self.tree.getroot()
        logger.info(f"XML Root tag: {root.tag}")
        
        all_parts = []
        section_texts = []
        
        try:
            # 섹션 처리
            sections = self._find_all_elements(root, 'section')
            if not sections:
                sections = [root]
            
            for section in sections:
                text = self._parse_section(section)
                if text.strip():
                    section_texts.append(text)
            
            if section_texts:
                all_parts.extend(section_texts)

            # 헤더/푸터/각주 처리
            for elem_type, prefix in [
                ('header', "HEADER: "),
                ('footer', "FOOTER: "),
                ('footnote', "FOOTNOTE: ")
            ]:
                elements = self._find_all_elements(root, elem_type)
                for elem in elements:
                    text = self._parse_text_block(elem, prefix)
                    if text:
                        all_parts.append(text)

            # 최종 결과 정리
            if not all_parts:
                return ""
                
            # 전체 문서 레벨에서 중복 제거
            combined_text = '\n\n'.join(all_parts)
            final_text = self._filter_text(combined_text)
            
            # 테이블 구조 보존을 위한 후처리
            lines = final_text.split('\n')
            processed_lines = []
            table_mode = False
            table_content = []
            
            for line in lines:
                if '\t' in line:  # 테이블 행 감지
                    if not table_mode:
                        table_mode = True
                        if processed_lines and processed_lines[-1].strip():
                            processed_lines.append('')  # 테이블 전에 빈 줄 추가
                    table_content.append(line)
                else:
                    if table_mode:
                        # 테이블 종료 처리
                        if table_content:
                            # 테이블 중복 제거
                            unique_rows = []
                            seen = set()
                            for table_line in table_content:
                                if table_line not in seen:
                                    unique_rows.append(table_line)
                                    seen.add(table_line)
                            processed_lines.extend(unique_rows)
                            if line.strip():
                                processed_lines.append('')  # 테이블 후에 빈 줄 추가
                        table_mode = False
                        table_content = []
                    if line.strip():
                        processed_lines.append(line)
                    elif not processed_lines or processed_lines[-1].strip():
                        processed_lines.append(line)
            
            # 마지막 테이블 처리
            if table_content:
                unique_rows = []
                seen = set()
                for table_line in table_content:
                    if table_line not in seen:
                        unique_rows.append(table_line)
                        seen.add(table_line)
                processed_lines.extend(unique_rows)
            
            return '\n'.join(processed_lines)

        except Exception as e:
            logger.error(f"Failed to extract text: {e}")
            raise TextExtractionError("Content Extraction", f"Text extraction failed: {e}")

    def _parse_section(self, section: ET.Element) -> str:
        """섹션 내용 파싱"""
        parts = []
        current_section_text = []
        
        try:
            # 문단 처리
            for para in self._find_all_elements(section, 'paragraph'):
                text = self._parse_text_block(para)
                if text:
                    current_section_text.append(text)

            # 현재 섹션의 텍스트가 있으면 처리
            if current_section_text:
                # 섹션 텍스트 중복 제거 및 정리
                section_text = self._filter_text('\n'.join(current_section_text))
                if section_text:
                    parts.append(section_text)

            # 테이블 처리
            for table in self._find_all_elements(section, 'table'):
                text = self._parse_table(table)
                if text:
                    # 테이블 앞뒤로 빈 줄 추가
                    parts.append('\n' + text + '\n')

            # 이미지 처리
            for img in self._find_all_elements(section, 'image'):
                text = self._parse_image(img)
                if text:
                    parts.append(text)

            # 도형 처리
            for shape in self._find_all_elements(section, 'shape'):
                text = self._parse_shape(shape)
                if text:
                    parts.append(text)

            # 최종 결과 정리
            result = '\n'.join(parts)
            
            # 섹션 구분선 추가 (실제 내용이 있는 경우에만)
            if result.strip():
                return result
            return ""

        except Exception as e:
            logger.warning(f"Failed to parse section: {e}")
            return ""

def create_test_hwpx_content(text: str = "test content") -> bytes:
    """테스트용 HWPX 파일 생성
    
    실제 HWPX 파일 구조를 따르되, 네임스페이스만 자체 구조로 사용합니다.
    """
    # mimetype 파일 내용
    mimetype = "application/hwp+zip"
    
    # META-INF/container.xml 내용
    container_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0">
    <rootfiles>
        <rootfile full-path="Contents/content.hpf" media-type="application/hwp+zip"/>
    </rootfiles>
</container>'''
    
    # Contents/content.hpf 내용
    content_hpf = '''<?xml version="1.0" encoding="UTF-8"?>
<hpf version="1.0">
    <head>
        <meta name="title" content="Test Document"/>
        <meta name="language" content="ko"/>
    </head>
    <body>
        <section id="section0" href="section0.xml"/>
    </body>
</hpf>'''
    
    # Contents/section0.xml 내용 (주요 텍스트)
    section0_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<section id="section0">
    <paragraph>
        <content>{text}</content>
    </paragraph>
</section>'''
    
    # ZIP 파일 생성
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # mimetype은 압축하지 않고 저장 (HWPX 스펙)
        zf.writestr('mimetype', mimetype, compress_type=zipfile.ZIP_STORED)
        # 나머지 파일들
        zf.writestr('META-INF/container.xml', container_xml)
        zf.writestr('Contents/content.hpf', content_hpf)
        zf.writestr('Contents/section0.xml', section0_xml)
    
    return zip_buffer.getvalue()

def _extract_text_from_hwpx(file_content: bytes) -> str:
    """
    HWPX 파일에서 텍스트를 추출하는 인터페이스 함수
    """
    try:
        extractor = HwpxExtractor(file_content)
        return extractor.extract()
    except HwpxError as e:
        logger.error(f"HWPX extraction error: {e}")
        raise TextExtractionError("Interface", str(e))
    except Exception as e:
        logger.error(f"Unexpected error in HWPX extraction: {e}")
        raise TextExtractionError("Interface", f"Failed to process HWPX: {e}") 