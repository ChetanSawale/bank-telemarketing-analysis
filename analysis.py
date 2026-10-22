#!/usr/bin/env python3
"""
Bank Telemarketing Conversion Analysis
======================================
Dataset: UCI Bank Marketing (bank-full.csv) — 45,211 clients contacted by a
Portuguese bank's phone campaigns (May 2008 – Nov 2010).
Target:  y = 'yes' -> the client subscribed to a term deposit.

Pipeline: clean -> SQLite + SQL business questions -> segment analysis ->
6-panel dashboard -> logistic regression on PRE-CALL features only
(call duration is excluded on purpose: it is only known after the call
ends, so using it to "predict" conversions would be target leakage).

Run:  python3 analysis.py
Outputs: outputs/*.csv, assets/dashboard.png, bank.db (local, not committed)
"""
import sqlite3
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent
MONTH_ORDER = ["jan", "feb", "mar", "apr", "may", "jun",
               "jul", "aug", "sep", "oct", "nov", "dec"]


def conv_table(df, col, min_n=1):
    g = df.groupby(col)["subscribed"].agg(["sum", "count", "mean"])
    g = g[g["count"] >= min_n].rename(
        columns={"sum": "subscriptions", "count": "clients", "mean": "conversion"})
    g["conversion_pct"] = (100 * g["conversion"]).round(2)
    return g.reset_index()


