import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sqlalchemy import create_engine
import os

# -------------------------------
# Step 1: Load Dataset
# -------------------------------

# Get current folder path
current_dir = os.path.dirname(os.path.abspath(__file__))

# File path (same folder)
file_path = r"C:\Users\saiba\OneDrive\Desktop\Adhar_mini_project\final_dataset_with_aadhaar_centers.csv"

df = pd.read_csv(file_path)

# Clean column names (VERY IMPORTANT)
df.columns = df.columns.str.lower().str.strip()

# -------------------------------
# Step 2: Feature Engineering
# -------------------------------

df["birthrate"] = df["birthrate"].fillna(0)
df["migrationrate"] = df["migrationrate"].fillna(0)
df["age_group15_19"] = df["age_group15_19"].fillna(0)

# Convert to decimal
df["birthrate"] = df["birthrate"] / 100
df["migrationrate"] = df["migrationrate"] / 100
df["agefactor"] = df["age_group15_19"] / 100

# Interaction features
df["pop_birth"] = df["population"] * df["birthrate"]
df["pop_migration"] = df["population"] * df["migrationrate"]
df["pop_youth"] = df["population"] * df["agefactor"]

# -------------------------------
# Step 3: Prepare ML Model
# -------------------------------

features = [
    "population",
    "pop_birth",
    "pop_migration",
    "pop_youth"
]

X = df[features]

# Target
y = df["aadhaar_centers"]

# Scaling
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Train model
model = LinearRegression()
model.fit(X_scaled, y)

# -------------------------------
# Step 4: Predict Current Centres
# -------------------------------

df["predicted_centres_current"] = model.predict(X_scaled)

# Ensure no negative predictions
df["predicted_centres_current"] = df["predicted_centres_current"].clip(lower=0)

# -------------------------------
# Step 5: Estimate Next Year Demand
# -------------------------------

df["estimated_demand_next_year"] = (
    df["population"] * (df["birthrate"] + 0.02) +
    df["population"] * df["migrationrate"] +
    df["population"] * df["agefactor"] * 0.4
)

# -------------------------------
# Step 6: Convert Demand → Centres
# -------------------------------

df["capacity_per_centre"] = np.where(
    df["population"] > 500000,
    25000,
    18000
)

df["required_centres_next_year"] = np.ceil(
    df["estimated_demand_next_year"] / df["capacity_per_centre"]
)

# -------------------------------
# Step 7: Extra Centres Needed
# -------------------------------

df["extra_centres_required"] = (
    df["required_centres_next_year"] - df["aadhaar_centers"]
)

# Ensure no negative values
df["extra_centres_required"] = df["extra_centres_required"].clip(lower=0)

# -------------------------------
# Step 8: Categorization (IMPORTANT for Power BI)
# -------------------------------

def categorize(x):
    if x > 10:
        return "High"
    elif x > 3:
        return "Medium"
    else:
        return "Low"

df["category"] = df["extra_centres_required"].apply(categorize)

# -------------------------------
# Step 9: Final Output
# -------------------------------

result = df[[
    "pincode",
    "population",
    "aadhaar_centers",
    "predicted_centres_current",
    "required_centres_next_year",
    "extra_centres_required",
    "category"
]]

# Save CSV (optional)
output_path = os.path.join(current_dir, "aadhaar_centre_prediction_output.csv")
result.to_csv(output_path, index=False)

print("✅ Output CSV generated!")
print(result.head(10))

# -------------------------------
# Step 10: Push to MySQL (Power BI)
# -------------------------------

# CHANGE PASSWORD HERE
engine = create_engine("mysql+pymysql://root:123456789@localhost/aadhaar_db")

result.to_sql("aadhaar_report", con=engine, if_exists="replace", index=False)

print("✅ Data uploaded to MySQL successfully!")