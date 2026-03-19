# 修正版核心邏輯（精簡示意版）

def calculate_period(prev_date, curr_date, data):
    if prev_date is None:
        return {
            "prev_qty": 0,
            "purchase": 0,
            "usage": 0
        }

    purchase = sum(x["qty"] for x in data if prev_date <= x["delivery_date"] <= curr_date)
    return {
        "purchase": purchase
    }
