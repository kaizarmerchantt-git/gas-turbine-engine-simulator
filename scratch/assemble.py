import os
import sys

# Add current scratch dir to sys.path
scratch_dir = os.path.dirname(__file__)
if scratch_dir not in sys.path:
    sys.path.insert(0, scratch_dir)

from gen_css import CSS_CONTENT
from gen_common_components import COMMON_COMPONENTS
from gen_domains_1_to_4 import DOMAINS_1_TO_4
from gen_domains_5_to_9 import DOMAINS_5_TO_9
from gen_app import APP_MAIN

def assemble():
    proj_dir = os.path.dirname(scratch_dir)
    frontend_dir = os.path.join(proj_dir, "frontend")
    target_v05 = os.path.join(frontend_dir, "index_v0.5.html")
    target_index = os.path.join(frontend_dir, "index.html")
    legacy_backup = os.path.join(frontend_dir, "index_v0.4_legacy.html")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AETHER-X // AEROSPACE PROPULSION & MISSION ANALYSIS SUITE (v0.5.0 OBSIDIAN BLUEPRINT)</title>

  <!-- Typography: Inter, JetBrains Mono & Share Tech Mono -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@300;400;500;600;700;800&family=Share+Tech+Mono&display=swap" rel="stylesheet">

  <!-- React 18, Babel Standalone & Chart.js 4 -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/react/18.2.0/umd/react.production.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.2.0/umd/react-dom.production.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/babel-standalone/7.23.10/babel.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>

  <style>
{CSS_CONTENT}
  </style>
</head>
<body>
  <div id="root"></div>

  <script type="text/babel">
{COMMON_COMPONENTS}
{DOMAINS_1_TO_4}
{DOMAINS_5_TO_9}
{APP_MAIN}
  </script>
</body>
</html>
"""

    # Backup legacy index.html if backup doesn't exist
    if os.path.exists(target_index) and not os.path.exists(legacy_backup):
        import shutil
        shutil.copyfile(target_index, legacy_backup)
        print(f"Backed up legacy frontend to {legacy_backup}")

    # Write index_v0.5.html
    with open(target_v05, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Successfully assembled {target_v05} ({len(html)} bytes, {len(html.splitlines())} lines).")

    # Also overwrite index.html so default browser / static root loads Obsidian Blueprint immediately
    with open(target_index, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Successfully updated default {target_index} ({len(html)} bytes).")

if __name__ == "__main__":
    assemble()
