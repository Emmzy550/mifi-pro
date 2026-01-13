import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
import os

def generate_synthetic_data(samples=1000):
    np.random.seed(42)
    
    # Financial indicators
    income = np.random.uniform(200, 5000, samples)
    expenses = income * np.random.uniform(0.3, 0.9, samples)
    debt = np.random.uniform(0, 1000, samples)
    requested = np.random.uniform(100, 2000, samples)
    
    # Alternative data indicators
    airtime_usage = np.random.uniform(5, 100, samples)
    mm_tx_vol = np.random.uniform(10, 50, samples) # mobile money transactions per month
    saving_trend = np.random.uniform(-10, 10, samples) # monthly saving growth %
    
    # Hidden correlations for "Default"
    # Logic: Higher DTI, lower airtime, and negative saving trend increase default risk
    dti = debt / (income + 1e-6)
    risk_score = (dti * 5) + (100 / (airtime_usage + 1)) + (mm_tx_vol / 10) - (saving_trend / 2)
    noise = np.random.normal(0, 2, samples)
    
    # Target: 1 if default, 0 if repay
    y = (risk_score + noise > np.percentile(risk_score, 80)).astype(int)
    
    df = pd.DataFrame({
        'monthly_income': income,
        'monthly_expenses': expenses,
        'existing_debt': debt,
        'loan_amount_requested': requested,
        'airtime_usage_avg': airtime_usage,
        'mm_tx_vol': mm_tx_vol,
        'saving_trend': saving_trend,
        'target': y
    })
    return df

def train_bootstrap_model():
    print("Generating synthetic bootstrap data...")
    df = generate_synthetic_data()
    
    X = df.drop('target', axis=1)
    y = df['target']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Training XGBoost Risk Model...")
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        objective='binary:logistic'
    )
    model.fit(X_train, y_train)
    
    model_path = os.path.join("ml_models", "risk_model.json")
    model.get_booster().save_model(model_path)
    print(f"Model saved to {model_path}")
    
    # Save feature names for inference
    with open(os.path.join("ml_models", "features.txt"), "w") as f:
        f.write(",".join(X.columns.tolist()))

if __name__ == "__main__":
    train_bootstrap_model()
