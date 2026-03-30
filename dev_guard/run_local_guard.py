from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from validation_baseline.run_validation_baseline import (
    run_compileall,
    run_export_checks,
    run_import_smoke,
    run_router_smoke,
    scan_page_layer_violations,
    summarize,
)

OUTPUT_DIR = PROJECT_ROOT / 'dev_guard'
REPORT_JSON = OUTPUT_DIR / 'latest_guard_report.json'
REPORT_MD = OUTPUT_DIR / 'latest_guard_report.md'


def build_results() -> dict[str, Any]:
    results: dict[str, Any] = {}
    results['meta'] = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'project_root': str(PROJECT_ROOT),
        'validator': 'dev_guard/run_local_guard.py',
        'baseline_source': 'validation_baseline/run_validation_baseline.py',
    }
    results['compileall'] = run_compileall()
    results['import_smoke'] = [asdict(item) for item in run_import_smoke()]
    results['router_smoke'] = run_router_smoke()
    results['page_exports'] = [asdict(item) for item in run_export_checks()]
    results['page_layer_violations'] = [asdict(item) for item in scan_page_layer_violations()]
    results['summary'] = summarize(results)
    results['guard_ok'] = is_guard_ok(results)
    return results


def is_guard_ok(results: dict[str, Any]) -> bool:
    summary = results['summary']
    return (
        summary['compileall_ok']
        and summary['import_modules_failed'] == 0
        and summary['router_ok']
        and summary['page_export_failed'] == 0
        and summary['page_violation_total'] == 0
    )


def write_reports(results: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    REPORT_MD.write_text(build_markdown_report(results), encoding='utf-8')


def build_markdown_report(results: dict[str, Any]) -> str:
    summary = results['summary']
    guard_status = 'PASS' if results['guard_ok'] else 'FAIL'
    lines: list[str] = [
        '# OMS 修改後驗證標準輸出',
        '',
        '## 一、執行資訊',
        '',
        f"- 執行時間：{results['meta']['generated_at']}",
        f"- 驗證腳本：{results['meta']['validator']}",
        f"- 基準腳本：{results['meta']['baseline_source']}",
        '',
        '## 二、總結論',
        '',
        f'- Guard 結果：{guard_status}',
        f"- compileall：{'PASS' if summary['compileall_ok'] else 'FAIL'}",
        f"- import smoke：{'PASS' if summary['import_modules_failed'] == 0 else 'FAIL'}（{summary['import_modules_total'] - summary['import_modules_failed']}/{summary['import_modules_total']}）",
        f"- router smoke：{'PASS' if summary['router_ok'] else 'FAIL'}（{summary['router_route_count']} routes）",
        f"- pages __init__ 匯出：{'PASS' if summary['page_export_failed'] == 0 else 'FAIL'}（{summary['page_export_total'] - summary['page_export_failed']}/{summary['page_export_total']}）",
        f"- page 邊界違規：{'PASS' if summary['page_violation_total'] == 0 else 'FAIL'}（共 {summary['page_violation_total']} 筆）",
        '',
        '## 三、失敗項目',
        '',
    ]

    failed_imports = [item for item in results['import_smoke'] if not item['ok']]
    failed_routes = [item for item in results['router_smoke']['checks'] if not item['ok']]
    failed_exports = [item for item in results['page_exports'] if not item['ok']]
    violations = results['page_layer_violations']

    if not any([failed_imports, failed_routes, failed_exports, violations, results['router_smoke']['extra_keys'], results['router_smoke']['missing_keys']]):
        lines.append('- 無失敗')
    else:
        for item in failed_imports:
            lines.append(f"- import_fail | {item['module']} | {item['error_type']} | {item['error_message']}")
        for item in failed_routes:
            lines.append(f"- router_fail | {item['route_key']} | {item['target']}")
        for key in results['router_smoke']['missing_keys']:
            lines.append(f'- router_missing_key | {key}')
        for key in results['router_smoke']['extra_keys']:
            lines.append(f'- router_extra_key | {key}')
        for item in failed_exports:
            detail = f" | {item['detail']}" if item['detail'] else ''
            lines.append(f"- export_fail | {item['package']}::{item['export_name']}{detail}")
        for item in violations:
            lines.append(f"- page_violation | {item['kind']} | {item['file']}:{item['line']} | {item['symbol']}")

    lines.extend([
        '',
        '## 四、提交判定',
        '',
        '- PASS：可提交',
        '- FAIL：禁止提交，需先修正再重新執行驗證',
        '',
    ])
    return '\n'.join(lines) + '\n'


def print_console_summary(results: dict[str, Any]) -> None:
    summary = results['summary']
    guard_status = 'PASS' if results['guard_ok'] else 'FAIL'
    console = {
        'guard_result': guard_status,
        'compileall': 'PASS' if summary['compileall_ok'] else 'FAIL',
        'import_smoke': 'PASS' if summary['import_modules_failed'] == 0 else 'FAIL',
        'router_smoke': 'PASS' if summary['router_ok'] else 'FAIL',
        'page_exports': 'PASS' if summary['page_export_failed'] == 0 else 'FAIL',
        'page_boundary': 'PASS' if summary['page_violation_total'] == 0 else 'FAIL',
        'report_json': str(REPORT_JSON.relative_to(PROJECT_ROOT)),
        'report_md': str(REPORT_MD.relative_to(PROJECT_ROOT)),
    }
    print(json.dumps(console, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    result = build_results()
    write_reports(result)
    print_console_summary(result)
    sys.exit(0 if result['guard_ok'] else 1)
