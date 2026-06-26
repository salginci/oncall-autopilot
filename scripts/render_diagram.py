from playwright.sync_api import sync_playwright
from pathlib import Path

html_file = Path(__file__).parent / "diagram.html"
output_file = Path(__file__).parent.parent / "architecture.png"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    page.goto(f"file://{html_file.absolute()}")

    page.wait_for_selector("svg", timeout=15000)
    page.wait_for_timeout(2000)

    mermaid_svg = page.query_selector(".mermaid svg")
    if mermaid_svg:
        box = mermaid_svg.bounding_box()
        if box:
            page.set_viewport_size({"width": int(box["width"]) + 80, "height": int(box["height"]) + 200})
            mermaid_svg.screenshot(path=str(output_file))
            print(f"Saved SVG: {output_file} ({output_file.stat().st_size} bytes)")

    full_output = output_file.parent / "architecture_full.png"
    page.set_viewport_size({"width": 1600, "height": 1200})
    page.screenshot(path=str(full_output), full_page=True)
    print(f"Saved full: {full_output} ({full_output.stat().st_size} bytes)")

    browser.close()
