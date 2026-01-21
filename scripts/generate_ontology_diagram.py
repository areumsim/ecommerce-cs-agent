#!/usr/bin/env python3
"""
온톨로지 다이어그램 생성 스크립트

TTL 파일에서 클래스/속성 관계를 추출하여 다양한 형식으로 시각화합니다.

출력 형식:
- Mermaid (마크다운 호환)
- GraphViz DOT (이미지 변환용)
- HTML (인터랙티브 뷰어)

사용법:
    python scripts/generate_ontology_diagram.py
    python scripts/generate_ontology_diagram.py --format all
    python scripts/generate_ontology_diagram.py --format mermaid --output docs/ontology.md
"""

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rdflib import OWL, RDF, RDFS, Graph, Namespace
from rdflib.term import URIRef

# 네임스페이스
ECOM = Namespace("http://example.org/ecommerce#")
SCHEMA = Namespace("http://schema.org/")

# 프로젝트 경로
PROJECT_ROOT = Path(__file__).parent.parent
ONTOLOGY_FILE = PROJECT_ROOT / "ontology" / "ecommerce.ttl"
OUTPUT_DIR = PROJECT_ROOT / "docs" / "images"


@dataclass
class OntologyClass:
    """온톨로지 클래스 정보"""

    uri: str
    name: str
    label_ko: str = ""
    parent: Optional[str] = None
    properties: list[str] = field(default_factory=list)


@dataclass
class OntologyProperty:
    """온톨로지 속성 정보"""

    uri: str
    name: str
    label_ko: str = ""
    domain: Optional[str] = None
    range: Optional[str] = None
    is_object_property: bool = True
    is_symmetric: bool = False
    is_functional: bool = False
    inverse_of: Optional[str] = None


class OntologyParser:
    """온톨로지 파서"""

    def __init__(self, ttl_path: Path):
        self.graph = Graph()
        self.graph.parse(ttl_path, format="turtle")
        self.classes: dict[str, OntologyClass] = {}
        self.object_properties: dict[str, OntologyProperty] = {}
        self.datatype_properties: dict[str, OntologyProperty] = {}
        self._parse()

    def _get_local_name(self, uri: URIRef) -> str:
        """URI에서 로컬 이름 추출"""
        uri_str = str(uri)
        if "#" in uri_str:
            return uri_str.split("#")[-1]
        return uri_str.split("/")[-1]

    def _get_label_ko(self, uri: URIRef) -> str:
        """한국어 라벨 추출"""
        for label in self.graph.objects(uri, RDFS.label):
            if hasattr(label, "language") and label.language == "ko":
                return str(label)
        return ""

    def _parse(self):
        """온톨로지 파싱"""
        # 클래스 파싱
        for cls in self.graph.subjects(RDF.type, OWL.Class):
            if not isinstance(cls, URIRef):
                continue
            name = self._get_local_name(cls)
            if name.startswith("_"):  # blank node 제외
                continue

            parent = None
            for p in self.graph.objects(cls, RDFS.subClassOf):
                if isinstance(p, URIRef):
                    parent = self._get_local_name(p)
                    break

            self.classes[name] = OntologyClass(
                uri=str(cls),
                name=name,
                label_ko=self._get_label_ko(cls),
                parent=parent,
            )

        # Object Property 파싱
        for prop in self.graph.subjects(RDF.type, OWL.ObjectProperty):
            if not isinstance(prop, URIRef):
                continue
            name = self._get_local_name(prop)

            domain = None
            for d in self.graph.objects(prop, RDFS.domain):
                if isinstance(d, URIRef):
                    domain = self._get_local_name(d)
                    break

            range_ = None
            for r in self.graph.objects(prop, RDFS.range):
                if isinstance(r, URIRef):
                    range_ = self._get_local_name(r)
                    break

            inverse_of = None
            for inv in self.graph.objects(prop, OWL.inverseOf):
                if isinstance(inv, URIRef):
                    inverse_of = self._get_local_name(inv)
                    break

            is_symmetric = (prop, RDF.type, OWL.SymmetricProperty) in self.graph
            is_functional = (prop, RDF.type, OWL.FunctionalProperty) in self.graph

            self.object_properties[name] = OntologyProperty(
                uri=str(prop),
                name=name,
                label_ko=self._get_label_ko(prop),
                domain=domain,
                range=range_,
                is_object_property=True,
                is_symmetric=is_symmetric,
                is_functional=is_functional,
                inverse_of=inverse_of,
            )

        # Datatype Property 파싱
        for prop in self.graph.subjects(RDF.type, OWL.DatatypeProperty):
            if not isinstance(prop, URIRef):
                continue
            name = self._get_local_name(prop)

            domain = None
            for d in self.graph.objects(prop, RDFS.domain):
                if isinstance(d, URIRef):
                    domain = self._get_local_name(d)
                    break

            range_ = None
            for r in self.graph.objects(prop, RDFS.range):
                if isinstance(r, URIRef):
                    range_ = self._get_local_name(r)
                    break

            is_functional = (prop, RDF.type, OWL.FunctionalProperty) in self.graph

            self.datatype_properties[name] = OntologyProperty(
                uri=str(prop),
                name=name,
                label_ko=self._get_label_ko(prop),
                domain=domain,
                range=range_,
                is_object_property=False,
                is_functional=is_functional,
            )


