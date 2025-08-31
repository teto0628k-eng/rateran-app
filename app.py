# app.py（英字タイトル厳守＋デバッグ）
# -*- coding: utf-8 -*-
import re
import pandas as pd
import streamlit as st

# =========================
# 固定セルの定義（0始まり）
# =========================
FIXPOS = {
    "TITLE": (6, 1),            # ①番組名: B7（英字 "DOCTOR PRICE" が入っている想定）
    "DATE_L": (2, 1),           # 放送日(左): B3
    "DATE_R": (2, 4),           # 放送日(右): E3
    "TIME_L": (3, 1),           # 開始時刻 : B4
    "TIME_R": (3, 4),           # 終了時刻 : E4
    "CAST": (10, 1),            # 出演者: B11
}

# =========================
# ユーティリティ
# =========================
LATIN = re.compile(r"[A-Za-z]")

def get_cell(df: pd.DataFrame, pos):
    if not pos:
        return ""
    r, c = pos
    try:
        val = str(df.iat[r, c]).strip()
        return "" if val.lower() == "nan" else val
    except Exception:
        return ""

def prefer_latin_title(title_raw: str) -> str:
    """
    ルール⑤: アルファベットはカタカナに変換しないでそのまま使用。
    もし「英字 + （読み仮名）」の複合（例: 'DOCTOR PRICE（ドクタープライス）'）なら英字側を採用。
    """
    s = (title_raw or "").strip()
    if not s:
        return s

    # 全角括弧/半角括弧の読み仮名を落とす（英字が含まれるときだけ）
    if LATIN.search(s):
        # 末尾の（……）/(...) を除去
        s = re.sub(r"[（(][^）)]*[）)]\s*$", "", s).strip()
        # 先頭や中間に余計な括弧がある場合も軽く除去（安全側）
        s = re.sub(r"\s*[（(][^）)]*[）)]\s*", " ", s).strip()
    return s

def normalize_cast(cast_text: str) -> str:
    """
    出演者の区切りだけ整える（英字はそのまま保持。カタカナ変換なし）
    """
    parts = re.split(r"[、，,/／・\s]+", (cast_text or "").strip())
    parts = [p for p in parts if p]
    return "、".join(parts)

def cast_first_n(cast: str, n: int) -> str:
    if not cast:
        return ""
    arr = [a for a in re.split(r"[、，,/／・\s]+", cast) if a]
    return "、".join(arr[:n])

def trim_to_len(s: str, n: int) -> str:
    """特殊カウント未対応：単純な文字数スライス"""
    return "" if n <= 0 else (s if len(s) <= n else s[:n])

def compose_text(base_title: str, cast: str, marks: dict) -> str:
    """
    新ルール（サブタイトルなし）:
      基本 = [先頭マーク] + [新]タイトル[終] + 出演者
      ・「字」→文頭、続いて「デ」（チェック時）。各1文字としてカウント（実装はスライスで対応）
      ・「新」→タイトルの前
      ・「終」→タイトルの後
      ・英字は変換せず、そのまま使用（prefer_latin_title で確実化）
    """
    head = ""
    if marks.get("字"): head += "字"
    if marks.get("デ"): head += "デ"

    title_prefix = "新" if marks.get("新") else ""
    title_suffix = "終" if marks.get("終") else ""

    core = f"{title_prefix}{base_title}{title_suffix}"
    if cast:
        core += f"{cast}"
    return f"{head}{core}"

def generate_ideas(base_title: str, cast: str, marks: dict, length: int):
    """
    各文字数パターンにつき3案：
      A: タイトル + フルキャスト
      B: タイトル + 主要2名
      C: タイトルのみ
    """
    ideas_raw = [
        compose_text(base_title, cast, marks),
        compose_text(base_title, cast_first_n(cast, 2), marks),
        compose_text(base_title, "", marks),
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
st.title("📺 ラテ欄作成アプリ（英字タイトル厳守版）")

# 文字数パターン
lengths_input = st.text_input("文字数パターン（カンマ区切り）：", "10,5,4,3")
try:
    lengths = [int(x.strip()) for x in lengths_input.split(",") if x.strip()]
except ValueError:
    st.error("文字数は整数で入力してください（例: 10,5,4,3）")
    st.stop()

# マーク指定
col1, col2, col3, col4 = st.columns(4)
marks = {
    "字": col1.checkbox("字 マークあり"),
    "デ": col2.checkbox("デ マークあり"),
    "新": col3.checkbox("新 マークあり"),
    "終": col4.checkbox("終 マークあり"),
}

# 記入者（手入力）
writer_input = st.text_input("④ 記入者のお名前を入力してください")

# EPG取込
uploaded = st.file_uploader("EPGファイルをアップロード（.xlsx）", type=["xlsx"])

# 実行
if st.button("ラテ欄作成", type="primary"):
    if not uploaded:
        st.warning("EPGファイルをアップロードしてください。")
        st.stop()

    try:
        df = pd.read_excel(uploaded, sheet_name=0, header=None)
    except Exception as e:
        st.error(f"読み込みに失敗しました: {e}")
        st.stop()

    # 固定セル読取
    title_raw = get_cell(df, FIXPOS["TITLE"])
    date_l    = get_cell(df, FIXPOS["DATE_L"])
    date_r    = get_cell(df, FIXPOS["DATE_R"])
    time_l    = get_cell(df, FIXPOS["TIME_L"])
    time_r    = get_cell(df, FIXPOS["TIME_R"])
    cast_raw  = get_cell(df, FIXPOS["CAST"])

    # タイトルは英字優先でそのまま使用（読み仮名が括弧で付いていたら落とす）
    base_title = prefer_latin_title(title_raw)
    cast = normalize_cast(cast_raw)

    # 表示
    st.subheader("結果表示")
    st.write("**① 番組名（B7 raw）**：", title_raw or "（空）")
    st.write("**① 番組名（使用値）**：", base_title or "（不明）")

    date_str = " ".join([x for x in [date_l, date_r] if x])
    time_str = "～".join([x for x in [time_l, time_r] if x])
    st.write("**② 放送日時**：", (date_str + " " + time_str).strip() or "（不明）")

    st.write("**③ 出演者**：", cast or "（不明）")
    st.write("**④ 記入者**：", writer_input or "（未入力）")

    st.markdown("**⑤ 文字数パターン別 ラテ欄アイデア**")
    out_rows = []
    for L in lengths:
        ideas = generate_ideas(base_title, cast, marks, L)
        st.markdown(f"- **{L}文字**")
        for idx, idea in enumerate(ideas, start=1):
            st.write(f"　案{idx}: {idea}")
            out_rows.append({
                "length": L, "idea_no": idx, "text": idea, "writer": writer_input
            })

    # CSVダウンロード
    if out_rows:
        out_df = pd.DataFrame(out_rows)
        csv = out_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("CSVでダウンロード", csv, "latekans.csv", "text/csv")

    # デバッグ（B7の実際の中身を可視化）
    with st.expander("🔧 デバッグ（B7の中身確認）"):
        st.code(repr(title_raw))  # Pythonのrepr表示で目に見えない文字も確認

