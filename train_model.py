import pandas as pd
import numpy as np
from sklearn.svm import SVC
import pickle

# Load training data
print("Loading training data...")
training = pd.read_csv('dataset/Training.csv')

# Prepare features and target
X = training.drop('prognosis', axis=1)
y = training['prognosis']

# Train SVC model
print("Training SVC model...")
svc = SVC(kernel='linear', probability=True)
svc.fit(X, y)

# Save the model
print("Saving model...")
with open('model/svc.pkl', 'wb') as f:
    pickle.dump(svc, f)

print("Model training and saving completed!") 