from typing import Dict, Optional
import xgboost as xgb
import numpy as np
import json
from pathlib import Path
from app.core.config import settings
import math
import random

class MLService:
    def __init__(self):
        # Load the trained XGBoost model
        self.model_loaded = False
        self.model = None
        self.feature_names = [
            "elevation",
            "slope",
            "aspect",
            "landslide_susceptibility_prob",
            "landslide_susceptibility_class",
            "annual_normal_mm",
            "monsoon_daily_mean_mm",
            "moderate_threshold_24h_mm",
            "high_threshold_24h_mm",
            "extreme_threshold_24h_mm"
        ]
        self.confidence_threshold = 0.6  # Minimum confidence to apply ML prediction
        self._load_model()

    def _load_model(self):
        """Load the XGBoost model from the risk_model.json file."""
        try:
            model_path = Path(__file__).resolve().parents[2] / "risk_model.json"
            if model_path.exists():
                self.model = xgb.Booster()
                self.model.load_model(str(model_path))
                self.model_loaded = True
                print(f"[MLService] Successfully loaded XGBoost model from {model_path}")
            else:
                print(f"[MLService] Warning: Model file not found at {model_path}")
                # Fallback to rule-based stub if model not found
                self.model_loaded = False
        except Exception as e:
            print(f"[MLService] Error loading model: {e}")
            # Fallback to rule-based stub if model loading fails
            self.model_loaded = False

    async def predict_segment_status(self, segment_id: int, external_data: Dict) -> Dict[str, Optional[str]]:
        """
        Predict the accessibility status for a road segment based on external data.

        Args:
            segment_id: The ID of the road segment
            external_data: Dictionary containing external data like weather, etc.

        Returns:
            Dictionary with keys:
                - status: One of "OPEN", "DEGRADED", "BLOCKED" or None if confidence too low
                - confidence: Float between 0 and 1 indicating prediction confidence
                - model_version: String indicating the model version used
        """
        # If model failed to load, fall back to rule-based stub
        if not self.model_loaded or self.model is None:
            return await self._rule_based_prediction(external_data)

        try:
            # Prepare features for the model
            features = self._prepare_features(external_data)
            if features is None:
                # If we couldn't prepare features, fall back to rule-based
                return await self._rule_based_prediction(external_data)

            # Make prediction using XGBoost
            # Convert to DMatrix for prediction
            dmatrix = xgb.DMatrix(features.reshape(1, -1), feature_names=self.feature_names)

            # Get prediction probabilities (for multi-class classification)
            # Assuming the model outputs probabilities for 3 classes: OPEN, DEGRADED, BLOCKED
            pred_probs = self.model.predict(dmatrix)

            # XGBoost classifier typically returns probabilities for each class
            # Shape should be (1, num_classes) where num_classes is 3
            if len(pred_probs.shape) == 1:
                # If it's a 1D array, it might be just the predicted class indices
                # We need to get probabilities, so let's use predict with output_margin=False
                pred_probs = self.model.predict(dmatrix, output_margin=False)
                if len(pred_probs.shape) == 1:
                    # Still 1D, might need to reshape or get probabilities differently
                    # For binary classification, XGBoost returns probability of positive class
                    # For multi-class, we might need to use a different approach
                    # Let's assume it's returning probabilities for each class in order
                    # We'll reshape it to (1, 3) assuming 3 classes
                    pred_probs = pred_probs.reshape(1, -1)

            # Get the class with highest probability
            predicted_class_idx = np.argmax(pred_probs[0])
            confidence = float(pred_probs[0][predicted_class_idx])

            # Map class index to status
            # Assuming class order: 0=OPEN, 1=DEGRADED, 2=BLOCKED
            # This should match the training data ordering
            status_map = {0: "OPEN", 1: "DEGRADED", 2: "BLOCKED"}
            predicted_status = status_map.get(predicted_class_idx, "OPEN")

            # Only return the prediction if confidence exceeds threshold
            # Otherwise, return None for status to indicate ML prediction should not be used
            if confidence < self.confidence_threshold:
                return {
                    "status": None,
                    "confidence": confidence,
                    "model_version": "xgboost-risk-model-v1"
                }

            return {
                "status": predicted_status,
                "confidence": confidence,
                "model_version": "xgboost-risk-model-v1"
            }

        except Exception as e:
            print(f"[MLService] Error during prediction: {e}")
            # Fall back to rule-based prediction on error
            return await self._rule_based_prediction(external_data)

    def _prepare_features(self, external_data: Dict) -> Optional[np.ndarray]:
        """
        Prepare features from external_data for the XGBoost model.

        Args:
            external_data: Dictionary containing external data

        Returns:
            Numpy array of features in the correct order, or None if preparation fails
        """
        try:
            # Extract features in the order expected by the model
            feature_values = []

            for feature_name in self.feature_names:
                value = external_data.get(feature_name)

                # Handle missing values
                if value is None:
                    # Provide default values for missing features
                    if feature_name in ["elevation", "slope", "aspect"]:
                        value = 0.0  # Default for topographical features
                    elif feature_name in ["landslide_susceptibility_prob"]:
                        value = 0.1  # Low probability by default
                    elif feature_name in ["landslide_susceptibility_class"]:
                        value = 1.0  # Low susceptibility class by default
                    elif feature_name in ["annual_normal_mm"]:
                        value = 1000.0  # Moderate annual rainfall by default
                    elif feature_name in ["monsoon_daily_mean_mm"]:
                        value = 20.0  # Moderate monsoon rainfall by default
                    elif feature_name in ["moderate_threshold_24h_mm"]:
                        value = 50.0  # Moderate threshold by default
                    elif feature_name in ["high_threshold_24h_mm"]:
                        value = 100.0  # High threshold by default
                    elif feature_name in ["extreme_threshold_24h_mm"]:
                        value = 150.0  # Extreme threshold by default

                # Convert to appropriate type
                if feature_name in ["landslide_susceptibility_class", "annual_normal_mm"]:
                    # These should be integers according to feature_types in the model
                    value = int(float(value))
                else:
                    # These should be floats
                    value = float(value)

                feature_values.append(value)

            return np.array(feature_values, dtype=np.float32)

        except Exception as e:
            print(f"[MLService] Error preparing features: {e}")
            return None

    async def _rule_based_prediction(self, external_data: Dict) -> Dict[str, Optional[str]]:
        """
        Rule-based stub prediction as fallback when ML model is not available.
        This is the original implementation kept as backup.
        """
        # Extract relevant data from external_data
        temperature = external_data.get('temperature', 20)  # Celsius
        precipitation = external_data.get('precipitation', 0)  # mm/hour
        wind_speed = external_data.get('wind_speed', 0)  # km/h
        visibility = external_data.get('visibility', 10000)  # meters

        # Simple rule-based logic for demonstration
        # In reality, this would be much more sophisticated

        # Initialize scores for each status
        scores = {
            "OPEN": 0.0,
            "DEGRADED": 0.0,
            "BLOCKED": 0.0
        }

        # Temperature effects (extreme temperatures can affect road conditions)
        if temperature < -10 or temperature > 45:
            scores["BLOCKED"] += 0.3
            scores["DEGRADED"] += 0.4
        elif temperature < 0 or temperature > 35:
            scores["DEGRADED"] += 0.3
            scores["OPEN"] += 0.1
        else:
            scores["OPEN"] += 0.4

        # Precipitation effects (rain, snow can make roads slippery or flooded)
        if precipitation > 50:  # Heavy precipitation
            scores["BLOCKED"] += 0.4
            scores["DEGRADED"] += 0.3
        elif precipitation > 10:  # Moderate precipitation
            scores["DEGRADED"] += 0.4
            scores["OPEN"] += 0.2
        else:  # Light or no precipitation
            scores["OPEN"] += 0.4

        # Wind effects (high wind can cause debris, dust, or make driving difficult)
        if wind_speed > 80:  # Very strong wind
            scores["BLOCKED"] += 0.2
            scores["DEGRADED"] += 0.3
        elif wind_speed > 50:  # Strong wind
            scores["DEGRADED"] += 0.3
            scores["OPEN"] += 0.1
        else:
            scores["OPEN"] += 0.2

        # Visibility effects (poor visibility affects driving safety)
        if visibility < 100:  # Very poor visibility
            scores["BLOCKED"] += 0.3
            scores["DEGRADED"] += 0.4
        elif visibility < 500:  # Poor visibility
            scores["DEGRADED"] += 0.3
            scores["OPEN"] += 0.1
        else:  # Good visibility
            scores["OPEN"] += 0.3

        # Normalize scores to get probabilities
        total_score = sum(scores.values())
        if total_score > 0:
            probabilities = {k: v/total_score for k, v in scores.items()}
        else:
            # Default to open if no factors detected
            probabilities = {"OPEN": 0.7, "DEGRADED": 0.2, "BLOCKED": 0.1}

        # Find the status with highest probability
        predicted_status = max(probabilities, key=probabilities.get)
        confidence = probabilities[predicted_status]

        # Only return the prediction if confidence exceeds threshold
        # Otherwise, return None for status to indicate ML prediction should not be used
        if confidence < self.confidence_threshold:
            return {
                "status": None,
                "confidence": confidence,
                "model_version": "rule-based-stub-v1"
            }

        return {
            "status": predicted_status,
            "confidence": confidence,
            "model_version": "rule-based-stub-v1"
        }

    def is_model_loaded(self) -> bool:
        """Check if the ML model is loaded."""
        return self.model_loaded

    async def load_model(self, model_path: str):
        """
        Load a trained ML model from the specified path.
        In a real implementation, this would load an actual ML model.
        """
        try:
            self.model = xgb.Booster()
            self.model.load_model(model_path)
            self.model_loaded = True
            print(f"[MLService] Successfully loaded model from {model_path}")
        except Exception as e:
            print(f"[MLService] Error loading model from {model_path}: {e}")
            self.model_loaded = False