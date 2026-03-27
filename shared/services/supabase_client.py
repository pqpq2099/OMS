from supabase import create_client

SUPABASE_URL = "https://hikmpynwpqtbgqhsuyqd.supabase.co"
SUPABASE_KEY = "sb_publishable_NnWCl-WgBU2BqHFZLgdCEQ_2QNQwxd-"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_table(table_name):
    res = supabase.table(table_name).select("*").execute()
    return res.data