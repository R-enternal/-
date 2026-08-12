"""临时脚本：用 pypdf 提取文本；失败则输出提示改用 OCR"""

from pypdf import PdfReader

PDF = r"D:\电脑管家迁移文件\微信聊天记录搬家\WeChat Files\wxid_xlfaftb3juwb12\FileStorage\Temp\Copy\策划书（pdf版）.pdf"
OUT = r"D:\AI Program\仓维云-agent\tmp_plan2.txt"


def main() -> None:
    reader = PdfReader(PDF)
    parts = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        parts.append(f"\n===== 第{i + 1}页 =====\n{text}")
    total = sum(len(p) for p in parts)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print(f"pypdf 提取完成，总字符 {total}")


if __name__ == "__main__":
    main()
