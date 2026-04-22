import pandas as pd
import numpy as np
import math
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import warnings
warnings.filterwarnings("ignore")

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTS  (only things that don't change year to year)
# ══════════════════════════════════════════════════════════════════════════════

# 1 center handles ~6500 requests/year
# (8 hrs × 250 days × ~5 requests/hr, accounting for idle/verification time)
THROUGHPUT = 6500

# India population (used to scale if your dataset population is synthetic)
INDIA_POP_REAL = {
    2021: 1_393_000_000,
    2022: 1_406_000_000,
    2023: 1_417_000_000,
    2024: 1_428_000_000,
    2025: 1_441_000_000,
    2026: 1_453_000_000,
    2027: 1_465_000_000,
    2028: 1_477_000_000,
    2029: 1_489_000_000,
    2030: 1_500_000_000,
}

# Aadhaar update rates by state (fraction needing update per year)
# These are structural constants — change only if policy changes
STATE_UPDATE_RATE = {
    "Andhra Pradesh": 0.082, "Arunachal Pradesh": 0.074,
    "Assam": 0.075,          "Bihar": 0.065,
    "Chhattisgarh": 0.072,   "Delhi": 0.095,
    "Goa": 0.088,            "Gujarat": 0.085,
    "Haryana": 0.083,        "Himachal Pradesh": 0.079,
    "Jammu And kashmir": 0.078, "Jharkhand": 0.070,
    "Karnataka": 0.088,      "Kerala": 0.090,
    "Madhya Pradesh": 0.071, "Maharashtra": 0.087,
    "Manipur": 0.072,        "Mizoram": 0.075,
    "Nagaland": 0.073,       "Orissa": 0.074,
    "Punjab": 0.086,         "Rajasthan": 0.073,
    "Sikkim": 0.078,         "Tamil Nadu": 0.089,
    "Telangana": 0.086,      "Uttar Pradesh": 0.068,
    "Uttarakhand": 0.078,    "West Bengal": 0.080,
}
DEFAULT_UPDATE_RATE = 0.080

# Age 15-19 cohort: fraction that enrolls/updates per year
AGE_COHORT_ENROL_RATE = 0.30

# ══════════════════════════════════════════════════════════════════════════════
# CORE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def compute_demand_for_row(population, birthrate, migrationrate,
                           age_group15_19, state,
                           pop_growth_rate=None):
    """
    Compute Aadhaar demand for ONE pincode given its actual demographic values.
    
    All rates come directly from the dataset for the current year.
    For future years, population is grown by pop_growth_rate; other rates
    are taken from the dataset as-is (best available estimate).

    Returns:
        total_demand (int), centers_required (int), demand_category (str)
    """
    ur = STATE_UPDATE_RATE.get(state, DEFAULT_UPDATE_RATE)

    # --- Demand components ---
    # 1. New births who will eventually need Aadhaar
    birth_demand = (birthrate / 1000) * population

    # 2. Net in-migrants needing new Aadhaar (out-migrants don't add demand)
    migration_demand = max(0, (migrationrate / 1000) * population)

    # 3. Age 15-19 cohort: major surge point (school/college/jobs)
    #    age_group15_19 is a state-level multiplier (fraction of population)
    age_cohort_demand = age_group15_19 * population * AGE_COHORT_ENROL_RATE

    # 4. Existing holders needing updates (address, biometric, lost card)
    update_demand = ur * population

    total_demand = birth_demand + migration_demand + age_cohort_demand + update_demand

    # Centers needed
    centers = max(1, math.ceil(total_demand / THROUGHPUT))

    # Demand category
    if   total_demand > 50_000: category = "High"
    elif total_demand > 25_000: category = "Medium"
    elif total_demand > 10_000: category = "Low"
    else:                       category = "Very Low"

    return {
        "birth_demand":      round(birth_demand),
        "migration_demand":  round(migration_demand),
        "age_cohort_demand": round(age_cohort_demand),
        "update_demand":     round(update_demand),
        "total_demand":      round(total_demand),
        "centers_required":  centers,
        "demand_category":   category,
    }


