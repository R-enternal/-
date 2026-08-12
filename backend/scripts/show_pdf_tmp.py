"""临时脚本：按关键词定位并打印 OCR 结果中相关页面"""

import os

path = os.path.join(os.environ.get("TEMP", ""), "plan2_ocr.txt")
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

pages = content.split("===== ")
for block in pages:
    lines = block.splitlines()
    if not lines:
        continue
    header = lines[0]
    body = "".join(lines[1:]).replace(" ", "")
    if any(k in body for k in ("技术介绍", "产品与功能", "系统架构设计", "未来科技导航", "产品特点", "产品优势", "核心技术")):
        print(f"\n########## {header} ##########")
        print(body[:2500])
