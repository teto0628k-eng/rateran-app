# -*- coding: utf-8 -*-
import re
import pandas as pd
import streamlit as st

# =========================
# 固定セルの定義（0始まり）
# =========================
FIXPOS = {
    "TITLE": (6, 1),       # 正式タイトル: B7
    "DATE_L": (2, 1),      # 放送日 左: B3
    "DATE_R": (2, 4),      # 放送日 右: E3
    "TIME_L": (3, 1),      # 時刻 左: B4
    "TIME_R": (3, 4),      # 時刻 右: E4
    "CAST": (10, 1),       # 出演者: B11
    "SHORT_TITLE": (40, 1) # 短縮版タイトル: B41
}

LATIN = re.compile(r"[A-Za-z]")

# =========================
# ユーティリティ
# =========================
def get_cell(df: pd.DataFrame, pos):
    r, c = pos
    try:
        v = str(df.iat[r, c]).strip()
        return "" if v.lower() == "nan" else v
    except Exception:
        return ""

def prefer_latin_title(title_raw: str) -> str:
    """英字があればそのまま、括弧付き読み仮名は削除"""
    s = (title_raw or "").strip()
    if not s:
        return s
    if LATIN.search(s):
        s = re.sub(r"[（(][^）)]*[）)]\s*$", "", s).strip()
        s = re.sub(r"\s*[（(][^）)]*[）)]\s*", " ", s).strip()
    return s

def normalize_cast(cast_text: str) -> str:
    parts = re.split(r"[、，,/／・\s]+", (cast_text or "").strip())
    return "、".join([p for p in parts if p])

def cast_first_n(cast: str, n: int) -> str:
    if not cast:
        return ""
    arr = [a for a in re.split(r"[、，,/／・\s]+", cast) if a]
    return "、".join(arr[:n])

def trim_to_len(s: str, n: int) -> str:
    return "" if n <= 0 else (s if len(s) <= n else s[:n])

def compose_text(title: str, cast: str, marks: dict) -> str:
    """マーク＋タイトル＋出演者"""
    head = ""
    if marks.get("字"): head += "字"
    if marks.get("デ"): head += "デ"
    title_prefix = "新" if marks.get("新") else ""
    title_suffix = "終" if marks.get("終") else ""
    core = f"{title_prefix}{title}{title_suffix}"
    if cast:
        core += f"{cast}"
    return f"{head}{core}"

def pick_title_for_length(L: int, main_title: str, short_title: str) -> str:
    """10文字以下なら短縮版を優先（空なら正式タイトル）"""
    if L <= 10 and short_title:
        return short_title
    return main_title

def generate_ideas(main_title: str, short_title: str, cast: str, marks: dict, length: int):
    title_for_L = pick_title_for_length(length, main_title, short_title)
    ideas_raw = [
        compose_text(title_for_L, cast, marks),
        compose_text(title_for_L, cast_first_n(cast, 2), marks),
        compose_text(title_for_L, "", marks),
    ]
    out = []
    for x in ideas_raw:
        t = trim_to_len(x, length)
        if t and t not in out:
            out.append(t)
    return out

# =========================
# Streamlit UI
# =========================
st.title("📺 ラテ欄作成アプリ（短縮版タイトル B41対応）")

lengths_input = st.text_input("文字数パターン（カンマ区切り）：", "10,5,4,3")
try:
    lengths = [int(x.strip()) for x in lengths_input.split(",") if x.strip()]
except ValueError:
    st.error("整数で入力してください（例: 10,5,4,3）")
    st.stop()

col1, col2, col3, col4 = st.columns(4)
marks = {
    "字": col1.checkbox("字 マークあり"),
    "デ": col2.checkbox("デ マークあり"),
    "新": col3.checkbox("新 マークあり"),
    "終": col4.checkbox("終 マークあり"),
}

writer_input = st.text_input("④ 記入者のお名前を入力してください")

short_title_override = st.text_input("短縮版タイトル（任意入力：B41より優先）")

uploaded = st.file_uploader("EPGファイルをアップロード（.xlsx）", type=["xlsx"])

if st.button("ラテ欄作成", type="primary"):
    if not uploaded:
        st.warning("EPGファイルをアップロードしてください。")
        st.stop()

    try:
        df = pd.read_excel(uploaded, sheet_name=0, header=None)
    except Exception as e:
        st.error(f"読み込み失敗: {e}")
        st.stop()

    main_title = prefer_latin_title(get_cell(df, FIXPOS["TITLE"]))
    cast = normalize_cast(get_cell(df, FIXPOS["CAST"]))
    date_l, date_r = get_cell(df, FIXPOS["DATE_L"]), get_cell(df, FIXPOS["DATE_R"])
    time_l, time_r = get_cell(df, FIXPOS["TIME_L"]), get_cell(df, FIXPOS["TIME_R"])

    # 短縮版（UI入力 > B41 > 正式タイトル）
    short_title = short_title_override.strip() if short_title_override else get_cell(df, FIXPOS["SHORT_TITLE"])

    st.subheader("結果表示")
    st.write("**① 正式タイトル**：", main_title or "（不明）")
    st.write("**①' 短縮版タイトル**：", short_title or "（未設定 → 正式使用）")

    st.write("**② 放送日時**：", f"{date_l} {date_r} {time_l}～{time_r}".strip())
    st.write("**③ 出演者**：", cast or "（不明）")
    st.write("**④ 記入者**：", writer_input or "（未入力）")

    st.markdown("**⑤ 文字数パターン別ラテ欄アイデア**（10文字以下なら短縮版）")
    out_rows = []
    for L in lengths:
        ideas = generate_ideas(main_title, short_title, cast, marks, L)
        st.markdown(f"- **{L}文字**")
        for idx, idea in enumerate(ideas, start=1):
            st.write(f"　案{idx}: {idea}")
            out_rows.append({
                "length": L,
                "idea_no": idx,
                "text": idea,
                "writer": writer_input,
                "used_title": pick_title_for_length(L, main_title, short_title)
            })

    if out_rows:
        out_df = pd.DataFrame(out_rows)
        st.download_button("CSVでダウンロード",
                           out_df.to_csv(index=False).encode("utf-8-sig"),
                           "latekans.csv",
                           "text/csv")
