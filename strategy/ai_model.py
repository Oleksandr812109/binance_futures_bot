import numpy as np
import logging
from typing import List, Dict, Any
from tensorflow.keras.models import load_model

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class AIModel:
    def __init__(self, model_path: str):
        """
        Initializes the AI model by loading a pre-trained model.

        Args:
            model_path (str): Path to the pre-trained model file.
        """
        try:
            self.model = load_model(model_path)
            logging.info(f"Model loaded successfully from {model_path}")
        except Exception as e:
            logging.error(f"Error loading model from {model_path}: {e}")
            raise

    def preprocess_data(self, data: List[float], input_shape: tuple) -> np.array:
        """
        Preprocesses input data to match the model's expected input shape.

        Args:
            data (List[float]): Raw input data.
            input_shape (tuple): Expected input shape for the model.

        Returns:
            np.array: Preprocessed input data.
        """
        try:
            data = np.array(data, dtype=np.float32)
            if len(data.shape) == 1:
                data = data.reshape((1, *input_shape))
            logging.info(f"Input data preprocessed to shape: {data.shape}")
            return data
        except Exception as e:
            logging.error(f"Error preprocessing input data: {e}")
            raise

    def predict(self, input_data: List[float], input_shape: tuple) -> Dict[str, Any]:
        """
        Makes a prediction using the pre-trained model.

        Args:
            input_data (List[float]): Input data for prediction.
            input_shape (tuple): Expected input shape for the model.

        Returns:
            Dict[str, Any]: Prediction results.
        """
        try:
            preprocessed_data = self.preprocess_data(input_data, input_shape)
            predictions = self.model.predict(preprocessed_data)
            strategy = np.argmax(predictions, axis=1)[0]  # Assuming classification task
            confidence = predictions[0][strategy]  # Confidence score for the predicted strategy
            logging.info(f"Prediction made successfully: Strategy={strategy}, Confidence={confidence:.2f}")
            return {"strategy": strategy, "confidence": confidence}
        except Exception as e:
            logging.error(f"Error during prediction: {e}")
            raise

if __name__ == "__main__":
    # Example usage
    model_path = "ml/models/trade_strategy_model.h5"
    input_data = [0.5, 0.3, 0.2, 0.1]  # Example input data
    input_shape = (4,)  # Example input shape

    try:
        ai_model = AIModel(model_path)
        result = ai_model.predict(input_data, input_shape)
        print(f"Predicted Strategy: {result['strategy']}, Confidence: {result['confidence']:.2f}")
    except Exception as e:
        logging.error(f"An error occurred: {e}")
