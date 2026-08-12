"""临时脚本：用 GLM-4V 视觉模型识别 PDF 页面中的系统架构图"""

import base64
import os
import sys
from pathlib import Path

from openai import OpenAI

IMG_DIR = Path(r"D:\AI Program\仓维云-agent\tmp_pdf")

PROMPT = """这是商业计划书的页面截图。请仔细识别：
1. 页面中是否包含"系统架构图/架构层次图/系统总体架构"之类的架构图？
2. 如果有，请详细描述这张图：图中有哪些层级（如感知层/传输层/平台层/应用层等）、
   每一层包含哪些模块或组件、模块之间的连接关系（上下级/箭头方向）、
   图中所有可见的文字标签（设备名、模块名、协议名等）。
3. 如果页面没有架构图，请直接回答"本页无架构图"。
请用中文回答，尽量完整列出图中的文字。"""


def encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def ask_glm(page_no: int) -> str:
    img_path = IMG_DIR / f"page_{page_no:02d}.png"
    if not img_path.exists():
        return f"页面图片不存在: {img_path}"
    client = OpenAI(
        api_key=os.environ.get("ZHIPU_API_KEY", ""),
        base_url="https://open.bigmodel.cn/api/paas/v4/",
    )
    resp = client.chat.completions.create(
        model="glm-4v-flash",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encode_image(img_path)}"}},
                    {"type": "text", "text": PROMPT},
                ],
            }
        ],
        temperature=0.1,
    )
    return resp.choices[0].message.content or ""


def main() -> None:
    pages = [int(x) for x in sys.argv[1:]] or [30, 31, 32]
    for page_no in pages:
        print(f"\n===== page_{page_no:02d} =====")
        try:
            print(ask_glm(page_no))
        except Exception as exc:  # noqa: BLE001
            print(f"识别失败: {exc}")


if __name__ == "__main__":
    main()
