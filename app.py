import streamlit as st
import pandas as pd
import numpy as np
import re
import plotly.express as px

st.set_page_config(page_title="Benchmarking Kompetitor - teraMedik CE", layout="wide")

# =========================================================
# 1. PARSER FILE EXCEL
# Format yang diharapkan: kolom A = "Kriteria", kolom berikutnya = tiap vendor
# =========================================================
def load_benchmark(file):
    raw = pd.read_excel(file, header=None)
    header_row_idx = None
    for i, val in enumerate(raw.iloc[:, 0]):
        if isinstance(val, str) and val.strip().lower() == "kriteria":
            header_row_idx = i
            break
    if header_row_idx is None:
        raise ValueError("Tidak menemukan baris header 'Kriteria' di kolom A.")

    header = raw.iloc[header_row_idx]
    vendors = [str(v).strip() for v in header[1:] if isinstance(v, str) and v.strip() != ""]

    data = {}
    for i in range(header_row_idx + 1, len(raw)):
        krit = raw.iloc[i, 0]
        if not isinstance(krit, str) or krit.strip() == "":
            continue
        krit = krit.strip()
        row_vals = {}
        for j, vendor in enumerate(vendors, start=1):
            val = raw.iloc[i, j]
            row_vals[vendor] = str(val).strip() if isinstance(val, str) else ""
        data[krit] = row_vals
    return vendors, data


def get_field(data, key, vendor, default=""):
    return data.get(key, {}).get(vendor, default)


# =========================================================
# 2. FEATURE GAP MATRIX
# =========================================================
DEFAULT_FEATURES = {
    "RME": ["rme", "rekam medis"],
    "Antrean/Booking": ["antrean", "booking"],
    "Kasir/POS/Tagihan": ["kasir", "tagihan", "pos"],
    "Farmasi/Stok Obat": ["farmasi", "obat", "stok"],
    "Inventory": ["inventory"],
    "Pengingat Otomatis": ["pengingat"],
    "White-label / Branding Sendiri": ["white-label", "white label", "branding"],
    "Modular / Bayar Sesuai Fitur": ["modular"],
    "Membership Pasien": ["membership"],
    "ICD-9/ICD-10": ["icd"],
    "Integrasi SATUSEHAT": ["satu sehat", "satusehat"],
    "Integrasi BPJS/PCare": ["bpjs", "pcare", "p-care", "jkn"],
    "Mobile App": ["mobile", "smartphone", " app "],
    "Multi-klinik / Multi-role": ["multi-klinik", "multi klinik", "multi-role", "banyak klinik", "multi role"],
}
FEATURE_SOURCE_FIELDS = ["Fitur Utama", "Fitur Unggulan / Diferensiasi", "Model Deployment (Cloud/On-Premise)",
                          "Platform (Web/Mobile/Desktop)"]
# Fitur yang dicek langsung dari baris "Ya/Tidak" tersendiri, bukan dari teks bebas
DIRECT_FIELDS = {
    "Integrasi SATUSEHAT": "Satu Sehat",
    "Integrasi BPJS/PCare": "Integrasi BPJS",
}


def build_feature_matrix(vendors, data, feature_dict, source_fields):
    combined_text = {v: "" for v in vendors}
    for field in source_fields:
        if field in data:
            for v in vendors:
                combined_text[v] += " " + get_field(data, field, v).lower()

    matrix = pd.DataFrame(index=list(feature_dict.keys()), columns=vendors)
    for feat, keywords in feature_dict.items():
        if feat in DIRECT_FIELDS and DIRECT_FIELDS[feat] in data:
            src_field = DIRECT_FIELDS[feat]
            for v in vendors:
                found = get_field(data, src_field, v).lower().startswith("ya")
                matrix.loc[feat, v] = "✅" if found else "—"
        else:
            for v in vendors:
                found = any(kw in combined_text[v] for kw in keywords)
                matrix.loc[feat, v] = "✅" if found else "—"
    return matrix


