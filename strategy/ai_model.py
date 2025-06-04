import numpy as np
import logging
import os
from typing import List, Dict, Any
from tensorflow.keras.models import load_model, Sequential
from tensorflow.keras.layers import Dense

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class AIModel:
    def __init__(self, model_path: str, input_dim: int = 4):  # input_dim за замовчуванням, змінюй під свою задачу
        """
        Initializes the AI model by loading a pre-trained model or creating a new one if not found.

        Args:
            model_path (str): Path to the pre-trained model file.
            input_dim (int): Number of input features for the model.
        """
        self.model_path = model_path
        if os.path.exists(model_path):
            try:
                self.model = load_model(model_path)
                logging.info(f"Model loaded successfully from {model_path}")
            except Exception as e:
                logging.error(f"Error loading model from {model_path}: {e}")
                raise
        else:
            # Створюємо нову просту модель, якщо файл не знайдено
            self.model = Sequential([
                Dense(64, input_dim=input_dim, activation='relu'),
                Dense(32, activation='relu'),
                Dense(2, activation='softmax')  # наприклад, для 2 класів (Buy/Sell), змінюй під свою задачу
            ])
            self.model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
            logging.info(f"No model found at {model_path}. Created a new model.")

    def preprocess_data(self, data: List[float], input_shape: tuple) -> np.array:
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