class DiagramGenerator:
    """다이어그램 생성기"""

    def __init__(self, parser: OntologyParser):
        self.parser = parser

    def generate_mermaid(self) -> str:
        """Mermaid 다이어그램 생성"""
        lines = ["```mermaid", "erDiagram"]

        # 클래스 정의 (속성 포함)
        for cls_name, cls in self.parser.classes.items():
            # 주요 클래스만 표시 (Category 하위 제외)
            if cls.parent and cls.parent == "Category":
                continue
            if cls_name == "Category":
                continue

            # 해당 클래스의 datatype properties 수집
            props = []
            for prop_name, prop in self.parser.datatype_properties.items():
                if prop.domain == cls_name:
                    range_type = prop.range or "string"
                    if "#" in range_type:
                        range_type = range_type.split("#")[-1]
                    props.append(f"        {range_type} {prop_name}")

            if props:
                lines.append(f"    {cls_name} {{")
                lines.extend(props)
                lines.append("    }")

        lines.append("")

        # 관계 정의
        seen_relations = set()
        for prop_name, prop in self.parser.object_properties.items():
            if not prop.domain or not prop.range:
                continue

            # 역방향 속성은 건너뛰기 (중복 방지)
            if prop.inverse_of and prop.inverse_of in seen_relations:
                continue

            # Category 관련 건너뛰기
            if "Category" in (prop.domain, prop.range):
                continue

            domain = prop.domain
            range_ = prop.range

            # 관계 카디널리티 결정
            if prop.is_functional:
                if prop.is_symmetric:
                    cardinality = "}o--o{"
                else:
                    cardinality = "}|--||"
            else:
                if prop.is_symmetric:
                    cardinality = "}o--o{"
                else:
                    cardinality = "||--o{"

            label = prop.label_ko or prop_name
            lines.append(f"    {domain} {cardinality} {range_} : {label}")
            seen_relations.add(prop_name)

        lines.append("```")
        return "\n".join(lines)

    def generate_mermaid_class_diagram(self) -> str:
        """Mermaid 클래스 다이어그램 (상세 버전)"""
        lines = ["```mermaid", "classDiagram"]

        # 클래스 계층 구조
        for cls_name, cls in self.parser.classes.items():
            if cls.parent and cls.parent not in ("Thing", "Person", "Product"):
                lines.append(f"    {cls.parent} <|-- {cls_name}")

        lines.append("")

        # 클래스 정의 (속성 포함)
        for cls_name, cls in self.parser.classes.items():
            if cls.parent and cls.parent == "Category":
                continue

            lines.append(f"    class {cls_name} {{")

            # Datatype properties
            for prop_name, prop in self.parser.datatype_properties.items():
                if prop.domain == cls_name:
                    range_type = prop.range or "string"
                    if "#" in range_type:
                        range_type = range_type.split("#")[-1]
                    func_mark = "*" if prop.is_functional else ""
                    lines.append(f"        +{range_type} {prop_name}{func_mark}")

            lines.append("    }")

        lines.append("")

        # 관계
        seen = set()
        for prop_name, prop in self.parser.object_properties.items():
            if not prop.domain or not prop.range:
                continue
            if prop.inverse_of and prop.inverse_of in seen:
                continue
            if "Category" in (prop.domain, prop.range):
                continue

            arrow = "--" if prop.is_symmetric else "-->"
            label = prop.label_ko or prop_name
            lines.append(f"    {prop.domain} {arrow} {prop.range} : {label}")
            seen.add(prop_name)

        lines.append("```")
        return "\n".join(lines)

    def generate_dot(self) -> str:
        """GraphViz DOT 형식 생성"""
        lines = [
            "digraph Ontology {",
            "    rankdir=TB;",
            "    node [shape=record, fontname=\"Malgun Gothic\"];",
            "    edge [fontname=\"Malgun Gothic\"];",
            "",
        ]

        # 클래스 노드
        for cls_name, cls in self.parser.classes.items():
            if cls.parent and cls.parent == "Category":
                continue
            if cls_name == "Category":
                continue

            # 속성 수집
            props = []
            for prop_name, prop in self.parser.datatype_properties.items():
                if prop.domain == cls_name:
                    label_ko = prop.label_ko or prop_name
                    props.append(f"{label_ko}")

            label_ko = cls.label_ko or cls_name
            if props:
                props_str = "\\l".join(props) + "\\l"
                label = f"{{{label_ko}|{props_str}}}"
            else:
                label = label_ko

            lines.append(f'    {cls_name} [label="{label}"];')

        lines.append("")

        # 관계 엣지
        seen = set()
        for prop_name, prop in self.parser.object_properties.items():
            if not prop.domain or not prop.range:
                continue
            if prop.inverse_of and prop.inverse_of in seen:
                continue
            if "Category" in (prop.domain, prop.range):
                continue

            label = prop.label_ko or prop_name
            style = ', dir="both"' if prop.is_symmetric else ""
            lines.append(
                f'    {prop.domain} -> {prop.range} [label="{label}"{style}];'
            )
            seen.add(prop_name)

        lines.append("}")
        return "\n".join(lines)

    def generate_html(self) -> str:
        """인터랙티브 HTML 뷰어 생성 (vis.js 사용)"""
        # 노드 데이터
        nodes = []
        for cls_name, cls in self.parser.classes.items():
            if cls.parent and cls.parent == "Category":
                continue
            if cls_name == "Category":
                continue

            label = cls.label_ko or cls_name
            nodes.append({"id": cls_name, "label": label, "title": cls_name})

        # 엣지 데이터
        edges = []
        seen = set()
        for prop_name, prop in self.parser.object_properties.items():
            if not prop.domain or not prop.range:
                continue
            if prop.inverse_of and prop.inverse_of in seen:
                continue
            if "Category" in (prop.domain, prop.range):
                continue

            label = prop.label_ko or prop_name
            edge = {
                "from": prop.domain,
                "to": prop.range,
                "label": label,
                "arrows": "to" if not prop.is_symmetric else "to, from",
            }
            edges.append(edge)
            seen.add(prop_name)

        nodes_json = json.dumps(nodes, ensure_ascii=False, indent=2)
        edges_json = json.dumps(edges, ensure_ascii=False, indent=2)

        html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>E-Commerce 온톨로지 다이어그램</title>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Malgun Gothic', sans-serif; background: #1a1a2e; }}
        h1 {{ color: #eee; text-align: center; padding: 20px; }}
        #network {{ width: 100%; height: calc(100vh - 80px); }}
        .legend {{
            position: fixed; bottom: 20px; right: 20px;
            background: rgba(255,255,255,0.9); padding: 15px;
            border-radius: 8px; font-size: 12px;
        }}
    </style>
</head>
<body>
    <h1>E-Commerce 온톨로지 구조</h1>
    <div id="network"></div>
    <div class="legend">
        <strong>범례</strong><br>
        노드: 클래스 (엔티티)<br>
        엣지: Object Property (관계)<br>
        양방향 화살표: 대칭 관계
    </div>
    <script>
        const nodes = new vis.DataSet({nodes_json});
        const edges = new vis.DataSet({edges_json});

        const container = document.getElementById('network');
        const data = {{ nodes: nodes, edges: edges }};
        const options = {{
            nodes: {{
                shape: 'box',
                color: {{
                    background: '#4a69bd',
                    border: '#1e3799',
                    highlight: {{ background: '#6a89cc', border: '#1e3799' }}
                }},
                font: {{ color: '#fff', size: 14 }},
                margin: 10
            }},
            edges: {{
                color: '#78e08f',
                font: {{ size: 11, color: '#aaa', align: 'middle' }},
                smooth: {{ type: 'curvedCW', roundness: 0.2 }}
            }},
            physics: {{
                enabled: true,
                solver: 'forceAtlas2Based',
                forceAtlas2Based: {{
                    gravitationalConstant: -50,
                    centralGravity: 0.01,
                    springLength: 150,
                    springConstant: 0.08
                }}
            }},
            interaction: {{
                hover: true,
                navigationButtons: true,
                keyboard: true
            }}
        }};

        const network = new vis.Network(container, data, options);
    </script>
</body>
</html>"""
        return html

    def generate_markdown_doc(self) -> str:
        """온톨로지 문서 (마크다운)"""
        lines = [
            "# E-Commerce 온톨로지 구조",
            "",
            "## 개요",
            "",
            f"- **클래스 수**: {len(self.parser.classes)}",
            f"- **Object Property 수**: {len(self.parser.object_properties)}",
            f"- **Datatype Property 수**: {len(self.parser.datatype_properties)}",
            "",
            "## 클래스 관계도 (ER Diagram)",
            "",
            self.generate_mermaid(),
            "",
            "## 클래스 상세도 (Class Diagram)",
            "",
            self.generate_mermaid_class_diagram(),
            "",
            "## 클래스 목록",
            "",
            "| 클래스 | 한국어 | 부모 클래스 |",
            "|--------|--------|-------------|",
        ]

        for cls_name, cls in sorted(self.parser.classes.items()):
            parent = cls.parent or "-"
            label = cls.label_ko or "-"
            lines.append(f"| `{cls_name}` | {label} | {parent} |")

        lines.extend(
            [
                "",
                "## Object Property 목록",
                "",
                "| 속성 | 한국어 | Domain → Range | 특성 |",
                "|------|--------|----------------|------|",
            ]
        )

        for prop_name, prop in sorted(self.parser.object_properties.items()):
            label = prop.label_ko or "-"
            domain = prop.domain or "*"
            range_ = prop.range or "*"
            features = []
            if prop.is_symmetric:
                features.append("대칭")
            if prop.is_functional:
                features.append("함수형")
            if prop.inverse_of:
                features.append(f"역: {prop.inverse_of}")
            features_str = ", ".join(features) if features else "-"
            lines.append(f"| `{prop_name}` | {label} | {domain} → {range_} | {features_str} |")

        lines.extend(
            [
                "",
                "## Datatype Property 목록",
                "",
                "| 속성 | 한국어 | Domain | Range | 함수형 |",
                "|------|--------|--------|-------|--------|",
            ]
        )

        for prop_name, prop in sorted(self.parser.datatype_properties.items()):
            label = prop.label_ko or "-"
            domain = prop.domain or "*"
            range_ = prop.range or "string"
            if "#" in range_:
                range_ = range_.split("#")[-1]
            func = "O" if prop.is_functional else "-"
            lines.append(f"| `{prop_name}` | {label} | {domain} | {range_} | {func} |")

        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="온톨로지 다이어그램 생성")
    parser.add_argument(
        "--format",
        choices=["mermaid", "dot", "html", "markdown", "all"],
        default="all",
        help="출력 형식",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="출력 파일 경로 (기본: docs/images/)",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=ONTOLOGY_FILE,
        help="입력 TTL 파일",
    )
    args = parser.parse_args()

    # 출력 디렉토리 생성
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"온톨로지 파싱: {args.input}")
    ont_parser = OntologyParser(args.input)
    generator = DiagramGenerator(ont_parser)

    print(f"  - 클래스: {len(ont_parser.classes)}개")
    print(f"  - Object Properties: {len(ont_parser.object_properties)}개")
    print(f"  - Datatype Properties: {len(ont_parser.datatype_properties)}개")

    outputs = []

    if args.format in ("mermaid", "all"):
        content = generator.generate_mermaid()
        path = args.output or OUTPUT_DIR / "ontology-er.md"
        path.write_text(content, encoding="utf-8")
        outputs.append(path)
        print(f"Mermaid ER: {path}")

    if args.format in ("dot", "all"):
        content = generator.generate_dot()
        path = OUTPUT_DIR / "ontology.dot"
        path.write_text(content, encoding="utf-8")
        outputs.append(path)
        print(f"GraphViz DOT: {path}")

        # DOT → PNG 변환 시도
        try:
            png_path = OUTPUT_DIR / "ontology.png"
            result = subprocess.run(
                ["dot", "-Tpng", str(path), "-o", str(png_path)],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                outputs.append(png_path)
                print(f"PNG 이미지: {png_path}")
            else:
                print(f"  (PNG 변환 실패: GraphViz 설치 필요)")
        except FileNotFoundError:
            print(f"  (PNG 변환 건너뜀: GraphViz 미설치)")

    if args.format in ("html", "all"):
        content = generator.generate_html()
        path = OUTPUT_DIR / "ontology-viewer.html"
        path.write_text(content, encoding="utf-8")
        outputs.append(path)
        print(f"HTML 뷰어: {path}")

    if args.format in ("markdown", "all"):
        content = generator.generate_markdown_doc()
        path = OUTPUT_DIR / "ontology-docs.md"
        path.write_text(content, encoding="utf-8")
        outputs.append(path)
        print(f"마크다운 문서: {path}")

    print(f"\n총 {len(outputs)}개 파일 생성 완료")


if __name__ == "__main__":
    main()