def load_and_validate(csv_path, data_year):
    """
    Load any year's CSV. Validates required columns exist.
    Scales population to India's real population for that year.
    """
    required = ['pincode', 'state', 'city', 'birthrate',
                'migrationrate', 'population', 'age_group15_19']

    df = pd.read_csv(csv_path, low_memory=False)

    # Clean
    df.columns = [c.strip().lower() for c in df.columns]
    df = df.dropna(subset=['pincode', 'state'])
    df = df[df['state'].str.strip().str.lower() != 'state']
    df = df.drop_duplicates(subset='pincode')
    df = df.reset_index(drop=True)

    # Check required columns
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in {csv_path}: {missing}")

    # Scale population to India's real figure for this year
    real_pop = INDIA_POP_REAL.get(data_year, 1_430_000_000)
    raw_total = df['population'].sum()
    if raw_total > 0:
        scale = real_pop / raw_total
        df['population'] = (df['population'] * scale).round().astype(int)

    print(f"  Loaded  : {csv_path}")
    print(f"  Year    : {data_year}")
    print(f"  Pincodes: {len(df):,}")
    print(f"  States  : {df['state'].nunique()}")
    print(f"  Total pop (scaled): {df['population'].sum():,}")

    return df


def estimate_growth_rates(df):
    """
    Estimate per-state population growth rate from the data itself.
    Uses the relationship between migration rate and a national baseline.
    Returns a dict: state -> annual growth rate (decimal).
    """
    # Base national growth rate for India (~1.1% in 2023)
    NATIONAL_GROWTH = 0.011

    state_stats = df.groupby('state').agg(
        avg_birthrate=('birthrate', 'mean'),
        avg_migrationrate=('migrationrate', 'mean'),
    ).reset_index()

    growth_rates = {}
    for _, row in state_stats.iterrows():
        state = row['state']
        br    = row['avg_birthrate']
        mr    = row['avg_migrationrate']

        # Natural growth ≈ (birth rate - assumed death rate) / 1000
        # Death rate estimated as: national_avg_br - national_growth*1000 ≈ 7
        assumed_death_rate = 7.0
        natural_growth = (br - assumed_death_rate) / 1000

        # Net migration adds to growth
        net_migration_growth = mr / 1000

        growth_rates[state] = max(0.002, natural_growth + net_migration_growth * 0.3)

    return growth_rates


def project_future(df, data_year, forecast_years, growth_rates):
    """
    For each pincode, project demand for data_year AND the next forecast_years.
    Birth rate, migration rate, age_group are taken directly from the dataset.
    Only population grows using per-state growth rates.
    """
    all_records = []

    for _, row in df.iterrows():
        state  = str(row['state'])
        g      = growth_rates.get(state, 0.011)
        base_pop = float(row['population'])

        for yr_offset in range(forecast_years + 1):
            year       = data_year + yr_offset
            pop        = round(base_pop * ((1 + g) ** yr_offset))

            # IMPORTANT: birth rate, migration rate, age_group come directly
            # from the dataset — NOT from fixed assumptions.
            # For future years, we use the same year's rates as best estimate.
            demand = compute_demand_for_row(
                population      = pop,
                birthrate       = float(row['birthrate']),
                migrationrate   = float(row['migrationrate']),
                age_group15_19  = float(row['age_group15_19']),
                state           = state,
            )

            record = {
                'year':     year,
                'pincode':  row['pincode'],
                'city':     row['city'],
                'state':    state,
                'birthrate':      row['birthrate'],
                'migrationrate':  row['migrationrate'],
                'age_group15_19': row['age_group15_19'],
                'population':     pop,
                **demand,
            }
            all_records.append(record)

    return pd.DataFrame(all_records)


