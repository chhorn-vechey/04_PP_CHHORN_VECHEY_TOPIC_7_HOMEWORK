import html
import subprocess
from playwright.sync_api import sync_playwright


def generate_artifacts() -> None:
    print("Running agent demo to capture output...")
    proc = subprocess.run(
        ["python", "main.py", "--demo"],
        capture_output=True,
        text=True,
        encoding="utf-8"
    )
    terminal_text = proc.stdout

    with open("terminal_output.txt", "w", encoding="utf-8") as f:
        f.write(terminal_text)

    escaped_text = html.escape(terminal_text)

    # Style keywords with terminal colors
    colored_html = (
        escaped_text
        .replace("&gt;&gt;&gt; Scenario", "<span class='hl-cyan'>&gt;&gt;&gt; Scenario</span>")
        .replace("User Request :", "<span class='hl-yellow'>User Request :</span>")
        .replace("Active Role  :", "<span class='hl-purple'>Active Role  :</span>")
        .replace("LLM Provider :", "<span class='hl-blue'>LLM Provider :</span>")
        .replace("Agent Reasoning...", "<span class='hl-blue'>Agent Reasoning...</span>")
        .replace("Decision: Propose Tool", "<span class='hl-green'>Decision: Propose Tool</span>")
        .replace("Decision: Final Answer", "<span class='hl-green'>Decision: Final Answer</span>")
        .replace("Harness : Checked", "<span class='hl-purple'>Harness : Checked</span>")
        .replace("Status: success", "<span class='hl-success'>Status: success</span>")
        .replace("Status: error", "<span class='hl-danger'>Status: error</span>")
        .replace("Validation Result:", "<span class='hl-yellow'>Validation Result:</span>")
    )

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Agent Execution Output</title>
  <style>
    body {{
      background: #0d1117;
      color: #c9d1d9;
      font-family: 'Consolas', 'Fira Code', 'Courier New', monospace;
      padding: 30px;
      margin: 0;
      display: flex;
      justify-content: center;
    }}
    .terminal-window {{
      background: #161b22;
      border: 1px solid #30363d;
      border-radius: 12px;
      box-shadow: 0 20px 40px rgba(0,0,0,0.6);
      width: 950px;
      overflow: hidden;
    }}
    .terminal-header {{
      background: #21262d;
      padding: 12px 18px;
      display: flex;
      align-items: center;
      border-bottom: 1px solid #30363d;
    }}
    .dots {{
      display: flex;
      gap: 8px;
    }}
    .dot {{
      width: 12px;
      height: 12px;
      border-radius: 50%;
    }}
    .dot-red {{ background: #ff5f56; }}
    .dot-yellow {{ background: #ffbd2e; }}
    .dot-green {{ background: #27c93f; }}
    .terminal-title {{
      flex: 1;
      text-align: center;
      font-size: 13px;
      color: #8b949e;
      font-weight: 600;
    }}
    .terminal-body {{
      padding: 24px;
      font-size: 14px;
      line-height: 1.5;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .hl-cyan {{ color: #58a6ff; font-weight: bold; }}
    .hl-yellow {{ color: #f2cc60; font-weight: bold; }}
    .hl-purple {{ color: #bc8cff; font-weight: bold; }}
    .hl-blue {{ color: #79c0ff; }}
    .hl-green {{ color: #7ee787; font-weight: bold; }}
    .hl-success {{ color: #56d364; font-weight: bold; }}
    .hl-danger {{ color: #f85149; font-weight: bold; }}
  </style>
</head>
<body>
  <div class="terminal-window">
    <div class="terminal-header">
      <div class="dots">
        <div class="dot dot-red"></div>
        <div class="dot dot-yellow"></div>
        <div class="dot dot-green"></div>
      </div>
      <div class="terminal-title">bash - python main.py --demo (Topic 07 Safe Agent Execution)</div>
    </div>
    <div class="terminal-body">{colored_html}</div>
  </div>
</body>
</html>
"""

    with open("terminal_view.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    print("Rendering screenshot and PDF via Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1050, "height": 1800})
        page.set_content(html_content)
        page.wait_for_load_state("networkidle")

        page.screenshot(path="screenshot_terminal_output.png", full_page=True)
        page.pdf(path="terminal_output.pdf", print_background=True, format="A4")
        browser.close()

    print("Successfully generated:")
    print("  - terminal_output.txt")
    print("  - terminal_view.html")
    print("  - screenshot_terminal_output.png")
    print("  - terminal_output.pdf")


if __name__ == "__main__":
    generate_artifacts()
