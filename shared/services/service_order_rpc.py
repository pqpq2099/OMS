from __future__ import annotations

# =============================================================================
# [v1 STABLE — RPC TRANSPORT LAYER]
# 本模組為唯一合法的叫貨寫入入口，透過 Supabase service_role RPC 呼叫
# DB function rpc_save_order_transaction，在單次 DB transaction 內完成
# 5 張表的原子寫入。
#
# 禁止事項：
#   - 不可繞過此函式直接呼叫 Supabase table API 進行多步寫入
#   - 不可在未重新執行 transaction validation 的情況下修改 RPC function 名稱
#     或參數結構（p_payload）
#   - SQL function 位於 migrations/007_fix_rpc_on_conflict_partial.sql，
#     修改需重新驗證並輸出 rpc_transaction_validation_report
# =============================================================================

from shared.services.supabase_client import _get_client


def rpc_save_order_transaction(payload: dict) -> dict:
    """呼叫 DB function rpc_save_order_transaction，以單次 transaction 原子寫入。
    使用 service_role key（已在 _get_client() 設定），繞過 RLS。
    """
    result = (
        _get_client()
        .rpc("rpc_save_order_transaction", {"p_payload": payload})
        .execute()
    )
    return result.data or {}