def train_model(proj_df, data_year):
    """
    Train a regression model on the projected data.
    Features include all the actual demographic values from the CSV.
    """
    le = LabelEncoder()
    proj_df = proj_df.copy()
    proj_df['state_enc']    = le.fit_transform(proj_df['state'])
    proj_df['years_ahead']  = proj_df['year'] - data_year
    proj_df['pop_log']      = np.log1p(proj_df['population'])
    proj_df['br_x_pop']     = proj_df['birthrate'] * proj_df['population'] / 1000
    proj_df['mr_x_pop']     = proj_df['migrationrate'].clip(lower=0) * proj_df['population'] / 1000

    FEATURES = [
        'population', 'pop_log',
        'birthrate', 'migrationrate', 'age_group15_19',
        'br_x_pop', 'mr_x_pop',
        'years_ahead', 'state_enc',
    ]

    X = proj_df[FEATURES]
    y = proj_df['centers_required']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    models = {
        "Linear Regression": LinearRegression(),
        "Gradient Boosting": GradientBoostingRegressor(
            n_estimators=150, max_depth=4, random_state=42
        ),
    }

    best_model, best_name, best_r2 = None, "", -999
    print("\n  Model performance:")
    for name, model in models.items():
        model.fit(X_train, y_train)
        pred  = np.maximum(model.predict(X_test), 1).round()
        mae   = mean_absolute_error(y_test, pred)
        r2    = r2_score(y_test, pred)
        print(f"    {name:<25} MAE={mae:.2f}  R²={r2:.4f}")
        if r2 > best_r2:
            best_model, best_name, best_r2 = model, name, r2

    print(f"  Best model: {best_name}")
    return best_model, le, FEATURES, proj_df


def aggregate(proj_df, data_year):
    """Produce state-year and national-year summaries with new centers needed."""

    state_year = proj_df.groupby(['year', 'state']).agg(
        population    = ('population',       'sum'),
        total_demand  = ('total_demand',     'sum'),
        centers_req   = ('centers_required', 'sum'),
    ).reset_index()

    # New centers = difference vs base year
    base = state_year[state_year['year'] == data_year][['state', 'centers_req']]\
           .rename(columns={'centers_req': 'base_centers'})
    state_year = state_year.merge(base, on='state')
    state_year['new_centers_needed'] = (
        state_year['centers_req'] - state_year['base_centers']
    ).clip(lower=0).round().astype(int)

    national = state_year.groupby('year').agg(
        population         = ('population',        'sum'),
        total_demand       = ('total_demand',       'sum'),
        centers_req        = ('centers_req',        'sum'),
        new_centers_needed = ('new_centers_needed', 'sum'),
    ).reset_index()

    return state_year, national


def print_summary(national, state_year, data_year):
    base_yr = national[national['year'] == data_year].iloc[0]

    print(f"\n{'─'*70}")
    print(f"  {'Year':<6} {'Population':>14} {'Total Demand':>14} "
          f"{'Centers Reqd':>13} {'New to Build':>13}")
    print(f"  {'─'*66}")
    for _, r in national.iterrows():
        print(f"  {int(r.year):<6} {r.population:>14,.0f} {r.total_demand:>14,.0f} "
              f"{r.centers_req:>13,.0f} {r.new_centers_needed:>13,.0f}")
    print(f"{'─'*70}")

    last_yr  = national['year'].max()
    last_row = national[national['year'] == last_yr].iloc[0]
    total_new = int(last_row['new_centers_needed'])
    print(f"\n  Total new centers needed by {last_yr}: {total_new:,}")

    # State breakdown for last year
    s_last = state_year[state_year['year'] == last_yr]\
             .sort_values('new_centers_needed', ascending=False)
    print(f"\n  State-wise for {last_yr} (top 15 by new centers needed):")
    print(f"  {'State':<28} {'Centers in {}'.format(data_year):>14} "
          f"{'Centers in {}'.format(last_yr):>14} {'New Needed':>11}")
    print(f"  {'─'*70}")
    for _, r in s_last.head(15).iterrows():
        print(f"  {r.state:<28} {r.base_centers:>14,.0f} "
              f"{r.centers_req:>14,.0f} {r.new_centers_needed:>11,.0f}")


