"""
validation_baseline/run_validation_baseline.py
OMS 本機驗證基準模組。

提供 run_local_guard.py 所需的全部驗證函式：
  run_compileall()          — Python 語法編譯檢查
  run_import_smoke()        — 核心模組 import 可行性檢查
  run_router_smoke()        — 路由表完整性與可解析性檢查
  run_export_checks()       — pages/__init__.py __all__ 匯出可用性檢查
  scan_page_layer_violations() — page 層邊界違規掃描
  summarize(results)        — 匯總所有結果

不依賴 Supabase 或網路連線。
"""
from __future__ import annotations

import ast
import compileall
import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# 1. compileall
# ---------------------------------------------------------------------------

def run_compileall() -> dict[str, Any]:
    ok = compileall.compile_dir(
        str(PROJECT_ROOT),
        quiet=2,
        force=True,
        workers=1,
    )
    return {"ok": bool(ok)}


# ---------------------------------------------------------------------------
# 2. import smoke
# ---------------------------------------------------------------------------

# 需要能成功 import 的核心模組清單
_SMOKE_MODULES: list[str] = [
    "shared.services.table_contract",
    "shared.services.data_backend",
    "shared.services.service_id",
    "shared.services.service_order_core",
    "shared.services.service_audit",
    "data_management.services.service_purchase",
    "data_management.logic.logic_purchase_settings",
    "operations.logic.order_write_rpc",
    "operations.logic.order_write",
    "operations.pages",
    "data_management.pages",
    "analysis.pages",
    "users_permissions.pages",
    "system.pages",
]


@dataclass
class ImportSmokeResult:
    ok: bool
    module: str
    error_type: str
    error_message: str


def run_import_smoke() -> list[ImportSmokeResult]:
    results: list[ImportSmokeResult] = []
    for mod in _SMOKE_MODULES:
        try:
            importlib.import_module(mod)
            results.append(ImportSmokeResult(ok=True, module=mod, error_type="", error_message=""))
        except Exception as e:
            results.append(ImportSmokeResult(
                ok=False,
                module=mod,
                error_type=type(e).__name__,
                error_message=str(e),
            ))
    return results


# ---------------------------------------------------------------------------
# 3. router smoke
# ---------------------------------------------------------------------------

# 路由表基準（對應 shared/core/app_shell.py 的 routes dict）
_EXPECTED_ROUTES: dict[str, str] = {
    "select_store":        "operations.pages.page_select_store",
    "select_vendor":       "operations.pages.page_select_vendor",
    "order_entry":         "operations.pages.page_order",
    "order_message_detail":"operations.pages.page_order_message_detail",
    "export":              "analysis.pages.page_export",
    "stock_order_compare": "analysis.pages.page_stock_order_compare",
    "analysis":            "analysis.pages.page_analysis",
    "view_history":        "analysis.pages.page_view_history",
    "cost_debug":          "analysis.pages.page_cost_debug",
    "appearance_settings": "system.pages.page_appearance_settings",
    "system_info":         "system.pages.page_system_info",
    "system_maintenance":  "system.pages.page_system_maintenance",
    "system_tools":        "system.pages.page_system_tools",
    "user_admin":          "users_permissions.pages.page_user_admin",
    "account_settings":    "users_permissions.pages.page_account_settings",
    "purchase_settings":   "data_management.pages.page_purchase_settings",
    "store_admin":         "users_permissions.pages.page_store_admin",
}


def _resolve_dotted(dotted: str) -> tuple[bool, str]:
    """嘗試解析 'pkg.module.symbol'，回傳 (ok, error_message)。"""
    parts = dotted.rsplit(".", 1)
    if len(parts) != 2:
        return False, f"cannot split: {dotted}"
    mod_path, symbol = parts
    try:
        mod = importlib.import_module(mod_path)
        if not hasattr(mod, symbol):
            return False, f"{symbol} not found in {mod_path}"
        return True, ""
    except Exception as e:
        return False, str(e)


def run_router_smoke() -> dict[str, Any]:
    checks = []
    for route_key, target in _EXPECTED_ROUTES.items():
        ok, err = _resolve_dotted(target)
        checks.append({"ok": ok, "route_key": route_key, "target": target, "error": err})

    # owner_verify is in app_runtime (optional — warn only)
    try:
        from shared.core import app_runtime as _ar
        has_owner_verify = hasattr(_ar, "page_owner_verify")
    except Exception:
        has_owner_verify = False
    checks.append({
        "ok": has_owner_verify,
        "route_key": "owner_verify",
        "target": "shared.core.app_runtime.page_owner_verify",
        "error": "" if has_owner_verify else "page_owner_verify not found in app_runtime",
    })

    # extra / missing keys: compare resolved route_keys vs expected
    resolved_keys = {c["route_key"] for c in checks}
    expected_keys = set(_EXPECTED_ROUTES.keys()) | {"owner_verify"}
    extra_keys = sorted(resolved_keys - expected_keys)
    missing_keys = sorted(expected_keys - resolved_keys)

    return {
        "ok": all(c["ok"] for c in checks),
        "checks": checks,
        "extra_keys": extra_keys,
        "missing_keys": missing_keys,
    }