# =========================================================
# 3. PRICING NORMALIZATION (heuristik, bisa dikoreksi manual)
# =========================================================
def parse_price_estimate(text):
    """Kembalikan estimasi Rp/bulan (float) atau None kalau tidak terdeteksi."""
    if not text:
        return None
    low = text.lower()
    if "tidak dipublikasikan" in low or "hubungi" in low:
        return None

    estimates = []
    for m in re.finditer(r"rp\s?([\d\.]+)", low):
        amount = int(m.group(1).replace(".", ""))
        context = low[m.end(): m.end() + 40]
        visit_match = re.search(r"(\d+)\s*visit\s*/\s*(\d+)\s*bln", context)
        if visit_match:
            months = int(visit_match.group(2))
            estimates.append(amount / months)
        elif "/bulan" in context or "bulan" in low:
            estimates.append(amount)
        else:
            estimates.append(amount)
    return round(sum(estimates) / len(estimates)) if estimates else None


# =========================================================
# 4. SENTIMENT (lexicon sederhana Bahasa Indonesia)
# =========================================================
POS_WORDS = ["mudah", "menarik", "ramah", "fleksibel", "ringan", "simple", "cepat",
             "dipahami", "efisien", "kuat", "luas", "lengkap", "nyaman"]
NEG_WORDS = ["kaku", "rumit", "mahal", "belum", "lambat", "membingungkan", "kurang",
             "terkunci", "tidak transparan", "sulit"]


def sentiment_score(text):
    low = text.lower()
    pos_hits = [w for w in POS_WORDS if w in low]
    neg_hits = [w for w in NEG_WORDS if w in low]
    score = len(pos_hits) - len(neg_hits)
    if score > 0:
        label = "Positif"
    elif score < 0:
        label = "Negatif"
    else:
        label = "Netral"
    return label, score, pos_hits, neg_hits


# =========================================================
# UI
# =========================================================
st.title("📊 Dashboard Benchmarking Kompetitor — teraMedik CE")
st.caption("Upload file Excel benchmarking (kolom A = Kriteria, kolom lain = tiap vendor)")

uploaded = st.file_uploader("Upload file Excel (.xlsx)", type=["xlsx"])
if uploaded is None:
    st.info("Silakan upload file benchmarking untuk mulai analisis.")
    st.stop()

try:
    vendors, data = load_benchmark(uploaded)
except Exception as e:
    st.error(f"Gagal membaca file: {e}")
    st.stop()

st.success(f"Berhasil memuat data {len(vendors)} vendor: {', '.join(vendors)}")

feature_matrix = build_feature_matrix(vendors, data, DEFAULT_FEATURES, FEATURE_SOURCE_FIELDS)
feature_score = {v: (feature_matrix[v] == "✅").sum() for v in vendors}
feature_pct = {v: round(feature_score[v] / len(DEFAULT_FEATURES) * 100) for v in vendors}

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["🎯 Positioning Map", "✅ Feature Gap Matrix", "💰 Pricing Normalization",
     "📋 SWOT Summary", "💬 Sentiment Analysis"]
)

# ---------------- TAB 1: Positioning Map ----------------
with tab1:
    st.subheader("Positioning Map: Harga (Rp/bulan estimasi) vs Kelengkapan Fitur")

    price_field = "Kisaran Harga (Rp)"
    rows = []
    no_price_vendors = []
    for v in vendors:
        price = parse_price_estimate(get_field(data, price_field, v))
        rows.append({"Vendor": v, "Estimasi Harga (Rp/bulan)": price, "Kelengkapan Fitur (%)": feature_pct[v]})
        if price is None:
            no_price_vendors.append(v)

    df_pos = pd.DataFrame(rows)
    df_plot = df_pos.dropna(subset=["Estimasi Harga (Rp/bulan)"])

    if not df_plot.empty:
        fig = px.scatter(
            df_plot, x="Estimasi Harga (Rp/bulan)", y="Kelengkapan Fitur (%)",
            text="Vendor", size=[30] * len(df_plot),
            color="Vendor", size_max=30
        )
        fig.update_traces(textposition="top center")
        fig.add_vline(x=df_plot["Estimasi Harga (Rp/bulan)"].mean(), line_dash="dash", line_color="gray")
        fig.add_hline(y=df_plot["Kelengkapan Fitur (%)"].mean(), line_dash="dash", line_color="gray")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Tidak ada vendor dengan harga yang bisa diparse untuk sumbu X.")

    if no_price_vendors:
        st.markdown(f"**Vendor tanpa harga publik** (tidak masuk chart): {', '.join(no_price_vendors)}")
    st.dataframe(df_pos, use_container_width=True)

