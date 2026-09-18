from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from pymongo import MongoClient
from web3 import Web3
from werkzeug.utils import secure_filename
import os
import hashlib
import librosa
import numpy as np
from pydub import AudioSegment
from scipy.spatial.distance import cosine
from sklearn.preprocessing import StandardScaler
import json
import uuid
from tensorflow.keras.models import load_model
import joblib
from bson import ObjectId
from datetime import datetime
import bcrypt
import jwt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
import io
import requests

app = Flask(__name__)
CORS(app)

# Configuration
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB

# Database connection
client = MongoClient('mongodb://localhost:27017/')
db = client.audio_evidence_db

# Blockchain connection (Ganache)
w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:7545'))

# Smart Contract ABI and Address (will be deployed)
CONTRACT_ABI = [
    {
        "inputs": [
            {"internalType": "string", "name": "_caseId", "type": "string"},
            {"internalType": "string", "name": "_audioHash", "type": "string"},
            {"internalType": "string", "name": "_metadata", "type": "string"}
        ],
        "name": "storeAudioEvidence",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "string", "name": "_caseId", "type": "string"},
            {"internalType": "string", "name": "_results", "type": "string"}
        ],
        "name": "storeAnalysisResults",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "string", "name": "", "type": "string"}],
        "name": "evidenceRecords",
        "outputs": [
            {"internalType": "string", "name": "caseId", "type": "string"},
            {"internalType": "string", "name": "audioHash", "type": "string"},
            {"internalType": "string", "name": "metadata", "type": "string"},
            {"internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

# Contract address (update after deployment)
CONTRACT_ADDRESS = "0x5FbDB2315678afecb367f032d93F642f64180aa3"  # Placeholder
contract = None

def init_contract():
    global contract
    if w3.is_connected():
        contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)

# Audio Processing Functions
class AudioProcessor:
    @staticmethod
    def preprocess_audio(file_path):
        """Preprocess audio: normalize, trim silence, remove noise"""
        try:
            # Load audio with librosa
            y, sr = librosa.load(file_path, sr=22050)
            
            # Trim silence
            y_trimmed, _ = librosa.effects.trim(y, top_db=20)
            
            # Normalize
            y_normalized = librosa.util.normalize(y_trimmed)
            
            # Simple noise reduction (spectral subtraction)
            S = librosa.stft(y_normalized)
            magnitude = np.abs(S)
            phase = np.angle(S)
            
            # Basic noise reduction
            noise_profile = np.mean(magnitude[:, :10], axis=1, keepdims=True)
            magnitude_clean = magnitude - 0.5 * noise_profile
            magnitude_clean = np.maximum(magnitude_clean, 0.1 * magnitude)
            
            S_clean = magnitude_clean * np.exp(1j * phase)
            y_clean = librosa.istft(S_clean)
            
            return y_clean, sr
        except Exception as e:
            print(f"Audio preprocessing error: {e}")
            return None, None

    @staticmethod
    def compute_audio_hash(audio_data):
        """Compute SHA-256 hash of preprocessed audio"""
        audio_bytes = audio_data.tobytes()
        return hashlib.sha256(audio_bytes).hexdigest()

    @staticmethod
    def extract_audio_features(audio_data, sr):
        """Extract features for tamper detection"""
        try:
            # MFCC features
            mfccs = librosa.feature.mfcc(y=audio_data, sr=sr, n_mfcc=13)
            
            # Spectral features
            spectral_centroids = librosa.feature.spectral_centroid(y=audio_data, sr=sr)
            spectral_rolloff = librosa.feature.spectral_rolloff(y=audio_data, sr=sr)
            zero_crossing_rate = librosa.feature.zero_crossing_rate(audio_data)
            
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
            print(f"Feature extraction error: {e}")
            return None

# class TamperDetector:
#     def __init__(self):
#         self.model_loaded = False
#         self.model = None
#         self.scaler = None
    
#     def load_model_from_gdrive(self, model_path="placeholder_model_path"):
#         """Load pre-trained tamper detection model from Google Drive"""
#         try:
#             # Placeholder for model loading
#             # In real implementation, download from Google Drive
#             print(f"Loading model from: {model_path}")
            
#             # Simulate model loading
#             from sklearn.ensemble import RandomForestClassifier
#             self.model = RandomForestClassifier(n_estimators=100, random_state=42)
#             self.scaler = StandardScaler()
            
#             # Generate dummy training data for demonstration
#             X_dummy = np.random.rand(1000, 28)  # 28 features
#             y_dummy = np.random.randint(0, 2, 1000)  # Binary: 0=authentic, 1=tampered
            
#             X_scaled = self.scaler.fit_transform(X_dummy)
#             self.model.fit(X_scaled, y_dummy)
            
#             self.model_loaded = True
#             print("Model loaded successfully!")
#             return True
#         except Exception as e:
#             print(f"Model loading error: {e}")
#             return False
    
#     def detect_tampering(self, features):
#         """Detect tampering in audio using pre-trained model"""
#         if not self.model_loaded:
#             if not self.load_model_from_gdrive():
#                 return {"result": "Error", "confidence": 0.0, "message": "Model not loaded"}
        
#         try:
#             features_scaled = self.scaler.transform(features.reshape(1, -1))
#             prediction = self.model.predict(features_scaled)[0]
#             confidence = self.model.predict_proba(features_scaled)[0].max()
            
#             result = "Tampered" if prediction == 1 else "Authentic"
            
#             return {
#                 "result": result,
#                 "confidence": float(confidence),
#                 "message": f"Audio classified as {result} with {confidence:.2%} confidence"
#             }
#         except Exception as e:
#             return {"result": "Error", "confidence": 0.0, "message": f"Detection error: {e}"}
from tensorflow.keras.models import load_model
import joblib

from tensorflow.keras.models import load_model
import joblib

class TamperDetector:
    def __init__(self):
        self.model_loaded = False
        self.model = None
        self.scaler = None
    
    def load_model_from_local(self):
        try:
            print("🔍 Trying to load tamper detection model...")
            self.model = load_model("models/colab_forensic_model.h5")
            print("✅ Model loaded successfully")
            
            self.scaler = joblib.load("models/colab_forensic_scaler.pkl")
            print("✅ Scaler loaded successfully")
            
            self.model_loaded = True
            return True
        except Exception as e:
            print(f"❌ Model loading error: {e}")
            return False
    
    # def detect_tampering(self, features):
    #     if not self.model_loaded:
    #         if not self.load_model_from_local():
    #             return {"result": "Error", "confidence": 0.0, "message": "Model not loaded"}
        
    #     try:
    #         features_scaled = self.scaler.transform(features.reshape(1, -1))
    #         prediction = self.model.predict(features_scaled)[0]
            
    #         # If model outputs probability
    #         if prediction.shape:  # e.g., [[0.1, 0.9]]
    #             prediction_label = np.argmax(prediction)
    #             confidence = float(np.max(prediction))
    #         else:  # direct label
    #             prediction_label = int(prediction)
    #             confidence = 1.0
            
    #         result = "Tampered" if prediction_label == 1 else "Authentic"
    #         return {
    #             "result": result,
    #             "confidence": confidence,
    #             "message": f"Audio classified as {result} with {confidence:.2%} confidence"
    #         }
    #     except Exception as e:
    #         return {"result": "Error", "confidence": 0.0, "message": f"Detection error: {e}"}


    # def detect_tampering(self, features):
    #     if not self.model_loaded:
    #         if not self.load_model_from_local():
    #             return {
    #                 "result": "Error",
    #                 "confidence": 0.0,
    #                 "message": "Model not loaded"
    #             }
    #     try:
    #     if features is None:
    #         print("❌ Features are None")
    #         return {"result": "Error", "confidence": 0.0, "message": "No features extracted"}

    #     print(f"🔎 Feature shape before scaling: {features.shape}")
    #     features_scaled = self.scaler.transform(features.reshape(1, -1))
    #     print(f"✅ Feature shape after scaling: {features_scaled.shape}")

    #     prediction = self.model.predict(features_scaled, verbose=0)[0][0]
    #     print(f"✅ Prediction raw: {prediction}")


    

    #     try:
    #         features_scaled = self.scaler.transform(features.reshape(1, -1))
    #         prediction = self.model.predict(features_scaled, verbose=0)[0][0]  # sigmoid output

    #         if prediction > 0.5:
    #             result = "Authentic"
    #             confidence = float(prediction)
    #         else:
    #             result = "Tampered"
    #             confidence = float(1 - prediction)

    #         return {
    #             "result": result,
    #             "confidence": confidence,
    #             "message": f"Audio classified as {result} with {confidence:.2%} confidence"
    #         }
    #     except Exception as e:
    #         return {
    #             "result": "Error",
    #             "confidence": 0.0,
    #             "message": f"Detection error: {e}"
    #         }
    def detect_tampering(self, features):
        if not self.model_loaded:
            if not self.load_model_from_local():
                return {"result": "Error", "confidence": 0.0, "message": "Model not loaded"}

         try:
            if features is None:
                 print("❌ Features are None")
                return {"result": "Error", "confidence": 0.0, "message": "No features extracted"}

            print(f"🔎 Feature shape before scaling: {features.shape}")
            features_scaled = self.scaler.transform(features.reshape(1, -1))
            print(f"✅ Feature shape after scaling: {features_scaled.shape}")

            prediction = self.model.predict(features_scaled, verbose=0)[0][0]
            print(f"✅ Prediction raw: {prediction}")





class SpeakerVerifier:
    @staticmethod
    def extract_voice_features(audio_data, sr):
        """Extract voice features for speaker verification"""
        try:
            # Pitch (F0)
            pitches, magnitudes = librosa.piptrack(y=audio_data, sr=sr)
            pitch_values = []
            for t in range(pitches.shape[1]):
                index = magnitudes[:, t].argmax()
                pitch = pitches[index, t]
                if pitch > 0:
                    pitch_values.append(pitch)
            
            pitch_mean = np.mean(pitch_values) if pitch_values else 0
            pitch_std = np.std(pitch_values) if pitch_values else 0
            
            # Formants (approximated using spectral peaks)
            spectrum = np.abs(np.fft.fft(audio_data))
            freqs = np.fft.fftfreq(len(spectrum), 1/sr)
            positive_freqs = freqs[:len(freqs)//2]
            positive_spectrum = spectrum[:len(spectrum)//2]
            
            # Find formant peaks
            from scipy.signal import find_peaks
            peaks, _ = find_peaks(positive_spectrum, height=np.max(positive_spectrum)*0.1)
            formants = positive_freqs[peaks][:4]  # First 4 formants
            
            # MFCC for spectral characteristics
            mfcc = librosa.feature.mfcc(y=audio_data, sr=sr, n_mfcc=13)
            mfcc_mean = np.mean(mfcc, axis=1)
            
            return {
                'pitch_mean': pitch_mean,
                'pitch_std': pitch_std,
                'formants': formants,
                'mfcc': mfcc_mean
            }
        except Exception as e:
            print(f"Voice feature extraction error: {e}")
            return None
    
    @staticmethod
    def verify_speaker(features1, features2):
        """Verify if two audio samples are from the same speaker"""
        try:
            # Cosine similarity for MFCC
            cosine_sim = 1 - cosine(features1['mfcc'], features2['mfcc'])
            
            # Pitch similarity
            pitch_diff = abs(features1['pitch_mean'] - features2['pitch_mean'])
            pitch_sim = max(0, 1 - pitch_diff / max(features1['pitch_mean'], features2['pitch_mean'], 1))
            
            # Formant similarity
            formant_sim = 0
            if len(features1['formants']) > 0 and len(features2['formants']) > 0:
                min_formants = min(len(features1['formants']), len(features2['formants']))
                formant_diffs = []
                for i in range(min_formants):
                    diff = abs(features1['formants'][i] - features2['formants'][i])
                    formant_diffs.append(diff)
                avg_formant_diff = np.mean(formant_diffs)
                formant_sim = max(0, 1 - avg_formant_diff / 1000)  # Normalize by 1000 Hz
            
            # Spectral similarity (using MFCC)
            spectral_sim = cosine_sim  # Same as cosine similarity for MFCC
            
            # Overall similarity
            overall_sim = (cosine_sim + pitch_sim + formant_sim + spectral_sim) / 4
            
            # Decision threshold
            match = "Match" if overall_sim > 0.7 else "Mismatch"
            
            return {
                'cosine_similarity': float(cosine_sim),
                'pitch_similarity': float(pitch_sim),
                'formant_similarity': float(formant_sim),
                'spectral_similarity': float(spectral_sim),
                'overall_confidence': float(overall_sim),
                'result': match
            }
        except Exception as e:
            print(f"Speaker verification error: {e}")
            return None

# Initialize processors
audio_processor = AudioProcessor()
tamper_detector = TamperDetector()
speaker_verifier = SpeakerVerifier()

# Utility Functions
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed)

def generate_token(user_id):
    payload = {
        'user_id': str(user_id),
        'exp': datetime.utcnow().timestamp() + 86400  # 24 hours
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

def verify_token(token):
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload['user_id']
    except:
        return None

# Database Models
def init_db():
    """Initialize database with default admin user"""
    if db.users.find_one({'username': 'admin'}) is None:
        admin_user = {
            'username': 'admin',
            'password': hash_password('admin123'),
            'role': 'admin',
            'full_name': 'System Administrator',
            'created_at': datetime.utcnow()
        }
        db.users.insert_one(admin_user)
        print("Default admin user created (admin/admin123)")

# API Routes
@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    user = db.users.find_one({'username': username})
    if user and check_password(password, user['password']):
        token = generate_token(user['_id'])
        return jsonify({
            'success': True,
            'token': token,
            'user': {
                'id': str(user['_id']),
                'username': user['username'],
                'role': user['role'],
                'full_name': user['full_name']
            }
        })
    
    return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

# @app.route('/api/auth/create-user', methods=['POST'])
# def create_user():
#     data = request.get_json()
    
#     # Verify admin token
#     token = request.headers.get('Authorization', '').replace('Bearer ', '')
#     user_id = verify_token(token)
#     if not user_id:
#         return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
#     current_user = db.users.find_one({'_id': user_id})
#     if not current_user or current_user['role'] != 'admin':
#         return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
#     # Check if username exists
#     if db.users.find_one({'username': data['username']}):
#         return jsonify({'success': False, 'message': 'Username already exists'}), 400
    
#     # Create new user
#     new_user = {
#         'username': data['username'],
#         'password': hash_password(data['password']),
#         'role': 'user',
#         'full_name': data['full_name'],
#         'badge_number': data.get('badge_number', ''),
#         'department': data.get('department', ''),
#         'created_at': datetime.utcnow()
#     }
    
#     result = db.users.insert_one(new_user)
#     return jsonify({'success': True, 'user_id': str(result.inserted_id)})
@app.route('/api/auth/create-user', methods=['POST'])
def create_user():
    try:
        data = request.get_json()
        
        # Debug logging
        print(f"Received create user request: {data}")
        
        # Verify admin token
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.replace('Bearer ', '')
        user_id = verify_token(token)
        
        if not user_id:
            print("Token verification failed")
            return jsonify({'success': False, 'message': 'Unauthorized - Invalid token'}), 401
        
        # FIX: Convert user_id string to ObjectId for MongoDB query
        try:
            from bson import ObjectId
            current_user = db.users.find_one({'_id': ObjectId(user_id)})
            print(f"Current user found: {current_user['username'] if current_user else 'None'}")
        except Exception as e:
            print(f"Error finding user: {e}")
            return jsonify({'success': False, 'message': 'Invalid user ID format'}), 401
        
        if not current_user:
            print("User not found in database")
            return jsonify({'success': False, 'message': 'User not found'}), 404
            
        if current_user['role'] != 'admin':
            print(f"Access denied - user role is {current_user['role']}, need admin")
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        
        # Validate required fields
        required_fields = ['username', 'password', 'full_name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field} is required'}), 400
        
        # Check if username exists
        if db.users.find_one({'username': data['username']}):
            return jsonify({'success': False, 'message': 'Username already exists'}), 400
        
        # Create new user
        new_user = {
            'username': data['username'],
            'password': hash_password(data['password']),
            'role': data.get('role', 'user'),  # Allow role specification, default to 'user'
            'full_name': data['full_name'],
            'badge_number': data.get('badge_number', ''),
            'department': data.get('department', ''),
            'created_at': datetime.utcnow()
        }
        
        result = db.users.insert_one(new_user)
        print(f"User created successfully with ID: {result.inserted_id}")
        return jsonify({'success': True, 'user_id': str(result.inserted_id)})
        
    except Exception as e:
        print(f"Unexpected error in create_user: {e}")
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

# @app.route('/api/cases', methods=['GET'])
# def get_cases():
#     token = request.headers.get('Authorization', '').replace('Bearer ', '')
#     user_id = verify_token(token)
#     if not user_id:
#         return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
#     current_user = db.users.find_one({'_id': user_id})
    
#     # Admin can see all cases, users only their own
#     current_user = db.users.find_one({'_id': ObjectId(user_id)})
#     if not current_user:
#         return jsonify({'success': False, 'message': 'User not found'}), 404

#     else:
#         cases = list(db.cases.find({'officer_id': str(user_id)}).sort('created_at', -1))
    
#     # Convert ObjectId to string
#     for case in cases:
#         case['_id'] = str(case['_id'])
    
#     return jsonify({'success': True, 'cases': cases})
# @app.route('/api/cases', methods=['GET'])
# def get_cases():
#     token = request.headers.get('Authorization', '').replace('Bearer ', '')
#     user_id = verify_token(token)
#     if not user_id:
#         return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
#     try:
#         current_user = db.users.find_one({'_id': ObjectId(user_id)})
#         if not current_user:
#             return jsonify({'success': False, 'message': 'User not found'}), 404
#     except:
#         return jsonify({'success': False, 'message': 'Invalid user ID'}), 401

#     # Admin can see all cases, users only their own
#     if current_user['role'] == 'admin':
#         cases = list(db.cases.find().sort('created_at', -1))
#     else:
#         cases = list(db.cases.find({'officer_id': str(user_id)}).sort('created_at', -1))
    
#     # Convert ObjectId to string
#     for case in cases:
#         case['_id'] = str(case['_id'])
    
#     return jsonify({'success': True, 'cases': cases})
@app.route('/api/cases', methods=['GET'])
def get_cases():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    if not user_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        from bson import ObjectId
        current_user = db.users.find_one({'_id': ObjectId(user_id)})
        if not current_user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
    except:
        return jsonify({'success': False, 'message': 'Invalid user ID'}), 401

    # Admin can see all cases, users only their own
    if current_user['role'] == 'admin':
        cases = list(db.cases.find().sort('created_at', -1))
    else:
        cases = list(db.cases.find({'officer_id': str(user_id)}).sort('created_at', -1))
    
    # Convert ObjectId to string
    for case in cases:
        case['_id'] = str(case['_id'])
    
    return jsonify({'success': True, 'cases': cases})

@app.route('/api/upload-audio', methods=['POST'])
def upload_audio():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    if not user_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    # current_user = db.users.find_one({'_id': user_id})
    current_user=db.users.find_one({'_id': ObjectId(user_id)})

    
    # Get files and metadata
    audio_file = request.files.get('audio_file')
    reference_file = request.files.get('reference_file')  # Optional
    
    case_number = request.form.get('case_number')
    device = request.form.get('device')
    location = request.form.get('location')
    
    if not audio_file:
        return jsonify({'success': False, 'message': 'No audio file provided'}), 400
    
    try:
        # Create case directory
        case_dir = os.path.join(app.config['UPLOAD_FOLDER'], case_number)
        os.makedirs(case_dir, exist_ok=True)
        
        # Generate file number
        file_number = f"AE{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Save primary audio file
        primary_filename = secure_filename(f"{file_number}_{audio_file.filename}")
        primary_path = os.path.join(case_dir, primary_filename)
        audio_file.save(primary_path)
        
        # === START INTEGRATED WORKFLOW ===
        
        # Step 1: Preprocess audio
        processed_audio, sample_rate = audio_processor.preprocess_audio(primary_path)
        if processed_audio is None:
            return jsonify({'success': False, 'message': 'Audio preprocessing failed'}), 500
        
        # Step 2: Compute hash
        audio_hash = audio_processor.compute_audio_hash(processed_audio)
        
        # Step 3: Store in blockchain (Step 1)
        metadata = {
            'case_number': case_number,
            'file_number': file_number,
            'officer': current_user['full_name'],
            'device': device,
            'location': location,
            'timestamp': datetime.utcnow().isoformat(),
            'filename': primary_filename
        }
        
        # Blockchain storage (simulated)
        blockchain_entry_1 = {
            'case_id': case_number,
            'audio_hash': audio_hash,
            'metadata': json.dumps(metadata),
            'timestamp': datetime.utcnow(),
            'block_type': 'evidence_storage'
        }
        
        # Step 4: Audio storage (local for this demo, could be IPFS/Google Drive)
        storage_path = primary_path
        
        # Step 5: Tamper detection
        features = audio_processor.extract_audio_features(processed_audio, sample_rate)
        tamper_result = tamper_detector.detect_tampering(features)
        
        # Step 6: Speaker verification (if reference provided)
        speaker_result = None
        if reference_file:
            ref_filename = secure_filename(f"{file_number}_ref_{reference_file.filename}")
            ref_path = os.path.join(case_dir, ref_filename)
            reference_file.save(ref_path)
            
            ref_audio, ref_sr = audio_processor.preprocess_audio(ref_path)
            if ref_audio is not None:
                primary_features = speaker_verifier.extract_voice_features(processed_audio, sample_rate)
                ref_features = speaker_verifier.extract_voice_features(ref_audio, ref_sr)
                
                if primary_features and ref_features:
                    speaker_result = speaker_verifier.verify_speaker(primary_features, ref_features)
        
        # Step 7: Store analysis results in blockchain (Step 2)
        analysis_results = {
            'tamper_detection': tamper_result,
            'speaker_verification': speaker_result,
            'analysis_timestamp': datetime.utcnow().isoformat()
        }
        
        blockchain_entry_2 = {
            'case_id': case_number,
            'results': json.dumps(analysis_results),
            'timestamp': datetime.utcnow(),
            'block_type': 'analysis_results'
        }
        
        # Step 8: Store case in database
        case_data = {
            'case_number': case_number,
            'file_number': file_number,
            'officer_id': str(user_id),
            'officer_name': current_user['full_name'],
            'device': device,
            'location': location,
            'audio_hash': audio_hash,
            'storage_path': storage_path,
            'tamper_result': tamper_result,
            'speaker_result': speaker_result,
            'blockchain_entries': [blockchain_entry_1, blockchain_entry_2],
            'created_at': datetime.utcnow(),
            'status': 'completed'
        }
        
        result = db.cases.insert_one(case_data)
        case_id = str(result.inserted_id)
        
        # === END INTEGRATED WORKFLOW ===
        
        return jsonify({
            'success': True,
            'case_id': case_id,
            'file_number': file_number,
            'tamper_result': tamper_result,
            'speaker_result': speaker_result,
            'message': 'Audio processed successfully through complete workflow'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Processing error: {str(e)}'}), 500

@app.route('/api/generate-report/<case_id>', methods=['GET'])
def generate_report(case_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    if not user_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        # Get case data
        # case = db.cases.find_one({'_id': case_id})
        case = db.cases.find_one({'_id': ObjectId(case_id)})
        if not case:
            return jsonify({'success': False, 'message': 'Case not found'}), 404
        
        # Generate PDF report
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title = Paragraph("Audio Evidence Verification Report", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 12))
        
        # Case Information
        case_info = [
            ['Case ID:', case['case_number']],
            ['File ID:', case['file_number']],
            ['Officer Name:', case['officer_name']],
            ['Date/Time:', case['created_at'].strftime('%Y-%m-%d %H:%M:%S')],
        ]
        
        case_table = Table(case_info)
        case_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
        
        story.append(case_table)
        story.append(Spacer(1, 12))
        
        # Audio Details
        audio_details = Paragraph("Audio Details", styles['Heading2'])
        story.append(audio_details)
        
        audio_info = [
            ['Device:', case['device']],
            ['Location:', case['location']],
            # ['File Hash:', case['audio_hash'][:32] + '...'],
        ]
        
        audio_table = Table(audio_info)
        audio_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        
        story.append(audio_table)
        story.append(Spacer(1, 12))
        
        # Analysis Results
        analysis_header = Paragraph("Audio Analysis", styles['Heading2'])
        story.append(analysis_header)
        
        tamper_result = case['tamper_result']
        analysis_info = [
            ['Result:', tamper_result['result']],
            ['Confidence:', f"{tamper_result['confidence']:.2%}"],
            ['Model Used:', 'RandomForest Tamper Detection Model'],
        ]
        
        analysis_table = Table(analysis_info)
        analysis_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        
        story.append(analysis_table)
        story.append(Spacer(1, 12))
        
        # Voice Verification
        if case['speaker_result']:
            voice_header = Paragraph("Voice Verification", styles['Heading2'])
            story.append(voice_header)
            
            speaker_result = case['speaker_result']
            voice_info = [
                ['Cosine Similarity:', f"{speaker_result['cosine_similarity']:.3f}"],
                ['Pitch Similarity:', f"{speaker_result['pitch_similarity']:.3f}"],
                ['Formant Similarity:', f"{speaker_result['formant_similarity']:.3f}"],
                ['Spectral Similarity:', f"{speaker_result['spectral_similarity']:.3f}"],
                ['Overall Result:', speaker_result['result']],
                ['Confidence:', f"{speaker_result['overall_confidence']:.2%}"],
            ]
            
            voice_table = Table(voice_info)
            voice_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
            ]))
            
            story.append(voice_table)
            story.append(Spacer(1, 12))
        else:
            no_voice = Paragraph("Voice Verification: N/A (No reference audio provided)", styles['Normal'])
            story.append(no_voice)
            story.append(Spacer(1, 12))
        
        # Summary
        summary_header = Paragraph("Result Summary", styles['Heading2'])
        story.append(summary_header)
        
        # Generate police-style summary
        tamper_status = "authentic" if tamper_result['result'] == 'Authentic' else "potentially tampered"
        speaker_status = ""
        
        if case['speaker_result']:
            speaker_match = case['speaker_result']['result'].lower()
            speaker_status = f" Speaker verification indicates a {speaker_match} with the reference audio."
        
        summary_text = f"Based on technical analysis, the submitted audio evidence appears to be {tamper_status} " \
                      f"with {tamper_result['confidence']:.1%} confidence.{speaker_status} " \
                      f"This analysis was conducted using blockchain-verified audio evidence verification system " \
                      f"on {case['created_at'].strftime('%B %d, %Y at %H:%M UTC')}."
        
        summary = Paragraph(summary_text, styles['Normal'])
        story.append(summary)
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        
        return send_file(
            io.BytesIO(buffer.read()),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'Audio_Evidence_Report_{case["case_number"]}_{case["file_number"]}.pdf'
        )
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Report generation error: {str(e)}'}), 500

# Initialize application
if __name__ == '__main__':
    # Create upload directory
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Initialize database
    init_db()
    
    # Initialize blockchain connection
    init_contract()
    
    app.run(debug=True, host='0.0.0.0', port=5000)