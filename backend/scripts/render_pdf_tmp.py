"""临时脚本：渲染策划书 PDF 页面为 PNG（供视觉阅读）"""

import os

import fitz

PDF = r"D:\电脑管家迁移文件\微信聊天记录搬家\WeChat Files\wxid_xlfaftb3juwb12\FileStorage\Temp\Copy\策划书（pdf版）.pdf"
OUTDIR = r"D:\AI Program\仓维云-agent\tmp_pdf"


def main() -> None:
    os.makedirs(OUTDIR, exist_ok=True)
    pdf = fitz.open(PDF)
    start, end = 23, min(32, len(pdf))
    for i in range(start, end):
        pix = pdf[i].get_pixmap(dpi=110)
        pix.save(os.path.join(OUTDIR, f"page_{i + 1:02d}.png"))
    print(f"已渲染 {end} 页，总页数 {len(pdf)}")


if __name__ == "__main__":
    main()
