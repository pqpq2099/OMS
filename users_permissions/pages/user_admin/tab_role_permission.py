from __future__ import annotations

import pandas as pd
import streamlit as st

from users_permissions.logic.user_permission import ROLE_PERMISSION_ROWS
from ui_text import t


def render_tab_role_permission(_ctx):
    st.subheader(t("role_permission_table"))
    st.caption(t("role_permission_caption"))
    permission_df = pd.DataFrame(ROLE_PERMISSION_ROWS)
    st.dataframe(permission_df, use_container_width=True, hide_index=True)
    st.markdown(f"#### {t('supplement')}")
    st.write(t("permission_note_1"))
    st.write(t("permission_note_2"))
    st.write(t("permission_note_3"))
    st.write(t("permission_note_4"))
