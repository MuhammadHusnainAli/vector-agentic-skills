import pandas as pd
from imblearn.pipeline import Pipeline
from imblearn.over_sampling import SMOTE
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.preprocessing import StandardScaler

df = pd.read_csv("churn.csv", parse_dates=["signup_date"]).sort_values("signup_date")
y = df["churned"]
X = df.drop(columns=["customer_id", "churned", "refund_issued", "cancellation_reason"])
pipe = Pipeline([("prep", ColumnTransformer([("num", StandardScaler(), ["tenure_months"])])),
                 ("smote", SMOTE()), ("model", LogisticRegression())])
print(cross_val_score(pipe, X, y, cv=TimeSeriesSplit(5)))
