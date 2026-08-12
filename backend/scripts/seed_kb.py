"""知识库演示数据：灌入《设备维保手册》"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import kb_service  # noqa: E402

KB_DOC = Path(__file__).resolve().parents[1] / "kb_docs" / "设备维保手册.md"


def main() -> None:
    if not KB_DOC.exists():
        print(f"找不到演示文档: {KB_DOC}")
        return
    content = KB_DOC.read_text(encoding="utf-8")
    result = kb_service.ingest_text(KB_DOC.name, content, doc_type="MD", created_by="seed")
    print(f"知识库演示文档入库完成：切块 {result.get('chunks', 0)} 个")


if __name__ == "__main__":
    main()