# ---------------------------------------------------------------------------
# 4. export checks
# ---------------------------------------------------------------------------

# 各 pages package 應匯出的 symbol 清單
_PAGE_EXPORTS: dict[str, list[str]] = {
    "operations.pages": [
        "page_select_store",
        "page_select_vendor",
        "page_order",
        "page_order_result",
        "page_order_message_detail",
    ],
    "data_management.pages": [
        "page_purchase_settings",
    ],
    "analysis.pages": [
        "page_export_report",
        "page_inventory_analysis",
        "page_order_history",
        "page_analysis",
        "page_cost_debug",
        "page_export",
        "page_stock_order_compare",
        "page_view_history",
    ],
    "users_permissions.pages": [
        "page_account_settings",
        "page_login",
        "page_store_admin",
        "page_user_admin",
        "render_login_sidebar",
    ],
    "system.pages": [
        "page_appearance_settings",
        "page_system_info",
        "page_system_maintenance",
        "page_system_tools",
    ],
}


@dataclass
class ExportCheckResult:
    ok: bool
    package: str
    export_name: str
    detail: str


def run_export_checks() -> list[ExportCheckResult]:
    results: list[ExportCheckResult] = []
    for package, symbols in _PAGE_EXPORTS.items():
        try:
            mod = importlib.import_module(package)
        except Exception as e:
            for sym in symbols:
                results.append(ExportCheckResult(
                    ok=False, package=package, export_name=sym,
                    detail=f"import failed: {e}",
                ))
            continue
        for sym in symbols:
            if hasattr(mod, sym):
                results.append(ExportCheckResult(ok=True, package=package, export_name=sym, detail=""))
            else:
                results.append(ExportCheckResult(
                    ok=False, package=package, export_name=sym,
                    detail=f"{sym} not in {package}",
                ))
    return results


# ---------------------------------------------------------------------------
# 5. page layer violations
# ---------------------------------------------------------------------------

# page 不可直接呼叫的函式前綴
_FORBIDDEN_CALL_PREFIXES = ("create_", "update_", "reset_", "send_")

# page 不可直接呼叫的 DataFrame 方法
_FORBIDDEN_DF_METHODS = ("merge", "groupby", "map", "drop_duplicates")


@dataclass
class PageViolation:
    kind: str
    file: str
    line: int
    symbol: str


def _collect_page_files() -> list[Path]:
    files: list[Path] = []
    for pages_dir in PROJECT_ROOT.rglob("pages"):
        if not pages_dir.is_dir():
            continue
        for py_file in pages_dir.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            files.append(py_file)
    return files


def _scan_file_violations(path: Path) -> list[PageViolation]:
    violations: list[PageViolation] = []
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(src, filename=str(path))
    except SyntaxError:
        return violations

    rel = str(path.relative_to(PROJECT_ROOT))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        # direct function call: create_xxx(...) / update_xxx(...)
        if isinstance(node.func, ast.Name):
            name = node.func.id
            for prefix in _FORBIDDEN_CALL_PREFIXES:
                if name.startswith(prefix):
                    violations.append(PageViolation(
                        kind="direct_service_call",
                        file=rel,
                        line=node.lineno,
                        symbol=name,
                    ))
                    break

        # attribute call: df.merge(...) / df.groupby(...)
        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            if attr in _FORBIDDEN_DF_METHODS:
                violations.append(PageViolation(
                    kind="df_operation_in_page",
                    file=rel,
                    line=node.lineno,
                    symbol=attr,
                ))

    return violations


def scan_page_layer_violations() -> list[PageViolation]:
    violations: list[PageViolation] = []
    for f in _collect_page_files():
        violations.extend(_scan_file_violations(f))
    return violations


# ---------------------------------------------------------------------------
# 6. summarize
# ---------------------------------------------------------------------------

def summarize(results: dict[str, Any]) -> dict[str, Any]:
    import_items = results.get("import_smoke", [])
    export_items = results.get("page_exports", [])
    violations = results.get("page_layer_violations", [])
    router = results.get("router_smoke", {})
    compileall_result = results.get("compileall", {})

    return {
        "compileall_ok": bool(compileall_result.get("ok", False)),
        "import_modules_total": len(import_items),
        "import_modules_failed": sum(1 for i in import_items if not i.get("ok", True)),
        "router_ok": bool(router.get("ok", False)),
        "router_route_count": len(router.get("checks", [])),
        "page_export_total": len(export_items),
        "page_export_failed": sum(1 for e in export_items if not e.get("ok", True)),
        "page_violation_total": len(violations),
    }
