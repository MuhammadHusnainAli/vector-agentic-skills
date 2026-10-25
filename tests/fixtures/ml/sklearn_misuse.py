import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import mean_squared_error, roc_auc_score
from sklearn.model_selection import GridSearchCV, KFold, train_test_split
from sklearn.preprocessing import FunctionTransformer, LabelEncoder, OneHotEncoder

df = pd.read_csv("data.csv")
df["plan"] = LabelEncoder().fit_transform(df["plan"])
X = pd.get_dummies(df.drop(columns=["y"]))
y = df["y"]
X_train, X_test, y_train, y_test = train_test_split(X, y)
enc = OneHotEncoder(sparse=False)
log_tf = FunctionTransformer(lambda v: v + 1)
prep = ColumnTransformer([("oh", enc, ["region"])])
clf = LogisticRegression(penalty="none")
clf.fit(X, y)
print(clf.score(X, y))
print(roc_auc_score(y_test, clf.predict(X_test)))
rf = RandomForestClassifier(max_features="auto")
search = GridSearchCV(RandomForestClassifier(n_jobs=-1), {"max_depth": [3, 5]}, n_jobs=-1)
cv = KFold(5, shuffle=True)
print(mean_squared_error(y_test, clf.predict(X_test), squared=False))