def save_plots(national, state_year, proj_df, data_year):
    last_yr = national['year'].max()
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    fig.suptitle(
        f"AadhaarMap — Center Demand Prediction  |  Base Year: {data_year}  →  {last_yr}",
        fontsize=13, fontweight="bold", y=0.99
    )
    BLUE, GREEN, RED, AMBER = "#185FA5", "#1D9E75", "#E8593C", "#EF9F27"

    # Plot 1: National centers by year
    ax = axes[0, 0]
    ax.bar(national['year'], national['centers_req'],
           color=BLUE, width=0.4, label="Total centers needed", zorder=2)
    ax.bar(national['year'], national['new_centers_needed'],
           color=GREEN, width=0.4, label="New centers to build", zorder=3)
    for _, r in national.iterrows():
        ax.text(r.year, r.centers_req + r.centers_req * 0.01,
                f"{int(r.centers_req):,}", ha='center', fontsize=7.5, fontweight='bold')
    ax.set_title(f"National: Total vs New Centers ({data_year}–{last_yr})")
    ax.set_xlabel("Year"); ax.set_ylabel("Centers")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.legend(fontsize=8); ax.set_ylim(0, national['centers_req'].max() * 1.15)
    ax.set_xticks(national['year'])

    # Plot 2: Top 12 states needing most new centers
    ax = axes[0, 1]
    top12 = state_year[state_year['year'] == last_yr]\
            .nlargest(12, 'new_centers_needed')
    bars = ax.barh(top12['state'], top12['new_centers_needed'], color=RED, edgecolor='white')
    for bar, val in zip(bars, top12['new_centers_needed']):
        ax.text(bar.get_width() + max(top12['new_centers_needed']) * 0.01,
                bar.get_y() + bar.get_height() / 2,
                f"{int(val):,}", va='center', fontsize=8)
    ax.set_title(f"Top 12 States — New Centers Needed by {last_yr}")
    ax.set_xlabel("New Centers"); ax.invert_yaxis()
    ax.set_xlim(0, top12['new_centers_needed'].max() * 1.22)

    # Plot 3: Demand component breakdown (national, stacked)
    ax = axes[1, 0]
    comp = proj_df.groupby('year').agg(
        birth    = ('birth_demand',      'sum'),
        migrants = ('migration_demand',  'sum'),
        age      = ('age_cohort_demand', 'sum'),
        updates  = ('update_demand',     'sum'),
    ).reset_index()
    btm = np.zeros(len(comp))
    labels_colors = [("Births", BLUE), ("Migrants", AMBER),
                     ("Age 15-19", GREEN), ("Updates", RED)]
    for (lbl, col), key in zip(labels_colors, ['birth','migrants','age','updates']):
        vals = comp[key].values
        ax.bar(comp['year'], vals, bottom=btm, label=lbl,
               color=col, edgecolor='white', width=0.5)
        btm += vals
    ax.set_title("Demand by Component (National, Stacked)")
    ax.set_xlabel("Year"); ax.set_ylabel("Requests / Year")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x/1e6:.1f}M"))
    ax.legend(fontsize=8); ax.set_xticks(comp['year'])

    # Plot 4: State-wise growth % base year → last year
    ax = axes[1, 1]
    s_base = state_year[state_year['year'] == data_year][['state','centers_req']]\
             .rename(columns={'centers_req': 'c_base'})
    s_last_df = state_year[state_year['year'] == last_yr][['state','centers_req']]\
                .rename(columns={'centers_req': 'c_last'})
    growth_df = s_base.merge(s_last_df, on='state')
    growth_df['pct'] = ((growth_df['c_last'] - growth_df['c_base']) / growth_df['c_base'] * 100).round(1)
    growth_df = growth_df.sort_values('pct').tail(15)
    colors = [RED if p >= 8 else BLUE for p in growth_df['pct']]
    bars = ax.barh(growth_df['state'], growth_df['pct'], color=colors, edgecolor='white')
    for bar, val in zip(bars, growth_df['pct']):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}%", va='center', fontsize=8)
    ax.set_title(f"Center Growth %: {data_year} → {last_yr}\n(Red = high priority >8%)")
    ax.set_xlabel("Growth (%)")
    ax.set_xlim(0, growth_df['pct'].max() * 1.25)

    plt.tight_layout()
    out_name = f"aadhaarmap_{data_year}_prediction.png"
    plt.savefig(out_name, dpi=150, bbox_inches="tight")
    # plt.show()
    print(f"\n  Plot saved: {out_name}")


def save_csvs(proj_df, state_year, national, data_year):
    proj_df.to_csv(f"aadhaar_pincode_{data_year}.csv", index=False)
    state_year.to_csv(f"aadhaar_state_{data_year}.csv", index=False)
    national.to_csv(f"aadhaar_national_{data_year}.csv", index=False)
    print(f"  CSVs saved:")
    print(f"    aadhaar_pincode_{data_year}.csv      — per-pincode, per-year")
    print(f"    aadhaar_state_{data_year}.csv        — state × year summary")
    print(f"    aadhaar_national_{data_year}.csv     — national totals by year")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE  — call this every year with your new CSV
