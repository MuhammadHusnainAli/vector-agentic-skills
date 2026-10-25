import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.feature_selection import SelectKBest
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler
import xgboost as xgb

df = pd.read_csv("churn.csv", parse_dates=["signup_date"])
df["monthly_charges"] = df["monthly_charges"].fillna(df["monthly_charges"].mean())
df["plan_rate"] = df.groupby("plan")["churned"].transform("mean")
y = df["churned"]
X = df.drop(columns=["customer_id"])

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)
selector = SelectKBest(k=10)
X_sel = selector.fit_transform(X_scaled, y)
X_res, y_res = SMOTE().fit_resample(X_sel, y)

X_train, X_test, y_train, y_test = train_test_split(X_res, y_res, test_size=0.2)
model = LogisticRegression()
print(cross_val_score(model, X_train, y_train, cv=5))
booster = xgb.XGBClassifier()
booster.fit(X_train, y_train, eval_set=[(X_test, y_test)])
scaler.fit(X_test)
