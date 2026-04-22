import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

# -------------------------------
# Step 1: Load Dataset
# -------------------------------
df = pd.read_csv("final_dataset_with_aadhaar_centers.csv")

# -------------------------------
# Step 2: Feature Engineering
# -------------------------------

# Convert to decimal
df["BirthRate"] = df["birthrate"] / 100
df["MigrationRate"] = df["migrationrate"] / 100
df["AgeFactor"] = df["age_group15_19"] / 100

# Interaction features (VERY IMPORTANT)
df["Pop_Birth"] = df["population"] * df["BirthRate"]
df["Pop_Migration"] = df["population"] * df["MigrationRate"]
df["Pop_Youth"] = df["population"] * df["AgeFactor"]

# -------------------------------
# Step 3: Prepare ML Model
# -------------------------------

features = [
    "population",
    "Pop_Birth",
    "Pop_Migration",
    "Pop_Youth"
]

X = df[features]

# 🎯 IMPORTANT CHANGE: real target
y = df["aadhaar_centers"]

# Scaling
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Train model
model = LinearRegression()
model.fit(X_scaled, y)

# -------------------------------
# Step 4: Predict Current Centres (model validation)
# -------------------------------
df["Predicted_Centres_Current"] = model.predict(X_scaled)

# -------------------------------
# Step 5: Estimate Next Year Demand
# -------------------------------

df["Estimated_Demand_Next_Year"] = (
    df["population"] * (df["BirthRate"] + 0.02) +
    df["population"] * df["MigrationRate"] +
    df["population"] * df["AgeFactor"] * 0.4
)

# -------------------------------
# Step 6: Convert Demand → Centres
# -------------------------------

# Dynamic capacity (urban areas need more handling)
df["Capacity_per_Centre"] = np.where(
    df["population"] > 500000,
    25000,
    18000
)

df["Required_Centres_Next_Year"] = np.ceil(
    df["Estimated_Demand_Next_Year"] / df["Capacity_per_Centre"]
)

# -------------------------------
# Step 7: Extra Centres Needed
# -------------------------------
df["Extra_Centres_Required"] = (
    df["Required_Centres_Next_Year"] - df["aadhaar_centers"]
)

df["Extra_Centres_Required"] = df["Extra_Centres_Required"].apply(lambda x: max(0, x))

# -------------------------------
# Step 8: Output
# -------------------------------
result = df[[
    "pincode",
    "population",
    "aadhaar_centers",
    "Predicted_Centres_Current",
    "Required_Centres_Next_Year",
    "Extra_Centres_Required"
]]

result.to_csv("aadhaar_centre_prediction_output.csv", index=False)

print(result.head(20))