def main():
    # ---------- 1. Load & clean ----------
    df = pd.read_csv(BASE / "data" / "bank-full.csv", sep=";")
    print(f"raw rows: {len(df):,} | columns: {len(df.columns)}")
    print(f"missing values: {int(df.isna().sum().sum())} | duplicates: {int(df.duplicated().sum())}")

    df["subscribed"] = (df["y"] == "yes").astype(int)
    # pdays = -1 means "never contacted in a previous campaign"
    df["contacted_before"] = (df["pdays"] != -1).astype(int)
    df["pdays_clean"] = df["pdays"].replace(-1, np.nan)
    df["age_band"] = pd.cut(df["age"], [0, 25, 35, 45, 55, 65, 120],
                            labels=["<25", "25-34", "35-44", "45-54", "55-64", "65+"])
    df["campaign_group"] = np.where(df["campaign"] >= 5, "5+", df["campaign"].astype(str))

    overall = df["subscribed"].mean()
    subs = int(df["subscribed"].sum())
    print(f"\nOVERALL: {len(df):,} clients contacted, {subs:,} subscriptions, "
          f"conversion = {100 * overall:.2f}%")

    # ---------- 2. SQLite + SQL business questions ----------
    con = sqlite3.connect(BASE / "bank.db")
    df.drop(columns=["subscribed"]).to_sql("clients_raw", con, if_exists="replace", index=False)
    # recreate the exact table the .sql file expects (y as yes/no text)
    con.execute("DROP TABLE IF EXISTS clients")
    con.execute("ALTER TABLE clients_raw RENAME TO clients")
    sql_text = (BASE / "sql" / "queries.sql").read_text()
    statements = [s.strip() for s in sql_text.split(";\n") if "-- Q" in s]
    print("\n--- SQL results ---")
    for stmt in statements:
        title = [ln for ln in stmt.splitlines() if ln.strip().startswith("-- Q")][0].strip("- ")
        res = pd.read_sql_query(stmt, con)
        print(f"\n{title}\n{res.to_string(index=False)}")
    con.close()

    # ---------- 3. Segment tables -> outputs/ ----------
    tables = {
        "conversion_by_month": conv_table(df.assign(
            month=pd.Categorical(df["month"], MONTH_ORDER, ordered=True)), "month").sort_values("month"),
        "conversion_by_contact": conv_table(df, "contact"),
        "conversion_by_poutcome": conv_table(df, "poutcome"),
        "conversion_by_campaign_contacts": conv_table(df, "campaign_group"),
        "conversion_by_job": conv_table(df, "job", min_n=500),
        "conversion_by_age_band": conv_table(df, "age_band"),
    }
    for name, t in tables.items():
        t.to_csv(BASE / "outputs" / f"{name}.csv", index=False)
        print(f"\nwrote outputs/{name}.csv\n{t.to_string(index=False)}")

    # duration: analyse it, but flag the leakage caveat loudly
    dur = df.groupby("subscribed")["duration"].agg(["mean", "median"]).round(1)
    print(f"\ncall duration (seconds) by outcome:\n{dur.to_string()}")
    print("NOTE: duration is known only AFTER the call -> excluded from the model (leakage).")

    # ---------- 4. Model: pre-call features only ----------
    try:
        from sklearn.compose import ColumnTransformer
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import roc_auc_score
        from sklearn.model_selection import train_test_split
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder, StandardScaler

        feats_cat = ["job", "marital", "education", "default", "housing", "loan",
                     "contact", "month", "poutcome"]
        feats_num = ["age", "balance", "campaign", "previous", "contacted_before"]
        X = df[feats_cat + feats_num]
        y = df["subscribed"]
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)
        pre = ColumnTransformer([
            ("cat", OneHotEncoder(handle_unknown="ignore"), feats_cat),
            ("num", StandardScaler(), feats_num)])
        model = Pipeline([("pre", pre),
                          ("lr", LogisticRegression(max_iter=1000, class_weight="balanced"))])
        model.fit(Xtr, ytr)
        auc = roc_auc_score(yte, model.predict_proba(Xte)[:, 1])
        print(f"\nMODEL (pre-call features only, no duration): ROC-AUC = {auc:.3f} "
              f"on {len(yte):,} held-out clients (baseline = 0.500)")
    except ImportError:
        print("\nscikit-learn not installed — model step skipped")

    # ---------- 5. Dashboard (6 panels) ----------
    plt.rcParams.update({"font.size": 9, "axes.titlesize": 11, "axes.titleweight": "bold"})
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    fig.suptitle("Bank Telemarketing — What Actually Converts?  (45,211 clients, 11.7% overall)",
                 fontsize=14, fontweight="bold")

    t = tables["conversion_by_month"]
    ax = axes[0, 0]
    ax.bar(t["month"].astype(str), t["conversion_pct"], color="#4C78A8")
    ax.axhline(100 * overall, color="crimson", ls="--", lw=1)
    ax.set_title("Conversion by month")
    ax.set_ylabel("conversion %")

    t = tables["conversion_by_poutcome"].sort_values("conversion_pct")
    ax = axes[0, 1]
    ax.barh(t["poutcome"], t["conversion_pct"], color="#54A24B")
    ax.set_title("Previous campaign outcome")

    t = tables["conversion_by_contact"]
    ax = axes[0, 2]
    ax.bar(t["contact"], t["conversion_pct"], color="#F58518")
    ax.set_title("Contact channel")
    ax.set_ylabel("conversion %")

    order = ["1", "2", "3", "4", "5+"]
    t = tables["conversion_by_campaign_contacts"].set_index("campaign_group").reindex(order).reset_index()
    ax = axes[1, 0]
    ax.plot(t["campaign_group"], t["conversion_pct"], marker="o", color="#B279A2", lw=2)
    ax.set_title("Call fatigue — more calls, worse conversion")
    ax.set_ylabel("conversion %")
    ax.set_xlabel("contacts in this campaign")

    t = tables["conversion_by_job"].sort_values("conversion_pct")
    ax = axes[1, 1]
    ax.barh(t["job"], t["conversion_pct"], color="#E45756")
    ax.set_title("Conversion by job (500+ clients)")

    t = tables["conversion_by_age_band"]
    ax = axes[1, 2]
    ax.bar(t["age_band"].astype(str), t["conversion_pct"], color="#72B7B2")
    ax.axhline(100 * overall, color="crimson", ls="--", lw=1)
    ax.set_title("Conversion by age band")
    ax.set_ylabel("conversion %")

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(BASE / "assets" / "dashboard.png", dpi=150)
    print(f"\nwrote assets/dashboard.png")
    print("\nDONE.")


if __name__ == "__main__":
    main()
