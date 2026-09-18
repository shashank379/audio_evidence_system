
import os
import numpy as np
import librosa
import pickle
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from google.colab import drive
import requests
import io

class ColabAudioAnalyzer:
    def __init__(self):
        self.tamper_model = None
        self.scaler = None
        self.model_path = '/content/drive/MyDrive/audio_evidence_models/'
        
    def mount_drive(self):
        '''Mount Google Drive to access/save models'''
        try:
            drive.mount('/content/drive')
            os.makedirs(self.model_path, exist_ok=True)
            print("Google Drive mounted successfully!")
            return True
        except Exception as e:
            print(f"Failed to mount drive: {e}")
            return False
            
    def generate_training_data(self, num_samples=5000):
        '''Generate synthetic training data for tamper detection'''
        print("Generating synthetic training data...")
        
        # Feature dimensions: 13 MFCC mean + 13 MFCC std + spectral features
        feature_dim = 28
        
        # Generate authentic audio features
        authentic_features = []
        for _ in range(num_samples // 2):
            # Simulate authentic audio characteristics
            mfcc_mean = np.random.normal(0, 1, 13)  # Typical MFCC values
            mfcc_std = np.random.exponential(0.5, 13)  # Typical MFCC variance
            spectral_centroid = np.random.normal(2000, 500)  # Typical spectral centroid
            spectral_rolloff = np.random.normal(4000, 1000)  # Typical rolloff
            zcr = np.random.beta(2, 5)  # Typical zero crossing rate
            
            features = np.concatenate([
                mfcc_mean, mfcc_std, [spectral_centroid], [spectral_rolloff], [zcr]
            ])
            authentic_features.append(features)
        
        # Generate tampered audio features (with artifacts)
        tampered_features = []
        for _ in range(num_samples // 2):
            # Simulate tampered audio with artifacts
            mfcc_mean = np.random.normal(0, 1.5, 13)  # More variance in tampered
            mfcc_std = np.random.exponential(1.0, 13)  # Higher variance
            
            # Add tampering artifacts
            spectral_centroid = np.random.normal(2500, 800)  # Shifted spectrum
            spectral_rolloff = np.random.normal(3500, 1200)  # Different rolloff
            zcr = np.random.beta(1, 3)  # Different ZCR pattern
            
            features = np.concatenate([
                mfcc_mean, mfcc_std, [spectral_centroid], [spectral_rolloff], [zcr]
            ])
            tampered_features.append(features)
        
        # Combine features and labels
        X = np.vstack([authentic_features, tampered_features])
        y = np.hstack([np.zeros(len(authentic_features)), np.ones(len(tampered_features))])
        
        return X, y
    
    def train_tamper_detection_model(self):
        '''Train the tamper detection model'''
        print("Training tamper detection model...")
        
        # Generate training data
        X, y = self.generate_training_data()
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Scale features
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train model
        self.tamper_model = RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42
        )
        
        self.tamper_model.fit(X_train_scaled, y_train)
        
        # Evaluate model
        y_pred = self.tamper_model.predict(X_test_scaled)
        accuracy = accuracy_score(y_test, y_pred)
        
        print(f"Model trained successfully!")
        print(f"Test Accuracy: {accuracy:.4f}")
        print(f"Classification Report:")
        print(classification_report(y_test, y_pred, target_names=['Authentic', 'Tampered']))
        
        return accuracy
    
    def save_model(self):
        '''Save trained model to Google Drive'''
        if self.tamper_model is None or self.scaler is None:
            print("No model to save. Train the model first.")
            return False
            
        try:
            # Save model
            model_file = os.path.join(self.model_path, 'tamper_detection_model.pkl')
            with open(model_file, 'wb') as f:
                pickle.dump(self.tamper_model, f)
            
            # Save scaler
            scaler_file = os.path.join(self.model_path, 'feature_scaler.pkl')
            with open(scaler_file, 'wb') as f:
                pickle.dump(self.scaler, f)
            
            print(f"Model saved to: {model_file}")
            print(f"Scaler saved to: {scaler_file}")
            return True
            
        except Exception as e:
            print(f"Failed to save model: {e}")
            return False
    
    def load_model(self):
        '''Load trained model from Google Drive'''
        try:
            model_file = os.path.join(self.model_path, 'tamper_detection_model.pkl')
            scaler_file = os.path.join(self.model_path, 'feature_scaler.pkl')
            
            if os.path.exists(model_file) and os.path.exists(scaler_file):
                with open(model_file, 'rb') as f:
                    self.tamper_model = pickle.load(f)
                
                with open(scaler_file, 'rb') as f:
                    self.scaler = pickle.load(f)
                
                print("Model loaded successfully!")
                return True
            else:
                print("Model files not found. Please train the model first.")
                return False
                
        except Exception as e:
            print(f"Failed to load model: {e}")
            return False
    
    def extract_features(self, audio_path):
        '''Extract features from audio file'''
        try:
            y, sr = librosa.load(audio_path, sr=22050)
            
            # Trim silence
            y_trimmed, _ = librosa.effects.trim(y, top_db=20)
            
            # Extract MFCC features
            mfccs = librosa.feature.mfcc(y=y_trimmed, sr=sr, n_mfcc=13)
            
            # Extract spectral features
            spectral_centroids = librosa.feature.spectral_centroid(y=y_trimmed, sr=sr)
            spectral_rolloff = librosa.feature.spectral_rolloff(y=y_trimmed, sr=sr)
            zero_crossing_rate = librosa.feature.zero_crossing_rate(y_trimmed)
            
            # Combine features
            features = np.concatenate([
                np.mean(mfccs, axis=1),
                np.std(mfccs, axis=1),
                np.mean(spectral_centroids),
                np.mean(spectral_rolloff),
                np.mean(zero_crossing_rate)
            ])
            
            return features
            
        except Exception as e:
            print(f"Feature extraction failed: {e}")
            return None
    
    def predict_tampering(self, features):
        '''Predict if audio is tampered'''
        if self.tamper_model is None or self.scaler is None:
            print("Model not loaded. Load or train the model first.")
            return None
        
        try:
            # Scale features
            features_scaled = self.scaler.transform(features.reshape(1, -1))
            
            # Make prediction
            prediction = self.tamper_model.predict(features_scaled)[0]
            confidence = self.tamper_model.predict_proba(features_scaled)[0].max()
            
            result = "Tampered" if prediction == 1 else "Authentic"
            
            return {
                'result': result,
                'confidence': float(confidence),
                'prediction': int(prediction)
            }
            
        except Exception as e:
            print(f"Prediction failed: {e}")
            return None

# Example usage in Colab
def main():
    '''Main function to run in Colab'''
    print("=== Audio Evidence Analysis in Colab ===")
    
    # Initialize analyzer
    analyzer = ColabAudioAnalyzer()
    
    # Mount Google Drive
    if not analyzer.mount_drive():
        print("Failed to mount Google Drive. Exiting...")
        return
    
    # Try to load existing model
    if not analyzer.load_model():
        print("Training new model...")
        accuracy = analyzer.train_tamper_detection_model()
        if accuracy > 0.8:  # Only save if accuracy is good
            analyzer.save_model()
        else:
            print("Model accuracy too low. Consider improving training data.")
    
    print("\\nModel ready for inference!")
    print("To use this model with your Flask backend:")
    print("1. Update the model path in your Flask app")
    print("2. Use analyzer.predict_tampering(features) for predictions")
    print("3. The model files are saved in Google Drive for persistence")

# Run this in Colab
if __name__ == "__main__":
    main()