# ══════════════════════════════════════════════════════════════════════════════

def run_pipeline(csv_path, data_year, forecast_years=5):
    """
    Full pipeline for any year's dataset.

    Parameters:
        csv_path       : str  — path to the year's CSV file
        data_year      : int  — the year this data represents (e.g. 2023)
        forecast_years : int  — how many years ahead to forecast (default 5)

    Returns:
        dict with proj_df, state_year, national, model
    """
    sep = "=" * 70
    print(f"\n{sep}")
    print(f"  AadhaarMap Pipeline — {data_year} Data")
    print(sep)

    # 1. Load
    print("\n[1] Loading data...")
    df = load_and_validate(csv_path, data_year)

    # 2. Estimate growth rates from actual data (no fixed values)
    print("\n[2] Estimating state growth rates from data...")
    growth_rates = estimate_growth_rates(df)
    for state, g in sorted(growth_rates.items())[:5]:
        print(f"    {state:<28} growth rate: {g*100:.2f}%/yr")
    print(f"    ... and {len(growth_rates)-5} more states")

    # 3. Project all years
    print(f"\n[3] Projecting demand: {data_year} → {data_year + forecast_years}...")
    proj_df = project_future(df, data_year, forecast_years, growth_rates)
    print(f"    Generated {len(proj_df):,} pincode-year records")

    # 4. Train model
    print("\n[4] Training prediction model...")
    model, le, features, proj_df = train_model(proj_df, data_year)

    # 5. Aggregate
    print("\n[5] Aggregating results...")
    state_year, national = aggregate(proj_df, data_year)

    # 6. Print summary
    print(f"\n{'='*70}")
    print("  NATIONAL YEAR-WISE SUMMARY")
    print_summary(national, state_year, data_year)

    # 7. Save
    print(f"\n[6] Saving outputs...")
    save_csvs(proj_df, state_year, national, data_year)
    save_plots(national, state_year, proj_df, data_year)

    print(f"\n{sep}")
    print("  DONE")
    print(sep)

    return {
        "proj_df":    proj_df,
        "state_year": state_year,
        "national":   national,
        "model":      model,
        "le":         le,
        "features":   features,
        "df_input":   df,
    }


# ══════════════════════════════════════════════════════════════════════════════
# SINGLE PINCODE PREDICTOR  — predict centers for any pincode in any year
# ══════════════════════════════════════════════════════════════════════════════

def predict_single_pincode(pipeline_result, pincode=None, state=None,
                           city=None, target_year=None):
    """
    After running the pipeline, predict for a specific pincode or custom values.

    Usage:
        predict_single_pincode(results, pincode="411001", target_year=2027)
    """
    proj_df  = pipeline_result["proj_df"]

    if pincode:
        subset = proj_df[proj_df['pincode'].astype(str) == str(pincode)]
        if subset.empty:
            print(f"Pincode {pincode} not found."); return
        if target_year:
            subset = subset[subset['year'] == target_year]
        print(f"\nPrediction for pincode {pincode}:")
        print(subset[['year','city','state','population','birthrate',
                      'migrationrate','total_demand','centers_required',
                      'demand_category']].to_string(index=False))
    elif state:
        sy = pipeline_result["state_year"]
        subset = sy[sy['state'].str.lower() == state.lower()]
        if target_year:
            subset = subset[subset['year'] == target_year]
        print(f"\nPrediction for state {state}:")
        print(subset[['year','population','total_demand','centers_req',
                      'new_centers_needed']].to_string(index=False))


# ══════════════════════════════════════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    # ── Run for 2023 data ─────────────────────────────────────────────────────
    results_2023 = run_pipeline(
        csv_path       = "final_dataset_with_aadhaar_centers.csv",
        data_year      = 2023,
        forecast_years = 5          # predict up to 2028
    )

    # ── Example: check a specific pincode ────────────────────────────────────
    print("\n── Single pincode lookup (2027 forecast) ──")
    predict_single_pincode(results_2023, pincode="786174", target_year=2027)

    # ── Example: check a whole state ─────────────────────────────────────────
    print("\n── State-level forecast: Karnataka ──")
    predict_single_pincode(results_2023, state="Karnataka")
