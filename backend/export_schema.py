"""
export_schema.py — Generates OpenAPI schema and frontend contract definitions from FastAPI.
Guarantees frontend types and backend schema cannot drift (Stage 4.2).
"""

import json
import os
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent
proj_root = backend_dir.parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(proj_root))

from main import app

def generate_typescript_type(name: str, schema: dict) -> str:
    """Convert an OpenAPI schema object to a TypeScript interface/type."""
    props = schema.get("properties", {})
    required = schema.get("required", [])
    lines = [f"export interface {name} {{"]
    
    for prop_name, prop_def in props.items():
        is_opt = "?" if prop_name not in required else ""
        t_type = "any"
        p_type = prop_def.get("type")
        ref = prop_def.get("$ref")
        
        if ref:
            t_type = ref.split("/")[-1]
        elif p_type == "string":
            t_type = "string"
        elif p_type in ("number", "integer"):
            t_type = "number"
        elif p_type == "boolean":
            t_type = "boolean"
        elif p_type == "array":
            items = prop_def.get("items", {})
            item_ref = items.get("$ref")
            if item_ref:
                t_type = f"{item_ref.split('/')[-1]}[]"
            else:
                item_type = items.get("type", "any")
                t_type = "number[]" if item_type in ("number", "integer") else f"{item_type}[]"
        elif p_type == "object":
            t_type = "Record<string, any>"
            
        desc = prop_def.get("description", "")
        if desc:
            lines.append(f"  /** {desc} */")
        lines.append(f"  {prop_name}{is_opt}: {t_type};")
        
    lines.append("}\n")
    return "\n".join(lines)


def export_all():
    docs_dir = proj_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    frontend_dir = proj_root / "frontend"
    frontend_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. OpenAPI JSON
    openapi_schema = app.openapi()
    openapi_path = docs_dir / "openapi.json"
    with open(openapi_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)
    print(f"[EXPORT] Wrote OpenAPI schema: {openapi_path} ({len(openapi_schema.get('paths', {}))} paths)")

    # 2. TypeScript Definitions (contracts.d.ts)
    schemas = openapi_schema.get("components", {}).get("schemas", {})
    ts_lines = [
        "/**",
        " * AETHER-X v0.5 Pure Physics & API Type Definitions",
        " * Auto-generated from FastAPI OpenAPI schema. DO NOT HAND EDIT.",
        " */\n"
    ]
    
    for schema_name, schema_def in sorted(schemas.items()):
        ts_lines.append(generate_typescript_type(schema_name, schema_def))
        
    ts_path = frontend_dir / "contracts.d.ts"
    with open(ts_path, "w", encoding="utf-8") as f:
        f.write("\n".join(ts_lines))
    print(f"[EXPORT] Wrote TypeScript contracts: {ts_path} ({len(schemas)} schemas)")

    # 3. JavaScript Contract Validator Map (contracts.js)
    js_lines = [
        "/**",
        " * AETHER-X v0.5 Frontend Contract Registry",
        " * Auto-generated from backend schema to enforce zero type drift.",
        " */",
        "window.AETHERX_CONTRACTS = {",
        f"  version: '{openapi_schema.get('info', {}).get('version', '0.5.0')}',",
        f"  title: '{openapi_schema.get('info', {}).get('title', 'AETHER-X')}',",
        f"  schemas: {json.dumps(list(schemas.keys()))}",
        "};\n"
    ]
    js_path = frontend_dir / "contracts.js"
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("\n".join(js_lines))
    print(f"[EXPORT] Wrote JavaScript contracts: {js_path}")

if __name__ == "__main__":
    export_all()
