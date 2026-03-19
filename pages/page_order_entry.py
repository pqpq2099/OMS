# 修正版頁面邏輯（精簡示意版）

def get_display_data(prev_date, curr_date, data):
    if prev_date is None:
        return {
            "last_purchase": 0,
            "note": "無歷史資料"
        }

    last_purchase = sum(x["qty"] for x in data if prev_date <= x["delivery_date"] <= curr_date)
    return {
        "last_purchase": last_purchase
    }
