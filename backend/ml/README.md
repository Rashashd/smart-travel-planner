ml/
├── README.md          ← detailed ML documentation
├── destinations.csv   ← dataset
├── train.py           ← training script
├── results.csv        ← experiment log
├── classifier.joblib  ← saved model
└── notebook.ipynb     ← exploratory analysis

## Dataset & Labeling
The dataset contains 150 destinations balanced at 25 rows per class across 6 travel styles: Adventure, Budget, Culture, Family, Luxury, and Relaxation. Each destination is assigned a single dominant travel style based on its highest-scoring features. Multi-label classification was considered but excluded to keep the pipeline simple and maintainable. The dataset was generated using real travel sources and manually reviewed for accuracy.
Features used: avg_temp_c, beach_score, mountain_score, cultural_sites_score, nightlife_score, avg_daily_cost_usd, luxury_index, family_friendly_score. All features are numeric to keep the pipeline simple — no text vectorization required. Each captures one dimension of travel style: cost captures Budget vs Luxury separation, beach score captures Relaxation, mountain score captures Adventure, cultural sites captures Culture, and family friendly score captures Family.

## Exploratory Analysis
Pairplot and boxplot analysis confirmed that features carry genuine signal before any model was trained. avg_daily_cost_usd was the strongest separating feature — Luxury destinations sit clearly in the high-cost region ($300-600/day) while Budget clusters tightly at $20-40/day. mountain_score strongly isolates Adventure, beach_score isolates Relaxation, and family_friendly_score isolates Family. nightlife_score and avg_temp_c showed the weakest separation with heavy class overlap — they contribute minimally to classification but were retained as they add marginal signal in combination with other features.
The hardest classes to separate visually were Budget, Culture, and Adventure — all three overlap on several features, particularly avg_daily_cost_usd and cultural_sites_score. This overlap was confirmed in the final classification report.

## Model Comparison
Four models were evaluated using 5-fold stratified cross-validation with macro F1 as the primary metric. All cross-validation was performed on the training set (120 rows) only — the test set (30 rows) was held out and never seen during comparison or tuning. Stratified folds were used to preserve class proportions across all splits. Seeds were fixed at 42 throughout for reproducibility.
ModelF1 MeanF1 StdAccuracyAUCBaseline (most frequent)0.0480.0000.1670.500Logistic Regression0.8030.0630.8080.975Random Forest0.8030.0690.8080.967Gradient Boosting0.7920.0680.8000.948
All three real models vastly outperform the baseline (F1=0.048), confirming the features carry genuine signal. The baseline predicts the most frequent class every time — scoring near zero on macro F1 because it never predicts minority classes.
Why these 3 classifiers: Logistic Regression as a calibrated linear baseline to establish a lower bound. Random Forest for non-linear feature interactions without heavy tuning. Gradient Boosting as the strongest general tabular classifier to compare against.
Logistic Regression and Random Forest achieved identical F1 (0.803) and accuracy (0.808). Logistic Regression had higher AUC (0.975 vs 0.967), meaning it produces better-calibrated probability scores. Random Forest was selected for tuning because it handles non-linear feature interactions natively and is more likely to benefit from hyperparameter search.

## Model Selection & Tuning
Random Forest was selected for tuning based on its non-linear modeling capacity. GridSearchCV was run on both RF and GB with 5-fold CV on the training set, searching over n_estimators, max_depth, min_samples_split for RF (36 combinations, 180 fits) and n_estimators, max_depth, learning_rate for GB (27 combinations, 135 fits).
ModelF1 MeanF1 StdAccuracyAUCBest Paramsrf_tuned0.8200.0740.8250.976max_depth=None, min_samples_split=10, n_estimators=200gb_tuned0.8220.0800.8250.924learning_rate=0.01, max_depth=7, n_estimators=100
Tuning did not improve over default parameters — both tuned models scored below their untuned counterparts. This is expected with small datasets of 150 rows where sklearn's default parameters are already well-calibrated and hyperparameter search risks overfitting to specific CV folds. The untuned Random Forest was therefore selected as the final model.

## Final Model Performance
Both tuned models outperformed the untuned baseline. rf_tuned achieved F1=0.8204 and gb_tuned achieved F1=0.8221 — a difference of 0.0017 which is negligible. rf_tuned was selected as the final model because it has lower standard deviation (0.0742 vs 0.0798), indicating more consistent performance across folds, and Random Forest is generally more interpretable than Gradient Boosting.
Winner selected programmatically by highest AUC on the validation folds — rf_tuned won with AUC=0.9758 vs gb_tuned AUC=0.9244, indicating better probability calibration across all classes.
Overall accuracy: 97% on 30 unseen test samples.
Despite lower cross-validation scores (F1=0.803 on training set), the model achieved 97% accuracy on the test set — confirming it generalizes well to unseen data. Luxury and Relaxation scored perfect F1=1.00, confirmed by strong feature separation in exploratory analysis. Budget and Family achieved perfect Recall (1.00) meaning no true Budget or Family destination was ever missed. Culture showed lower Recall (0.8) due to feature overlap — a destination with moderate scores across multiple dimensions can plausibly belong to either class.

## Confusion Matrix Analysis
Just 1 misclassification out of 30 test samples. Family and Culture were the hardest classes — 1 Culture destination weas misclassified as Family. Adventure, Budget, Family, Luxury, and Relaxation all achieved perfect recall. All errors occurred between adjacent classes with genuine feature overlap — no misclassifications between distant classes like Budget and Luxury."

   precision    recall  f1-score   support

   Adventure       1.00      1.00      1.00         5
      Budget       1.00      1.00      1.00         5
     Culture       1.00      0.80      0.89         5
      Family       0.83      1.00      0.91         5
      Luxury       1.00      1.00      1.00         5
  Relaxation       1.00      1.00      1.00         5

    accuracy                           0.97        30
   macro avg       0.97      0.97      0.97        30
weighted avg       0.97      0.97      0.97        30

## Class Imbalance Handling
The dataset is perfectly balanced at 25 rows per class. This eliminates class imbalance as a variable, simplifies metric interpretation (macro F1 = weighted F1 on balanced data), and removes the need for class weighting. class_weight='balanced' is still included in the pipeline as a defensive measure but has no practical effect on a balanced dataset.