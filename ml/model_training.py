# This script is responsible for training a machine learning model.

import os
import json
import numpy as np
import pandas as pd
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras.callbacks import ModelCheckpoint
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

def load_data(file_path, target_column):
    """
    Load and prepare data for training.

    Args:
        file_path (str): Path to the dataset file.
        target_column (str): The target column for prediction.

    Returns:
        tuple: Features (X) and target (y) dataframes.
    """
    data = pd.read_csv(file_path)
    X = data.drop(columns=[target_column])
    y = data[target_column]
    return X, y

def preprocess_data(X, y):
    """
    Preprocess features and target data.

    Args:
        X (pd.DataFrame): Features data.
        y (pd.Series): Target data.

    Returns:
        tuple: Scaled features and one-hot encoded target data.
    """
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    return X_scaled, y

def build_model(input_dim, output_dim):
    """
    Build a sequential neural network model.

    Args:
        input_dim (int): Number of input features.
        output_dim (int): Number of output classes.

    Returns:
        keras.Model: Compiled model.
    """
    model = Sequential([
        Dense(128, activation='relu', input_dim=input_dim),
        Dropout(0.3),
        Dense(64, activation='relu'),
        Dropout(0.3),
        Dense(output_dim, activation='softmax')
    ])
    model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
    return model

def save_metadata(metadata_path, input_shape, output_classes):
    """
    Save model metadata to a JSON file.

    Args:
        metadata_path (str): Path to the metadata file.
        input_shape (tuple): Shape of input data.
        output_classes (int): Number of output classes.
    """
    metadata = {
        "model_name": "TrainedModel",
        "version": "1.0",
        "description": "Trained machine learning model for classification.",
        "author": "Oleksandr812109",
        "created_date": "2025-05-01",
        "framework": "TensorFlow",
        "input_shape": input_shape,
        "output_classes": output_classes
    }
    with open(metadata_path, 'w') as file:
        json.dump(metadata, file, indent=4)
    print(f"Metadata saved to {metadata_path}")

if __name__ == "__main__":
    # Configuration
    data_path = "ml/data/dataset.csv"  # Path to your dataset
    target_column = "target"
    model_save_path = "ml/models/model.h5"
    metadata_save_path = "ml/models/metadata.json"

    # Load and preprocess data
    X, y = load_data(data_path, target_column)
    X_scaled, y_preprocessed = preprocess_data(X, y)

    # Split data into training and validation sets
    X_train, X_val, y_train, y_val = train_test_split(X_scaled, y_preprocessed, test_size=0.2, random_state=42)

    # Build and train the model
    model = build_model(input_dim=X_train.shape[1], output_dim=len(np.unique(y)))
    checkpoint = ModelCheckpoint(filepath=model_save_path, save_best_only=True, monitor='val_loss', mode='min')
    model.fit(X_train, y_train, validation_data=(X_val, y_val), epochs=20, batch_size=32, callbacks=[checkpoint])

    # Save metadata
    save_metadata(metadata_save_path, input_shape=X_train.shape[1:], output_classes=len(np.unique(y)))

    print("Model training and saving completed.")
