# Security.py

import os

# --- 可配置的变量 ---
# 将来这些变量可以从配置文件、版本文件或环境变量中动态读取
PROJECT_NAME = "Yquoter"
CONTACT_EMAIL = "[2729147823@qq.com]"
SUPPORTED_VERSION = "1.0.x"  # 示例版本号

# --- Markdown 模板 ---
# 使用 f-string 格式化字符串，方便将变量嵌入模板中
SECURITY_TEMPLATE = f"""
# {PROJECT_NAME} 项目安全策略 (Security Policy)

## 支持的版本 (Supported Versions)

我们承诺为以下版本提供安全更新。请尽量使用最新版本。

| Version | Supported          |
| ------- | ------------------ |
| {SUPPORTED_VERSION}   | :white_check_mark: |
| < 1.0   | :x:                |

## 报告漏洞 (Reporting a Vulnerability)

我们非常重视 **{PROJECT_NAME}** 项目的安全性。如果您在项目中发现了安全漏洞，我们非常感谢您的帮助，并希望您能负责任地向我们披露。

**请不要在公开的 GitHub Issues 中提交安全漏洞问题。**

请通过以下方式将您发现的漏洞私下报告给我们：

1.  **发送电子邮件**至：**`{CONTACT_EMAIL}`**
2.  邮件标题请以 `[SECURITY] {PROJECT_NAME} Vulnerability Report:` 开头。
3.  请在邮件中尽可能详细地包含以下信息：
    * 漏洞的描述，包括它可能造成的影响。
    * 重现该漏洞的详细步骤（包括代码示例、配置等）。
    * 您所使用的 **{PROJECT_NAME}** 项目版本。

我们收到报告后，会尽快确认问题，在一个工作日内给予初步回复，并与您保持沟通，告知您我们的修复计划和进度。我们对所有帮助我们提升 **{PROJECT_NAME}** 项目安全性的研究人员表示诚挚的感谢。
"""


def generate_security_md():
    """
    生成 SECURITY.md 文件的主函数。
    """
    file_name = "SECURITY.md"

    print(f"正在生成 {file_name} 文件...")

    # 【异常处理】使用 try...except 块来处理可能发生的文件写入错误
    try:
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(SECURITY_TEMPLATE.strip())
        print(f"✅ 文件 {file_name} 已成功生成在项目根目录！")

    except IOError as e:
        print(f"❌ 错误：无法写入文件 {file_name}。")
        print(f"   原因: {e}")


# 当直接运行这个脚本时，执行生成函数
if __name__ == "__main__":
    # 1. 【重要】在运行前，请确保您已经修改了上面 CONTACT_EMAIL 的值
    if "[请在此处填写您或团队的联系邮箱]" in CONTACT_EMAIL:
        print("⚠️ 警告：请先在脚本中修改 CONTACT_EMAIL 变量的值！")
    else:
        generate_security_md()