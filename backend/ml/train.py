import pandas as pd, joblib, csv, datetime as dt, random, numpy as np
import os
from sklearn.exceptions import UndefinedMetricWarning
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.dummy import DummyClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score, GridSearchCV, train_test_split
from sklearn.metrics import classification_report
import warnings
 
warnings.filterwarnings('ignore', category=UndefinedMetricWarning)
SEED = 42
random.seed(SEED); np.random.seed(SEED)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
df = pd.read_csv(os.path.join(BASE_DIR, 'destinations.csv'))

X = df.drop(columns=['city', 'country', 'travel_style'])
y = df['travel_style']
print(f"Dataset loaded: {len(df)} rows, {X.shape[1]} features, {y.nunique()} classes")
 
# stratify=y preserves class balance in the test split
# Without this, if Luxury has 8 rows, it might all end up in train
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=SEED)

warnings.filterwarnings('ignore', category=UndefinedMetricWarning)
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
 
models = {
  'baseline': DummyClassifier(strategy='most_frequent', random_state=SEED),
  'logreg':   Pipeline([('scaler', StandardScaler()),
                        ('clf', LogisticRegression(max_iter=1000, class_weight='balanced'))]),
  'rf':       Pipeline([('clf', RandomForestClassifier(random_state=SEED, class_weight='balanced'))]),
  'gb':       Pipeline([('clf', GradientBoostingClassifier(random_state=SEED))]),
}

# Compare all Models
rows = []
for name, pipe in models.items():
    f1 = cross_val_score(pipe, X_train, y_train, cv=cv, scoring='f1_macro')
    acc = cross_val_score(pipe, X_train, y_train, cv=cv, scoring='accuracy')
    auc = cross_val_score(pipe, X_train, y_train, cv=cv, scoring='roc_auc_ovr')
    prec = cross_val_score(pipe, X_train, y_train, cv=cv, scoring='precision_macro')
    rec = cross_val_score(pipe, X_train, y_train, cv=cv, scoring='recall_macro')
    rows.append({'model': name, 'f1_mean': f1.mean(), 'f1_std': f1.std(),
                 'acc_mean': acc.mean(),
                 'auc_mean': auc.mean(),
                 'prec_mean': prec.mean(),
                 'rec_mean': rec.mean(),
                 'params': 'default',
                 'timestamp': dt.datetime.now(dt.timezone.utc).isoformat()
})

results_df = pd.DataFrame(rows)
print("\n--- Full Results Table ---")
print(results_df.to_string(index=False))


# Tuning RF and GB
rf_params = {
    'clf__n_estimators': [100, 200, 300],
    'clf__max_depth': [None, 5, 10, 15],
    'clf__min_samples_split': [2, 5, 10],
}

gb_params = {
    'clf__n_estimators': [100, 200, 300],
    'clf__max_depth': [3, 5, 7],
    'clf__learning_rate': [0.01, 0.1, 0.2],
}

grids = {
    'rf_tuned': (models['rf'], rf_params),
    'gb_tuned': (models['gb'], gb_params),
}

tuned_rows = []
tuned_estimators = {}

for name, (pipe, params) in grids.items():
    grid = GridSearchCV(
        pipe, params,
        cv=cv,
        scoring='f1_macro',
        n_jobs=-1,
        verbose=1
    )
    grid.fit(X_train, y_train)
    
    best = grid.best_estimator_
    tuned_estimators[name] = best

    f1   = cross_val_score(best, X_train, y_train, cv=cv, scoring='f1_macro')
    acc  = cross_val_score(best, X_train, y_train, cv=cv, scoring='accuracy')
    auc  = cross_val_score(best, X_train, y_train, cv=cv, scoring='roc_auc_ovr_weighted')
    prec = cross_val_score(best, X_train, y_train, cv=cv, scoring='precision_macro')
    rec  = cross_val_score(best, X_train, y_train, cv=cv, scoring='recall_macro')

    tuned_rows.append({
        'model':      name,
        'f1_mean':    f1.mean(),
        'f1_std':     f1.std(),
        'acc_mean':   acc.mean(),
        'auc_mean':   auc.mean(),
        'prec_mean':  prec.mean(),
        'rec_mean':   rec.mean(),
        'params':     str(grid.best_params_),
        'timestamp':  dt.datetime.now(dt.timezone.utc).isoformat()
    })

print("\n--- Tuned Results ---")
for r in tuned_rows:
    print(f"{r['model']:10s} | F1: {r['f1_mean']:.4f} ± {r['f1_std']:.4f} | Accuracy: {r['acc_mean']:.4f} | AUC: {r['auc_mean']:.4f} | Precision: {r['prec_mean']:.4f} | Recall: {r['rec_mean']:.4f} | Params: {r['params']}")
 
# Per-class metrics on test set
winner = tuned_estimators['rf_tuned'] if tuned_rows[0]['auc_mean'] > tuned_rows[1]['auc_mean'] else tuned_estimators['gb_tuned']
winner.fit(X_train, y_train)
print("The winner is:", winner, classification_report(y_test,winner.predict(X_test)))
 
# Retrain winner on all data and save
winner.fit(X, y)
joblib.dump(winner, os.path.join(BASE_DIR, 'classifier.joblib'))
print(f"\nModel saved: classifier.joblib — {dt.datetime.now(dt.timezone.utc).isoformat()}")

# Save all results to results.csv
all_rows = rows + tuned_rows
fieldnames = [
    'model',
    'f1_mean',    'f1_std',
    'acc_mean',
    'auc_mean',
    'prec_mean',
    'rec_mean',
    'params',     'timestamp'
]

with open(os.path.join(BASE_DIR, 'results.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(all_rows)

# Print final results
print("\n--- Final results.csv ---")
print(pd.read_csv(os.path.join(BASE_DIR, 'results.csv')).to_string(index=False))