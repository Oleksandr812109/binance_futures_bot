# This script is responsible for running inference using a pre-trained machine learning model.

import json
import numpy as np
from tensorflow.keras.models import load_model

def load_metadata(metadata_path):
    """
    Load metadata for the model.

    Args:
        metadata_path (str): Path to the metadata JSON file.

    Returns:
        dict: Metadata dictionary.
    """
    try:
        with open(metadata_path, 'r') as file:
            metadata = json.load(file)
        print("Metadata loaded successfully.")
        return metadata
    except FileNotFoundError:
        print(f"Metadata file not found: {metadata_path}")
        return None

def load_trained_model(model_path):
    """
    Load a pre-trained model.

    Args:
        model_path (str): Path to the saved model file.

    Returns:
        keras.Model: Loaded Keras model.
    """
    try:
        model = load_model(model_path)
        print("Model loaded successfully.")
        return model
    except Exception as e:
        print(f"Error loading model: {e}")
        return None

def preprocess_input(data, input_shape):
    """
    Preprocess input data to match the model's expected input shape.

    Args:
        data (np.array): Raw input data.
        input_shape (tuple): Shape expected by the model.

    Returns:
        np.array: Preprocessed data.
    """
    try:
        processed_data = np.array(data).reshape((-1, *input_shape))
        print("Input data preprocessed successfully.")
        return processed_data
    except Exception as e:
        print(f"Error preprocessing input data: {e}")
        return None

def make_prediction(model, input_data):
    """
    Run inference using the model.

    Args:
        model (keras.Model): Pre-trained model.
        input_data (np.array): Preprocessed input data.

    Returns:
        np.array: Model predictions.
    """
    try:
        predictions = model.predict(input_data)
        print("Inference completed successfully.")
        return predictions
    except Exception as e:
        print(f"Error during inference: {e}")
        return None

if __name__ == "__main__":
    # Example usage
    metadata_path = "ml/models/metadata.json"
    model_path = "ml/models/model.h5"
    input_data = [[0.1, 0.2, 0.3, 0.4]]  # Example input data

    # Load metadata
    metadata = load_metadata(metadata_path)

    if metadata:
        # Load model
        model = load_trained_model(model_path)

        if model:
            # Preprocess input
            processed_data = preprocess_input(input_data, metadata['input_shape'])

            if processed_data is not None:
                # Make prediction
                predictions = make_prediction(model, processed_data)
                print(f"Predictions: {predictions}")
