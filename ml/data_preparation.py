# This script is responsible for preparing data for machine learning models.

import pandas as pd
from sklearn.model_selection import train_test_split

def load_data(file_path):
    """
    Load data from a CSV file.

    Args:
        file_path (str): Path to the CSV file.

    Returns:
        pd.DataFrame: Loaded data.
    """
    try:
        data = pd.read_csv(file_path)
        print(f"Data loaded successfully from {file_path}")
        return data
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return None

def preprocess_data(data):
    """
    Perform data preprocessing steps such as cleaning, encoding, and scaling.

    Args:
        data (pd.DataFrame): Raw data.

    Returns:
        pd.DataFrame: Preprocessed data.
    """
    # Example: Drop missing values
    data = data.dropna()
    print("Missing values dropped.")

    # Example: Convert categorical columns to dummy variables
    data = pd.get_dummies(data, drop_first=True)
    print("Categorical variables encoded.")

    return data

def split_data(data, target_column, test_size=0.2):
    """
    Split the data into training and testing sets.

    Args:
        data (pd.DataFrame): Preprocessed data.
        target_column (str): Name of the target column.
        test_size (float): Proportion of the dataset to include in the test split.

    Returns:
        tuple: Training and testing sets (X_train, X_test, y_train, y_test).
    """
    X = data.drop(columns=[target_column])
    y = data[target_column]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=42)
    print(f"Data split into training and testing sets with test size = {test_size}")
    return X_train, X_test, y_train, y_test

if __name__ == "__main__":
    # Example usage
    file_path = "data/sample_data.csv"
    target_column = "target"

    # Load the data
    raw_data = load_data(file_path)

    if raw_data is not None:
        # Preprocess the data
        processed_data = preprocess_data(raw_data)

        # Split the data
        X_train, X_test, y_train, y_test = split_data(processed_data, target_column)

        print("Data preparation is complete.")
