import logging
from pathlib import Path
from hwpx_extractor import HwpxExtractor
import zipfile
import io
import xml.etree.ElementTree as ET

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,  # DEBUG 레벨로 변경
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def print_element_structure(element, level=0, max_level=10):
    """XML 요소의 구조를 출력"""
    if level >= max_level:
        return
    
    indent = "  " * level
    tag = element.tag.split('}')[-1] if '}' in element.tag else element.tag
    attrs = ' '.join(f'{k}="{v}"' for k, v in element.attrib.items())
    text = element.text.strip() if element.text and element.text.strip() else None
    
    if attrs:
        print(f"{indent}<{tag} {attrs}>", end='')
    else:
        print(f"{indent}<{tag}>", end='')
        
    if text:
        print(f" {text} ", end='')
    
    has_children = len(element) > 0
    if has_children:
        print()  # 줄바꿈
        for child in element:
            print_element_structure(child, level + 1, max_level)
        print(f"{indent}</{tag}>")
    else:
        print(f"</{tag}>")

def analyze_xml_content(content: bytes):
    """XML 내용 분석"""
    try:
        tree = ET.parse(io.BytesIO(content))
        root = tree.getroot()
        print("\n=== XML 구조 분석 ===")
        print(f"루트 태그: {root.tag}")
        print("\n=== 상세 구조 ===")
        print_element_structure(root)
        
        # text 태그 분석
        print("\n=== text 태그 분석 ===")
        text_elements = root.findall(".//*")
        for elem in text_elements:
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            if tag == 'text' and elem.text and elem.text.strip():
                # 부모 태그들의 계층 구조 찾기
                parent_tags = []
                parent = elem
                while parent is not None:
                    parent = parent.getparent() if hasattr(parent, 'getparent') else None
                    if parent is not None:
                        parent_tag = parent.tag.split('}')[-1] if '}' in parent.tag else parent.tag
                        parent_tags.insert(0, parent_tag)
                
                parent_path = ' > '.join(parent_tags) if parent_tags else 'Root'
                print(f"텍스트 발견: '{elem.text.strip()}'")
                print(f"태그 계층: {parent_path} > text")
                print("-" * 50)
        
    except ET.ParseError as e:
        print(f"XML 파싱 에러: {e}")

def test_hwpx_extraction(file_path: str):
    """HWPX 파일 파싱 테스트"""
    try:
        # 파일 읽기
        file_path = Path(file_path)
        if not file_path.exists():
            print(f"파일이 존재하지 않습니다: {file_path}")
            return
        
        print(f"\n{'='*50}")
        print(f"테스트 파일: {file_path.name}")
        print(f"{'='*50}")
        print(f"파일 크기: {file_path.stat().st_size:,} bytes")
        
        # 파일 내용 읽기
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # ZIP 파일 구조 분석
        print("\n=== ZIP 파일 구조 ===")
        with zipfile.ZipFile(io.BytesIO(file_content)) as zf:
            for info in zf.infolist():
                print(f"파일: {info.filename} (크기: {info.file_size:,} bytes)")
            
            # content.hpf 파일 찾기 및 분석
            content_paths = ['Contents/content.hpf', 'content.hpf', 'Contents/section0.xml', 'Contents/content.xml']
            content_file = next((path for path in content_paths if path in zf.namelist()), None)
            
            if content_file:
                print(f"\n=== {content_file} 파일 분석 ===")
                with zf.open(content_file) as f:
                    content = f.read()
                    analyze_xml_content(content)
        
        # HWPX 파싱
        print("\n=== HWPX 파싱 시작 ===")
        extractor = HwpxExtractor(file_content)
        text = extractor.extract()
        
        # 결과 출력
        print("\n=== 추출 결과 ===")
        print(f"추출된 텍스트 길이: {len(text):,} 문자")
        print("\n=== 텍스트 미리보기 (처음 500자) ===")
        print(text[:500] + "..." if len(text) > 500 else text)
        
        # 결과 파일 저장
        output_file = file_path.parent / f"{file_path.stem}_extracted.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"\n추출된 텍스트가 저장된 파일: {output_file}")
        
    except Exception as e:
        print(f"\n[에러] {file_path.name} 처리 중 오류 발생: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    # 테스트할 HWPX 파일들
    TEST_FILES = [
        "/Users/kimtaewoong/Downloads/[메일]20250705_211433/국세청 연말정산 인적공제 연계 레이아웃(원천세과， 소득세과).hwpx",
        "/Users/kimtaewoong/Downloads/[메일]20250705_211433/건강보험 피부양자 연계 레이아웃(건보 자격부).hwpx",
        "/Users/kimtaewoong/Downloads/[메일]20250705_211433/급여서비스 기준 사전협의 검토결과(산림복지서비스이용권 지원사업).hwpx",
        "/Users/kimtaewoong/Downloads/[메일]20250705_211433/사회보장정보시스템 이용·연계 검토 결과 안내_수정.hwpx",
        "/Users/kimtaewoong/Downloads/[메일]20250705_211433/사회보장정보시스템 이용·연계 검토 결과 안내(서울시 중증장애인 수도요금 감면)_연계부_운영부 검토250514.hwpx",
        "/Users/kimtaewoong/Downloads/[메일]20250705_211433/통합채용시스템 오픈에 따른 연계 변경 요청.hwpx"
    ]
    
    print(f"\n총 {len(TEST_FILES)}개 파일 테스트 시작\n")
    
    for i, test_file in enumerate(TEST_FILES, 1):
        print(f"\n[{i}/{len(TEST_FILES)}] 파일 테스트 중...")
        test_hwpx_extraction(test_file)
    
    print(f"\n모든 파일({len(TEST_FILES)}개) 테스트 완료!") 