# ---------------- TAB 2: Feature Gap Matrix ----------------
with tab2:
    st.subheader("Feature Gap Matrix")
    st.caption("Dideteksi otomatis dari kolom Fitur Utama, Fitur Unggulan, Deployment & Platform. Cek ulang manual bila perlu.")
    st.dataframe(feature_matrix, use_container_width=True)

    gap_features = feature_matrix[(feature_matrix == "—").all(axis=1)]
    if not gap_features.empty:
        st.success(f"**Peluang diferensiasi** (fitur belum dipunyai vendor manapun): {', '.join(gap_features.index)}")
    else:
        st.info("Semua fitur pada daftar sudah dimiliki minimal satu vendor.")

    df_score = pd.DataFrame({"Vendor": vendors, "Jumlah Fitur": [feature_score[v] for v in vendors],
                              "Kelengkapan (%)": [feature_pct[v] for v in vendors]})
    st.bar_chart(df_score.set_index("Vendor")["Kelengkapan (%)"])

# ---------------- TAB 3: Pricing Normalization ----------------
with tab3:
    st.subheader("Normalisasi Harga")
    st.caption("Estimasi otomatis dari teks harga (heuristik). Silakan koreksi manual di tabel bila perlu, lalu grafik akan mengikuti.")

    df_price = pd.DataFrame({
        "Vendor": vendors,
        "Teks Harga Asli": [get_field(data, price_field, v) for v in vendors],
        "Estimasi Rp/Bulan": [parse_price_estimate(get_field(data, price_field, v)) for v in vendors],
    })
    edited = st.data_editor(df_price, use_container_width=True, num_rows="fixed",
                             disabled=["Vendor", "Teks Harga Asli"])

    df_chart = edited.dropna(subset=["Estimasi Rp/Bulan"])
    if not df_chart.empty:
        fig2 = px.bar(df_chart, x="Vendor", y="Estimasi Rp/Bulan", color="Vendor", text="Estimasi Rp/Bulan")
        st.plotly_chart(fig2, use_container_width=True)
    tidak_transparan = edited[edited["Estimasi Rp/Bulan"].isna()]["Vendor"].tolist()
    if tidak_transparan:
        st.markdown(f"**Harga tidak transparan / custom quote:** {', '.join(tidak_transparan)}")

# ---------------- TAB 4: SWOT Summary ----------------
with tab4:
    st.subheader("Ringkasan Kompetitif per Vendor")
    cols = st.columns(len(vendors))
    for col, v in zip(cols, vendors):
        with col:
            st.markdown(f"### {v}")
            st.markdown("**✅ Kelebihan**")
            for point in get_field(data, "Kelebihan", v).split(","):
                if point.strip():
                    st.markdown(f"- {point.strip()}")
            st.markdown("**⚠️ Kekurangan**")
            for point in get_field(data, "Kekurangan", v).split(","):
                if point.strip():
                    st.markdown(f"- {point.strip()}")
            st.markdown("**🎯 Diferensiasi**")
            st.caption(get_field(data, "Fitur Unggulan / Diferensiasi", v))

# ---------------- TAB 5: Sentiment Analysis ----------------
with tab5:
    st.subheader("Sentiment dari Catatan UI/UX")
    rows_sent = []
    for v in vendors:
        text = get_field(data, "Catatan UI/UX", v)
        label, score, pos_hits, neg_hits = sentiment_score(text)
        rows_sent.append({
            "Vendor": v, "Sentimen": label, "Skor": score,
            "Kata Positif": ", ".join(pos_hits) if pos_hits else "-",
            "Kata Negatif": ", ".join(neg_hits) if neg_hits else "-",
        })
    df_sent = pd.DataFrame(rows_sent)

    fig3 = px.bar(df_sent, x="Vendor", y="Skor", color="Sentimen",
                   color_discrete_map={"Positif": "#2ecc71", "Netral": "#95a5a6", "Negatif": "#e74c3c"})
    st.plotly_chart(fig3, use_container_width=True)
    st.dataframe(df_sent, use_container_width=True)

    with st.expander("Lihat teks asli Catatan UI/UX"):
        for v in vendors:
            st.markdown(f"**{v}:** {get_field(data, 'Catatan UI/UX', v)}")