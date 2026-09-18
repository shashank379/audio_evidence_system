import os
# ---- Windows fix: disable HuggingFace symlinks ----
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
import io
import json
import uuid
import bcrypt
import jwt
import pywt
import hashlib
import librosa
import numpy as np
import joblib
import tensorflow as tf
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from pymongo import MongoClient
from web3 import Web3
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from bson import ObjectId
from scipy import signal
from scipy.spatial.distance import cosine
from scipy.stats import entropy, kurtosis, skew
from tensorflow.keras.models import load_model
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.regularizers import l2
from tensorflow.keras.layers import Dense, Dropout, BatchNormalization, Input, LeakyReLU
from tensorflow.keras.models import Model
from flask import send_from_directory
import torch
import torchaudio
from speechbrain.inference.speaker import SpeakerRecognition


# Suppress NumPy and Librosa warnings for cleaner output
import warnings
import matplotlib
matplotlib.use('Agg')  # prevents Tkinter GUI calls
import matplotlib.pyplot as plt


def visualize_tampering(audio_path, edit_points, tamper_result):
    """
    Generates a PNG waveform visualization showing tampered regions
    and computes approximate percentage of tampering.
    """
    try:
        import os
        import librosa
        import numpy as np
        import matplotlib.pyplot as plt

        # Load the audio
        audio, sr = librosa.load(audio_path, sr=16000)
        duration_seconds = len(audio) / sr

        # Extract case folder and base filename
        case_number = os.path.basename(os.path.dirname(audio_path))
        file_base = os.path.splitext(os.path.basename(audio_path))[0]

        # Prepare uploads directory
        uploads_dir = os.path.join("uploads", case_number)
        os.makedirs(uploads_dir, exist_ok=True)
        visual_path = os.path.join(uploads_dir, f"{file_base}_tamper_visual.png")

        # --- Calculate tampering percentage ---
        if len(edit_points) > 0:
            # assume each tamper event spans ~0.1 sec
            estimated_tampered_duration = len(edit_points) * 0.1
            tamper_percentage = min((estimated_tampered_duration / duration_seconds) * 100, 100)
        else:
            tamper_percentage = 0.0

        # --- Start plotting ---
        plt.figure(figsize=(12, 4))
        time_axis = np.linspace(0, duration_seconds, len(audio))
        plt.plot(time_axis, audio, color='gray', alpha=0.6)
        plt.xlabel("Time (seconds)")
        plt.ylabel("Amplitude")

        if tamper_result["result"].lower() == "tampered":
            plt.title(
                f"Tamper Visualization: Tampered ({tamper_result['confidence']*100:.1f}% confidence, "
                f"{tamper_percentage:.1f}% region)",
                color='red'
            )
            # Highlight tampered timestamps
            for ep in edit_points:
                if ep["confidence"] < 0.7:
                    continue
                plt.axvline(ep['time'], color='red', linestyle='--', alpha=0.8, linewidth=1)

                # ### UPDATED: label with tamper type if available
                label = ep.get("tamper_type", f"{ep['confidence']:.2f}")
                plt.text(
                    ep['time'],
                    0.8 * np.max(audio),
                    label,
                    color='red',
                    fontsize=8,
                    rotation=90,
                    ha='center',
                    va='bottom'
                )
        else:
            plt.title(
                f"Tamper Visualization: Authentic ({tamper_result['confidence']*100:.1f}% confidence, "
                f"0.0% region)",
                color='green'
            )

        # Add legend and save
        plt.tight_layout()
        plt.savefig(visual_path)
        plt.close()

        print(f"✅ Visualization saved: {visual_path}")
        print(f"📊 Tampering estimated: {tamper_percentage:.2f}% of audio duration")

        # Return both path and percentage
        return visual_path, tamper_percentage

    except Exception as e:
        print(f"Visualization error: {e}")
        return None, 0.0


warnings.filterwarnings('ignore')

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Configuration
app.config['SECRET_KEY'] = ''
# app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')
app.config['UPLOAD_FOLDER'] = 'uploads'  # Use relative path
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB

# # Database connection
client = MongoClient('mongodb://localhost:27017/')
db = client.audio_evidence_db
MONGO_URI = os.getenv("MONGODB_URI", "mongodb://admin:password123@mongodb:27017/audio_evidence_db?authSource=admin")
# client = MongoClient('mongodb://localhost:27017/')
# db = client.audio_evidence_db

# client = MongoClient(MONGO_URI)
# db = client["audio_evidence_db"]


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
CONTRACT_ADDRESS = "0x5FbDB2315678afecb367f032d93F642f64180aa3"
contract = None


def init_contract():
    global contract
    if w3.is_connected():
        contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)


# --- NEW: Helper to generate human-readable description for tamper type ---
def build_tamper_explanation(tamper_type, time_sec, confidence):
    """
    Returns a short natural language explanation for a detected tampered point.
    """
    base_intro = (
        f"Tampered segment detected at {time_sec:.2f} seconds "
        f"with approximately {confidence*100:.1f}% confidence. "
    )

    tamper_type_upper = (tamper_type or "UNKNOWN ARTIFACT").upper()

    if tamper_type_upper == "CUT / SPLICE":
        detail = (
            "The system detected a sudden discontinuity in energy and spectrum, "
            "which suggests that a portion of the audio may have been cut, removed, "
            "or inserted from another recording."
        )
    elif tamper_type_upper == "NOISE FILTERING / SMOOTHING":
        detail = (
            "Noise floor and spectral shape changed abruptly, indicating possible "
            "post-processing such as denoising, smoothing, or aggressive filtering "
            "around this region."
        )
    elif tamper_type_upper == "PITCH / SPEED CHANGE":
        detail = (
            "Pitch and timing patterns show an unnatural shift, which is often caused "
            "by time-stretching, speed alteration, or pitch-shifting operations."
        )
    elif tamper_type_upper == "VOICE CONVERSION / DEEPFAKE ARTIFACT":
        detail = (
            "Vocal-tract and prosodic patterns differ from surrounding speech, "
            "suggesting possible voice conversion or synthetic (deepfake-style) "
            "manipulation at this point."
        )
    else:
        detail = (
            "Anomalous behavior was detected in the signal that does not clearly "
            "match common editing patterns, but still appears suspicious and should "
            "be manually reviewed."
        )

    recommendation = (
        "Recommendation: review this region carefully in the original context, "
        "and correlate with transcripts, witness statements, or other evidence."
    )

    return base_intro + detail + " " + recommendation


# --- NEW FEATURE EXTRACTION CLASSES AND FUNCTIONS (from training script) ---
class CutSpliceDetector:
    def __init__(self, window_size=2048, hop_length=512):
        self.window_size = window_size
        self.hop_length = hop_length

    def detect_cuts_and_splices(self, audio, sr=16000):
        features = {}
        try:
            frame_energy = librosa.feature.rms(
                y=audio,
                frame_length=self.window_size,
                hop_length=self.hop_length
            )[0]
            energy_diff = np.abs(np.diff(frame_energy))
            energy_threshold = np.mean(energy_diff) + 2 * np.std(energy_diff)
            energy_outliers = np.sum(energy_diff > energy_threshold)
            features['energy_discontinuities'] = energy_outliers / len(energy_diff)

            stft = librosa.stft(audio, hop_length=self.hop_length)
            magnitude = np.abs(stft)

            spectral_centroids = librosa.feature.spectral_centroid(S=magnitude, sr=sr)[0]
            centroid_diff = np.abs(np.diff(spectral_centroids))
            centroid_threshold = np.mean(centroid_diff) + 2 * np.std(centroid_diff)
            centroid_jumps = np.sum(centroid_diff > centroid_threshold)
            features['spectral_jumps'] = centroid_jumps / len(centroid_diff)

            phase = np.angle(stft)
            phase_diff = np.diff(np.unwrap(phase, axis=1), axis=1)
            phase_discontinuities = np.sum(np.abs(phase_diff) > np.pi / 2, axis=0)
            features['phase_discontinuities'] = np.mean(phase_discontinuities) / magnitude.shape[0]

            if len(audio) > sr:
                autocorr = np.correlate(audio, audio, mode='full')
                autocorr = autocorr[autocorr.size // 2:][:sr]
                autocorr_normalized = autocorr / (autocorr[0] + 1e-10)
                peaks, _ = signal.find_peaks(
                    autocorr_normalized,
                    height=0.1,
                    distance=sr // 100
                )
                periodicity_strength = (
                    np.mean(autocorr_normalized[peaks]) if len(peaks) > 0 else 0
                )
                features['periodicity_disruption'] = 1 - periodicity_strength
            else:
                features['periodicity_disruption'] = 0.5

            try:
                harmonic, percussive = librosa.effects.hpss(audio)
                harmonic_frames = librosa.util.frame(
                    harmonic,
                    frame_length=self.window_size,
                    hop_length=self.hop_length
                )
                harmonic_consistency = []
                for i in range(1, min(harmonic_frames.shape[1], 100)):
                    correlation = np.corrcoef(
                        harmonic_frames[:, i - 1],
                        harmonic_frames[:, i]
                    )[0, 1]
                    harmonic_consistency.append(
                        correlation if not np.isnan(correlation) else 0
                    )
                features['harmonic_inconsistency'] = (
                    1 - np.mean(harmonic_consistency)
                    if harmonic_consistency else 0.5
                )
            except Exception:
                features['harmonic_inconsistency'] = 0.5

            edit_points = self._localize_edit_points(audio, sr)
            features['detected_edit_points'] = len(edit_points)
            features['edit_point_confidence'] = (
                np.mean([ep['confidence'] for ep in edit_points]) if edit_points else 0
            )

        except Exception as e:
            print(f"Cut/splice detection error: {e}")
            features = {
                'energy_discontinuities': 0,
                'spectral_jumps': 0,
                'phase_discontinuities': 0,
                'periodicity_disruption': 0.5,
                'harmonic_inconsistency': 0.5,
                'detected_edit_points': 0,
                'edit_point_confidence': 0
            }
            edit_points = []
        return features, edit_points

    # ### NEW: classify type of tampering at each suspected edit point
    def _classify_edit_type(self, energy_ratio, spectral_distance, temporal_correlation):
        """
        Heuristic classification of tamper type based on local measurements.
        This is NOT a perfect forensic label, but gives a meaningful hint.
        """
        # Work with absolute log energy ratio
        energy_change = abs(np.log(energy_ratio + 1e-10))
        spec = spectral_distance
        corr = temporal_correlation

        # Thresholds can be tuned based on your data
        if energy_change > 1.5 and spec > 0.6:
            return "CUT / SPLICE"
        elif spec < 0.15 and corr < 0.4:
            return "NOISE FILTERING / SMOOTHING"
        elif spec > 0.3 and abs(corr) > 0.8:
            return "PITCH / SPEED CHANGE"
        elif spec > 0.4 and energy_ratio < 0.6:
            return "VOICE CONVERSION / DEEPFAKE ARTIFACT"
        else:
            return "UNKNOWN ARTIFACT"

    def _localize_edit_points(self, audio, sr, threshold=0.6):
        edit_points = []
        try:
            window_size = sr // 4
            hop_size = sr // 10
            if len(audio) < window_size * 2:
                return edit_points

            for start in range(0, len(audio) - window_size - hop_size, hop_size):
                window1 = audio[start:start + window_size]
                window2 = audio[start + hop_size:start + hop_size + window_size]
                if len(window1) != len(window2):
                    continue

                energy_ratio = np.mean(window2 ** 2) / (np.mean(window1 ** 2) + 1e-10)
                spectral_distance = self._spectral_distance(window1, window2, sr)
                temporal_correlation = np.corrcoef(window1, window2)[0, 1]
                if np.isnan(temporal_correlation):
                    temporal_correlation = 0

                edit_confidence = (
                    min(abs(np.log(energy_ratio)), 2) * 0.3 +
                    min(spectral_distance, 1) * 0.4 +
                    (1 - abs(temporal_correlation)) * 0.3
                )

                if edit_confidence > threshold:
                    tamper_type = self._classify_edit_type(
                        energy_ratio, spectral_distance, temporal_correlation
                    )
                    edit_points.append({
                        'time': start / sr,
                        'confidence': edit_confidence,
                        'energy_ratio': energy_ratio,
                        'spectral_distance': spectral_distance,
                        'temporal_correlation': temporal_correlation,
                        'tamper_type': tamper_type  # ### NEW
                    })
        except Exception as e:
            print(f"Edit point localization error: {e}")
        return edit_points

    def _spectral_distance(self, audio1, audio2, sr):
        try:
            stft1 = librosa.stft(audio1, n_fft=1024)
            stft2 = librosa.stft(audio2, n_fft=1024)
            mag1 = np.mean(np.abs(stft1), axis=1)
            mag2 = np.mean(np.abs(stft2), axis=1)
            mag1 = mag1 / (np.sum(mag1) + 1e-10)
            mag2 = mag2 / (np.sum(mag2) + 1e-10)
            return cosine(mag1, mag2)
        except Exception:
            return 0.5


class VoiceMimicDetector:
    def __init__(self):
        pass

    def detect_voice_mimicry(self, audio, sr=16000, reference_audio=None):
        features = {}
        try:
            prosodic_features = self._analyze_prosody(audio, sr)
            features.update(prosodic_features)
            vc_artifacts = self._detect_voice_conversion_artifacts(audio, sr)
            features.update(vc_artifacts)
            vocal_features = self._analyze_vocal_tract_consistency(audio, sr)
            features.update(vocal_features)
            breathing_features = self._analyze_breathing_patterns(audio, sr)
            features.update(breathing_features)
        except Exception as e:
            print(f"Voice mimicry detection error: {e}")
            features = {
                'f0_mean': 0, 'f0_std': 0, 'f0_range': 0, 'f0_jitter': 0,
                'f0_smoothness': 0.5, 'f0_unnatural_jumps': 0, 'speech_rate': 0,
                'speech_rate_variance': 0, 'formant_f1_mean': 0, 'formant_f2_mean': 0,
                'formant_stability': 0.5, 'spectral_consistency': 0.5,
                'high_freq_artifact_ratio': 0, 'periodic_artifact_strength': 0,
                'vocal_tract_stability': 0.5, 'lpc_residual_error': 0,
                'lpc_coefficient_variance': 0, 'breath_regularity': 0.5,
                'breath_duration_consistency': 0.5, 'breath_frequency': 0
            }
        return features

    def _analyze_prosody(self, audio, sr):
        features = {}
        try:
            f0 = librosa.yin(audio, fmin=50, fmax=400, sr=sr)
            voiced_frames = f0 > 0
            if np.sum(voiced_frames) > 10:
                f0_voiced = f0[voiced_frames]
                features['f0_mean'] = np.mean(f0_voiced)
                features['f0_std'] = np.std(f0_voiced)
                features['f0_range'] = np.ptp(f0_voiced)
                if len(f0_voiced) > 1:
                    f0_diff = np.abs(np.diff(f0_voiced))
                    features['f0_jitter'] = np.mean(f0_diff) / np.mean(f0_voiced)
                else:
                    features['f0_jitter'] = 0
                if len(f0_voiced) >= 5:
                    f0_smooth = signal.savgol_filter(f0_voiced, 5, 2)
                    features['f0_smoothness'] = np.corrcoef(f0_voiced, f0_smooth)[0, 1]
                    if np.isnan(features['f0_smoothness']):
                        features['f0_smoothness'] = 0.5
                else:
                    features['f0_smoothness'] = 0.5
                f0_diff = np.abs(np.diff(f0_voiced))
                jump_threshold = np.mean(f0_diff) + 2 * np.std(f0_diff)
                features['f0_unnatural_jumps'] = np.sum(
                    f0_diff > jump_threshold) / len(f0_diff)
            else:
                features.update({
                    'f0_mean': 0, 'f0_std': 0, 'f0_range': 0, 'f0_jitter': 0,
                    'f0_smoothness': 0.5, 'f0_unnatural_jumps': 0
                })
            onset_frames = librosa.onset.onset_detect(
                y=audio, sr=sr, units='frames')
            speech_rate = len(onset_frames) / (len(audio) / sr)
            features['speech_rate'] = speech_rate
            if len(onset_frames) > 2:
                onset_times = librosa.frames_to_time(onset_frames, sr=sr)
                intervals = np.diff(onset_times)
                features['speech_rate_variance'] = np.std(
                    intervals) / (np.mean(intervals) + 1e-10)
            else:
                features['speech_rate_variance'] = 0
        except Exception as e:
            print(f"Prosody analysis error: {e}")
            features.update({
                'f0_mean': 0, 'f0_std': 0, 'f0_range': 0, 'f0_jitter': 0,
                'f0_smoothness': 0.5, 'f0_unnatural_jumps': 0, 'speech_rate': 0,
                'speech_rate_variance': 0
            })
        return features

    def _detect_voice_conversion_artifacts(self, audio, sr):
        features = {}
        try:
            stft = librosa.stft(audio)
            magnitude = np.abs(stft)
            freqs = librosa.fft_frequencies(
                sr=sr, n_fft=stft.shape[0] * 2 - 1)
            avg_magnitude = np.mean(magnitude, axis=1)
            peaks, _ = signal.find_peaks(
                avg_magnitude, distance=len(avg_magnitude) // 20)
            if len(peaks) >= 2:
                features['formant_f1_mean'] = freqs[peaks[0]]
                features['formant_f2_mean'] = freqs[peaks[1]]
                features['formant_stability'] = 0.7
            else:
                features.update(
                    {'formant_f1_mean': 0, 'formant_f2_mean': 0, 'formant_stability': 0.5})
            mel_spec = librosa.feature.melspectrogram(
                y=audio, sr=sr, n_mels=40)
            mel_spec_db = librosa.power_to_db(mel_spec)
            spectral_consistency = []
            for i in range(1, min(mel_spec_db.shape[1], 100)):
                corr = np.corrcoef(mel_spec_db[:, i - 1], mel_spec_db[:, i])[0, 1]
                spectral_consistency.append(corr if not np.isnan(corr) else 0)
            features['spectral_consistency'] = np.mean(
                spectral_consistency) if spectral_consistency else 0.5
            high_freq_start = magnitude.shape[0] // 2
            high_freq_energy = np.mean(magnitude[high_freq_start:, :])
            total_energy = np.mean(magnitude)
            features['high_freq_artifact_ratio'] = high_freq_energy / \
                (total_energy + 1e-10)
            if len(audio) > sr // 10:
                autocorr = np.correlate(
                    audio[:sr // 5], audio[:sr // 5], mode='full')
                autocorr = autocorr[autocorr.size // 2:]
                peaks, _ = signal.find_peaks(
                    autocorr, height=np.max(autocorr) * 0.1)
                if len(peaks) > 1:
                    peak_intervals = np.diff(peaks)
                    features['periodic_artifact_strength'] = np.std(
                        peak_intervals) / (np.mean(peak_intervals) + 1e-10)
                else:
                    features['periodic_artifact_strength'] = 0
            else:
                features['periodic_artifact_strength'] = 0
        except Exception as e:
            print(
                f"Voice conversion artifact detection error: {e}")
            features.update({
                'formant_f1_mean': 0, 'formant_f2_mean': 0, 'formant_stability': 0.5,
                'spectral_consistency': 0.5, 'high_freq_artifact_ratio': 0, 'periodic_artifact_strength': 0
            })
        return features

    def _analyze_vocal_tract_consistency(self, audio, sr):
        features = {}
        try:
            lpc_order = 10
            frame_length = sr // 20
            hop_length = sr // 40
            if len(audio) < frame_length:
                features.update(
                    {'vocal_tract_stability': 0.5, 'lpc_residual_error': 0, 'lpc_coefficient_variance': 0})
                return features
            lpc_coefficients = []
            residual_errors = []
            for start in range(0, len(audio) - frame_length, hop_length):
                frame = audio[start:start + frame_length]
                windowed_frame = frame * np.hanning(len(frame))
                try:
                    if np.std(windowed_frame) > 1e-6:
                        lpc_coeffs = librosa.lpc(
                            windowed_frame, order=lpc_order)
                        lpc_coefficients.append(lpc_coeffs[1:])
                        error = np.var(windowed_frame)
                        residual_errors.append(error)
                except Exception:
                    lpc_coefficients.append(np.zeros(lpc_order))
                    residual_errors.append(0)
            if len(lpc_coefficients) > 1:
                lpc_coefficients = np.array(lpc_coefficients)
                lpc_stability = []
                for i in range(1, len(lpc_coefficients)):
                    stability = np.corrcoef(
                        lpc_coefficients[i - 1], lpc_coefficients[i])[0, 1]
                    lpc_stability.append(
                        stability if not np.isnan(stability) else 0)
                features['vocal_tract_stability'] = np.mean(
                    lpc_stability) if lpc_stability else 0.5
                features['lpc_residual_error'] = np.mean(
                    residual_errors)
                features['lpc_coefficient_variance'] = np.mean(
                    np.var(lpc_coefficients, axis=0))
            else:
                features.update(
                    {'vocal_tract_stability': 0.5, 'lpc_residual_error': 0, 'lpc_coefficient_variance': 0})
        except Exception as e:
            print(f"Vocal tract analysis error: {e}")
            features.update(
                {'vocal_tract_stability': 0.5, 'lpc_residual_error': 0, 'lpc_coefficient_variance': 0})
        return features

    def _analyze_breathing_patterns(self, audio, sr):
        features = {}
        try:
            if len(audio) < sr:
                features.update(
                    {'breath_regularity': 0.5, 'breath_duration_consistency': 0.5, 'breath_frequency': 0})
                return features
            nyquist = sr / 2
            low_cutoff = 500 / nyquist
            if low_cutoff < 1:
                b, a = signal.butter(4, low_cutoff, btype='low')
                breath_audio = signal.filtfilt(b, a, audio)
            else:
                breath_audio = audio
            breath_energy = librosa.feature.rms(
                y=breath_audio, frame_length=2048, hop_length=512)[0]
            if len(breath_energy) > 10:
                breath_threshold = np.percentile(
                    breath_energy, 30)
                breath_segments = breath_energy < breath_threshold
                breath_transitions = np.diff(
                    breath_segments.astype(int))
                breath_starts = np.where(
                    breath_transitions == 1)[0]
                breath_ends = np.where(
                    breath_transitions == -1)[0]
                if len(breath_starts) > 2 and len(breath_ends) > 2:
                    breath_durations = (
                        breath_ends[:len(breath_starts)] - breath_starts[:len(breath_ends)]
                    ) * (512 / sr)
                    inter_breath_intervals = np.diff(
                        breath_starts) * (512 / sr)
                    features['breath_regularity'] = 1 - (
                        np.std(inter_breath_intervals) / (np.mean(inter_breath_intervals) + 1e-10)
                    )
                    features['breath_duration_consistency'] = 1 - (
                        np.std(breath_durations) / (np.mean(breath_durations) + 1e-10)
                    )
                    features['breath_frequency'] = len(
                        breath_starts) / (len(audio) / sr)
                    features['breath_regularity'] = max(
                        0, min(1, features['breath_regularity']))
                    features['breath_duration_consistency'] = max(
                        0, min(1, features['breath_duration_consistency']))
                else:
                    features.update(
                        {'breath_regularity': 0.5, 'breath_duration_consistency': 0.5, 'breath_frequency': 0})
            else:
                features.update(
                    {'breath_regularity': 0.5, 'breath_duration_consistency': 0.5, 'breath_frequency': 0})
        except Exception as e:
            print(f"Breathing pattern analysis error: {e}")
            features.update(
                {'breath_regularity': 0.5, 'breath_duration_consistency': 0.5, 'breath_frequency': 0})
        return features


def extract_forensic_features(audio, sr=16000):
    all_features = []
    cut_detector = CutSpliceDetector()
    mimic_detector = VoiceMimicDetector()
    try:
        if len(audio) < sr // 2:
            audio = np.pad(audio, (0, sr // 2 - len(audio)), mode='constant')

        basic_features = extract_basic_features(audio, sr)
        all_features.extend(basic_features)

        cut_features, edit_points = cut_detector.detect_cuts_and_splices(
            audio, sr)
        all_features.extend(list(cut_features.values()))

        mimic_features = mimic_detector.detect_voice_mimicry(audio, sr)
        all_features.extend(list(mimic_features.values()))

        advanced_features = extract_advanced_tampering_features(
            audio, sr)
        all_features.extend(advanced_features)

        feature_array = np.array(all_features, dtype=np.float32)
        feature_array = np.nan_to_num(
            feature_array, nan=0.0, posinf=1e6, neginf=-1e6)

        return feature_array, edit_points
    except Exception as e:
        print(f"Forensic feature extraction error: {e}")
        return np.zeros(150, dtype=np.float32), []


def extract_basic_features(audio, sr=16000):
    features = []
    try:
        mfcc = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13)
        mfcc_delta = librosa.feature.delta(mfcc)
        mfcc_delta2 = librosa.feature.delta(mfcc, order=2)
        features.extend([
            np.mean(mfcc, axis=1), np.std(mfcc, axis=1),
            np.mean(mfcc_delta, axis=1), np.std(mfcc_delta, axis=1),
            np.mean(mfcc_delta2, axis=1), np.std(mfcc_delta2, axis=1)
        ])
        spectral_centroids = librosa.feature.spectral_centroid(
            y=audio, sr=sr)[0]
        spectral_rolloff = librosa.feature.spectral_rolloff(
            y=audio, sr=sr)[0]
        spectral_bandwidth = librosa.feature.spectral_bandwidth(
            y=audio, sr=sr)[0]
        spectral_contrast = librosa.feature.spectral_contrast(
            y=audio, sr=sr)
        spectral_flatness = librosa.feature.spectral_flatness(
            y=audio)[0]
        features.extend([
            np.mean(spectral_centroids), np.std(spectral_centroids),
            np.mean(spectral_rolloff), np.std(spectral_rolloff),
            np.mean(spectral_bandwidth), np.std(spectral_bandwidth),
            np.mean(spectral_contrast, axis=1), np.std(spectral_contrast, axis=1),
            np.mean(spectral_flatness), np.std(spectral_flatness)
        ])
        zero_crossings = librosa.feature.zero_crossing_rate(
            audio)[0]
        rms_energy = librosa.feature.rms(y=audio)[0]
        features.extend([
            np.mean(zero_crossings), np.std(zero_crossings),
            np.mean(rms_energy), np.std(rms_energy)
        ])
        try:
            pitches, magnitudes = librosa.piptrack(
                y=audio, sr=sr)
            pitch_mean = np.mean(pitches[pitches > 0]
                                 ) if np.any(pitches > 0) else 0
            pitch_std = np.std(pitches[pitches > 0]
                               ) if np.any(pitches > 0) else 0
            harmonic, percussive = librosa.effects.hpss(audio)
            harmonic_ratio = np.sum(harmonic ** 2) / \
                (np.sum(audio ** 2) + 1e-10)
            features.extend([pitch_mean, pitch_std, harmonic_ratio])
        except Exception:
            features.extend([0, 0, 0.5])
        try:
            stft_full = librosa.stft(audio, hop_length=256)
            magnitude = np.abs(stft_full)
            frame_energy = np.sum(magnitude ** 2, axis=0)
            if len(frame_energy) > 0:
                quiet_threshold = np.percentile(frame_energy, 20)
                quiet_frames = frame_energy < quiet_threshold
                if np.sum(quiet_frames) > 0:
                    noise_spectrum = np.mean(
                        magnitude[:, quiet_frames], axis=1)
                    signal_spectrum = np.mean(magnitude, axis=1)
                    noise_power = np.mean(noise_spectrum ** 2)
                    signal_power = np.mean(signal_spectrum ** 2)
                    snr_estimate = 10 * \
                        np.log10(signal_power / (noise_power + 1e-10))
                    noise_variance = np.var(noise_spectrum)
                    features.extend(
                        [noise_power, snr_estimate, noise_variance])
                else:
                    features.extend([np.var(audio), 20, 0.1])
            else:
                features.extend([np.var(audio), 20, 0.1])
        except Exception:
            features.extend([np.var(audio), 20, 0.1])
        try:
            max_audio_len = min(len(audio), 8192)
            coeffs = pywt.wavedec(
                audio[:max_audio_len], 'db4', level=4)
            wavelet_energy = [np.sum(c ** 2) for c in coeffs[:5]]
            wavelet_entropy = [-np.sum(c ** 2 * np.log(np.abs(c ** 2) + 1e-10))
                               for c in coeffs[:5]]
            features.extend(wavelet_energy + wavelet_entropy)
        except Exception:
            features.extend([0] * 10)
    except Exception as e:
        print(f"Basic feature extraction error: {e}")
        features = [0] * 90
    flat_features = []
    for feature in features:
        if isinstance(feature, np.ndarray):
            flat_features.extend(feature.flatten())
        else:
            flat_features.append(feature)
    return flat_features


def extract_advanced_tampering_features(audio, sr=16000):
    features = []
    try:
        stft = librosa.stft(audio, n_fft=1024)
        magnitude = np.abs(stft)
        harmonic_structure = []
        max_frames = min(magnitude.shape[1], 100)
        for frame in range(max_frames):
            frame_mag = magnitude[:, frame]
            peaks, _ = signal.find_peaks(
                frame_mag, distance=len(frame_mag) // 40)
            if len(peaks) >= 3:
                ratios = [peaks[i + 1] / peaks[i]
                          for i in range(min(2, len(peaks) - 1))]
                harmonic_structure.append(np.mean(ratios))
            else:
                harmonic_structure.append(0)
        harmonic_stability = np.std(
            harmonic_structure) if harmonic_structure else 0
        features.append(min(harmonic_stability, 10))
        high_freq_power = np.mean(magnitude[int(
            0.8 * magnitude.shape[0]):, :])
        total_power = np.mean(magnitude)
        aliasing_ratio = high_freq_power / (total_power + 1e-10)
        features.append(min(aliasing_ratio, 5))
        noise_floor = []
        window_size = sr // 4
        hop_size = window_size // 2
        for start in range(0, len(audio) - window_size, hop_size):
            if start + window_size < len(audio):
                window = audio[start:start + window_size]
                noise_estimate = np.percentile(np.abs(window), 10)
                noise_floor.append(noise_estimate)
            if len(noise_floor) >= 10:
                break
        if noise_floor:
            noise_consistency = 1 - (np.std(noise_floor) /
                                     (np.mean(noise_floor) + 1e-10))
            features.append(max(0, min(1, noise_consistency)))
        else:
            features.append(0.5)
        stft_phase = np.angle(stft)
        phase_deviation = np.std(
            np.diff(stft_phase[:, :min(stft_phase.shape[1], 50)], axis=1),
            axis=1
        )
        compression_artifacts = np.mean(phase_deviation)
        features.append(min(compression_artifacts, 10))
        mel_spec = librosa.feature.melspectrogram(
            y=audio, sr=sr, n_mels=20)
        mel_spec_db = librosa.power_to_db(mel_spec)
        if mel_spec_db.shape[1] > 1:
            max_frames = min(mel_spec_db.shape[1], 50)
            similarity_scores = []
            for i in range(1, max_frames):
                similarity = np.corrcoef(
                    mel_spec_db[:, i - 1], mel_spec_db[:, i])[0, 1]
                if not np.isnan(similarity):
                    similarity_scores.append(similarity)
            if similarity_scores:
                high_similarity_ratio = np.sum(
                    np.array(similarity_scores) > 0.9) / len(similarity_scores)
                features.append(min(high_similarity_ratio, 1))
            else:
                features.append(0)
        else:
            features.append(0)
    except Exception as e:
        print(f"Advanced tampering feature extraction error: {e}")
        features = [0] * 5
    return features



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

    def detect_tampering(self, features):
        if not self.model_loaded:
            if not self.load_model_from_local():
                return {
                    "result": "Error",
                    "confidence": 0.0,
                    "message": "Model not loaded"
                }

        try:
            if features is None or features.size == 0:
                print("❌ Features are None or empty")
                return {
                    "result": "Error",
                    "confidence": 0.0,
                    "message": "No features extracted"
                }

            print(f"🔎 Feature shape before scaling: {features.shape}")

            features_reshaped = features.reshape(1, -1)

            features_scaled = self.scaler.transform(features_reshaped)
            print(f"✅ Feature shape after scaling: {features_scaled.shape}")

            prediction = self.model.predict(features_scaled, verbose=0)[0][0]
            print(f"✅ Prediction raw: {prediction}")

            if prediction > 0.5:
                result = "Authentic"
                confidence = float(prediction)
            else:
                result = "Tampered"
                confidence = float(1 - prediction)

            return {
                "result": result,
                "confidence": confidence,
                "message": f"Audio classified as {result} with {confidence:.2%} confidence"
            }
        except Exception as e:
            print(f"❌ Detection error: {e}")
            return {
                "result": "Error",
                "confidence": 0.0,
                "message": f"Detection error: {e}"
            }

# ================== SPEECHBRAIN SETUP ==================
print("🔊 Loading SpeechBrain ECAPA-TDNN model...")
speaker_model = SpeakerRecognition.from_hparams(
    source="speechbrain/spkrec-ecapa-voxceleb",
    savedir="pretrained_models/spkrec-ecapa-voxceleb",
    run_opts={"device": "cuda"} if torch.cuda.is_available() else {}
)
print("✅ Speaker model loaded")

SPEAKER_THRESHOLD = 0.25

def verify_speaker_files(file1, file2):
    """
    Uses SpeechBrain ECAPA-TDNN to verify two speakers.
    Returns a dictionary with verification results.
    
    Args:
        file1: Path to primary audio file (should already be absolute/normalized)
        file2: Path to reference audio file (should already be absolute/normalized)
    """
    try:
        print(f"🔍 Verifying speakers: {file1} vs {file2}")
        
        # Files should already be absolute paths, just verify they exist
        if not os.path.exists(file1):
            print(f"❌ Primary file not found: {file1}")
            return {
                "result": "Error",
                "error": "Primary audio file not found",
                "similarity_score": 0.0,
                "overall_confidence": 0.0,
                "cosine_similarity": 0.0,
                "pitch_similarity": 0.0,
                "formant_similarity": 0.0,
                "spectral_similarity": 0.0
            }
            
        if not os.path.exists(file2):
            print(f"❌ Reference file not found: {file2}")
            return {
                "result": "Error",
                "error": "Reference audio file not found",
                "similarity_score": 0.0,
                "overall_confidence": 0.0,
                "cosine_similarity": 0.0,
                "pitch_similarity": 0.0,
                "formant_similarity": 0.0,
                "spectral_similarity": 0.0
            }
        
        # Check file sizes
        file1_size = os.path.getsize(file1)
        file2_size = os.path.getsize(file2)
        print(f"📏 Primary file size: {file1_size} bytes")
        print(f"📏 Reference file size: {file2_size} bytes")
        
        if file1_size == 0 or file2_size == 0:
            print("❌ One or both audio files are empty")
            return {
                "result": "Error",
                "error": "Empty audio file detected",
                "similarity_score": 0.0,
                "overall_confidence": 0.0,
                "cosine_similarity": 0.0,
                "pitch_similarity": 0.0,
                "formant_similarity": 0.0,
                "spectral_similarity": 0.0
            }
        
        # Run SpeechBrain verification - pass paths directly without modification
        print("🎯 Running SpeechBrain ECAPA-TDNN verification...")
        score, prediction = speaker_model.verify_files(file1, file2)
        
        # Convert score to confidence (0-1 range)
        # SpeechBrain scores are cosine similarity (-1 to 1)
        raw_score = float(score.item())
        confidence = (raw_score + 1) / 2  # Normalize to 0-1
        
        # Determine result based on threshold
        result = "Match" if prediction else "Mismatch"
        
        result_dict = {
            "result": result,
            "similarity_score": raw_score,
            "overall_confidence": min(1.0, max(0.0, confidence)),
            "cosine_similarity": raw_score,
            "pitch_similarity": 0.0,  # Not computed by SpeechBrain
            "formant_similarity": 0.0,  # Not computed by SpeechBrain
            "spectral_similarity": 0.0  # Not computed by SpeechBrain
        }
        
        print(f"✅ Speaker verification complete: {result} (score: {raw_score:.4f}, confidence: {confidence:.2%})")
        return result_dict
        
    except Exception as e:
        print(f"❌ Speaker verification error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "result": "Error",
            "error": str(e),
            "similarity_score": 0.0,
            "overall_confidence": 0.0,
            "cosine_similarity": 0.0,
            "pitch_similarity": 0.0,
            "formant_similarity": 0.0,
            "spectral_similarity": 0.0
        }


tamper_detector = TamperDetector()

# Initialize processors
tamper_detector = TamperDetector()
#speaker_verifier = SpeakerVerifier()

# Utility Functions
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())


def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed)


def generate_token(user_id):
    payload = {
        'user_id': str(user_id),
        'exp': datetime.now(timezone.utc).timestamp() + 86400
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')


def verify_token(token):
    try:
        payload = jwt.decode(
            token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload['user_id']
    except jwt.ExpiredSignatureError:
        print("Token has expired")
        return None
    except jwt.InvalidTokenError:
        print("Invalid token")
        return None


# Database Models
def init_db():
    if db.users.find_one({'username': 'admin'}) is None:
        admin_user = {
            'username': 'admin',
            'password': hash_password('admin123'),
            'role': 'admin',
            'full_name': 'System Administrator',
            'created_at': datetime.now(timezone.utc)
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


@app.route('/api/auth/create-user', methods=['POST'])
def create_user():
    try:
        data = request.get_json()
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.replace('Bearer ', '')
        user_id = verify_token(token)
        if not user_id:
            return jsonify({'success': False, 'message': 'Unauthorized - Invalid token'}), 401
        try:
            current_user = db.users.find_one({'_id': ObjectId(user_id)})
        except Exception:
            return jsonify({'success': False, 'message': 'Invalid user ID format'}), 401
        if not current_user or current_user['role'] != 'admin':
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        required_fields = ['username', 'password', 'full_name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field} is required'}), 400
        if db.users.find_one({'username': data['username']}):
            return jsonify({'success': False, 'message': 'Username already exists'}), 400
        new_user = {
            'username': data['username'],
            'password': hash_password(data['password']),
            'role': data.get('role', 'user'),
            'full_name': data['full_name'],
            'badge_number': data.get('badge_number', ''),
            'department': data.get('department', ''),
            'created_at': datetime.now(timezone.utc)
        }
        result = db.users.insert_one(new_user)
        return jsonify({'success': True, 'user_id': str(result.inserted_id)})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500


@app.route('/api/cases', methods=['GET'])
def get_cases():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    if not user_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    try:
        current_user = db.users.find_one({'_id': ObjectId(user_id)})
        if not current_user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
    except Exception:
        return jsonify({'success': False, 'message': 'Invalid user ID'}), 401
    if current_user['role'] == 'admin':
        cases = list(db.cases.find().sort('created_at', -1))
    else:
        cases = list(db.cases.find(
            {'officer_id': str(user_id)}).sort('created_at', -1))
    for case in cases:
        case['_id'] = str(case['_id'])
    return jsonify({'success': True, 'cases': cases})



@app.route('/api/upload-audio', methods=['POST'])
def upload_audio():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    if not user_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    try:
        current_user = db.users.find_one({'_id': ObjectId(user_id)})
    except Exception:
        return jsonify({'success': False, 'message': 'Invalid user ID'}), 401

    audio_file = request.files.get('audio_file')
    reference_file = request.files.get('reference_file')
    case_number = request.form.get('case_number')
    device = request.form.get('device')
    location = request.form.get('location')

    if not audio_file:
        return jsonify({'success': False, 'message': 'No audio file provided'}), 400

    try:
        # ---------- 1. Save primary file ----------
        case_dir = os.path.join(app.config['UPLOAD_FOLDER'], case_number)
        os.makedirs(case_dir, exist_ok=True)
        file_number = f"AE{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        
        primary_filename = secure_filename(f"{file_number}_{audio_file.filename}")
        primary_path = os.path.join(case_dir, primary_filename)
        audio_file.save(primary_path)
        
        # DEBUG: Print the path immediately after save
        print(f"🔧 DEBUG: primary_path after save: {primary_path}")
        print(f"🔧 DEBUG: Is absolute? {os.path.isabs(primary_path)}")

        # ---------- 2. SHA-256 hash ----------
        with open(primary_path, 'rb') as f:
            audio_hash = hashlib.sha256(f.read()).hexdigest()

        # ---------- 3. Duplicate check ----------
        existing = db.cases.find_one({'audio_hash': audio_hash})
        if existing:
            prev_user = existing.get('officer_name', 'Unknown')
            prev_time = existing['created_at'].strftime('%Y-%m-%d %H:%M:%S') if existing.get('created_at') else ''
            return jsonify({
                'success': True,
                'duplicate': True,
                'message': f"File already analysed by {prev_user} on {prev_time}.",
                'tamper_result': existing.get('tamper_result', {}),
                'speaker_result': existing.get('speaker_result'),
                'comparison_status': 'Identical file previously analysed'
            })

        # ---------- 4. Modified-evidence check ----------
        prev_case = db.cases.find_one({'case_number': case_number})
        modification_status = ("Modified version of previous audio evidence"
                               if prev_case and prev_case['audio_hash'] != audio_hash
                               else "New audio evidence")

        # ---------- 5. Tamper detection ----------
        audio, sr = librosa.load(primary_path, sr=16000, duration=10)
        features, edit_points = extract_forensic_features(audio, sr)
        tamper_result = tamper_detector.detect_tampering(features)

        visual_path, pct_vis = visualize_tampering(primary_path, edit_points, tamper_result)
        tamper_result["tamper_percentage_visual"] = round(pct_vis, 2)
        if visual_path and os.path.exists(visual_path):
            tamper_result['visual_url'] = f"/uploads/{case_number}/{os.path.basename(visual_path)}"

        duration = len(audio) / sr
        tamper_pct = min((len(edit_points) * (sr // 10) / len(audio)) * 100, 100) if len(audio) else 0
        tamper_segments = []
        for ep in edit_points[:5]:
            t = round(ep['time'], 2)
            tamper_segments.append({
                "time": t,
                "confidence": round(float(ep['confidence']), 3),
                "tamper_type": ep.get('tamper_type', 'UNKNOWN ARTIFACT'),
                "explanation": build_tamper_explanation(ep.get('tamper_type', ''), t, ep['confidence'])
            })
        tamper_result.update({
            "tamper_percentage": round(tamper_pct, 2),
            "tamper_segments": tamper_segments,
            "duration": round(duration, 2)
        })

        # ---------- 6. Speaker verification ----------
        speaker_result = None
        if reference_file:
            print("📁 Reference file received, processing speaker verification...")
            
            # Save reference file
            ref_filename = secure_filename(f"{file_number}_ref_{reference_file.filename}")
            ref_path = os.path.join(case_dir, ref_filename)
            reference_file.save(ref_path)
            
            # DEBUG
            print(f"🔧 DEBUG: ref_path after save: {ref_path}")
            print(f"🔧 DEBUG: Is absolute? {os.path.isabs(ref_path)}")
            
            # DON'T call abspath() - just use paths as-is since os.path.join already made them absolute
            print(f"🔍 Primary audio: {primary_path}")
            print(f"🔍 Reference audio: {ref_path}")
            
            # Verify files exist
            if not os.path.exists(primary_path):
                print(f"❌ Primary file not found at {primary_path}")
                speaker_result = {
                    "result": "Error",
                    "error": "Primary file not found after save",
                    "similarity_score": 0.0,
                    "overall_confidence": 0.0,
                    "cosine_similarity": 0.0,
                    "pitch_similarity": 0.0,
                    "formant_similarity": 0.0,
                    "spectral_similarity": 0.0
                }
            elif not os.path.exists(ref_path):
                print(f"❌ Reference file not found at {ref_path}")
                speaker_result = {
                    "result": "Error",
                    "error": "Reference file not found after save",
                    "similarity_score": 0.0,
                    "overall_confidence": 0.0,
                    "cosine_similarity": 0.0,
                    "pitch_similarity": 0.0,
                    "formant_similarity": 0.0,
                    "spectral_similarity": 0.0
                }
            else:
                print("✅ Both files found, running speaker verification...")
                print(f"🔧 FINAL CHECK - primary_path: {primary_path}")
                print(f"🔧 FINAL CHECK - ref_path: {ref_path}")
                print(f"🔧 Path contains double prefix? {primary_path.count('audio_evidence_system') > 1}")
                # Pass paths directly without any modification
                speaker_result = verify_speaker_files(primary_path, ref_path)
                
                if speaker_result:
                    print(f"✅ Speaker verification complete: {speaker_result}")
                else:
                    print("⚠️ Speaker verification returned None")
        else:
            print("ℹ️ No reference file provided, skipping speaker verification")

        # ---------- 7. Blockchain metadata ----------
        metadata = {
            'case_number': case_number,
            'file_number': file_number,
            'officer': current_user['full_name'],
            'device': device,
            'location': location,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'filename': primary_filename
        }
        blockchain_entries = [
            {
                'case_id': case_number,
                'audio_hash': audio_hash,
                'metadata': json.dumps(metadata),
                'timestamp': datetime.now(timezone.utc),
                'block_type': 'evidence_storage'
            },
            {
                'case_id': case_number,
                'results': json.dumps({
                    'tamper_detection': tamper_result,
                    'speaker_verification': speaker_result,
                    'analysis_timestamp': datetime.now(timezone.utc).isoformat()
                }),
                'timestamp': datetime.now(timezone.utc),
                'block_type': 'analysis_results'
            }
        ]

        # ---------- 8. MongoDB record ----------
        db.cases.insert_one({
            'case_number': case_number,
            'file_number': file_number,
            'officer_id': str(user_id),
            'officer_name': current_user['full_name'],
            'device': device,
            'location': location,
            'audio_hash': audio_hash,
            'tamper_result': tamper_result,
            'speaker_result': speaker_result,
            'comparison_status': modification_status,
            'verified_by': current_user['full_name'],
            'verified_at': datetime.now(timezone.utc),
            'blockchain_entries': blockchain_entries,
            'created_at': datetime.now(timezone.utc),
            'status': 'completed'
        })

        # ---------- 9. Response ----------
        print(f"📤 Sending response with speaker_result: {speaker_result}")
        
        return jsonify({
            'success': True,
            'file_number': file_number,
            'tamper_result': tamper_result,
            'speaker_result': speaker_result,
            'comparison_status': modification_status,
            'verified_by': current_user['full_name'],
            'verified_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
            'message': 'Audio processed successfully through complete workflow'
        })

    except Exception as e:
        print(f"❌ Processing error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Processing error: {str(e)}'}), 500
@app.route('/api/generate-report/<case_id>', methods=['GET'])
def generate_report(case_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    if not user_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    try:
        case = db.cases.find_one({'_id': ObjectId(case_id)})
        if not case:
            return jsonify({'success': False, 'message': 'Case not found'}), 404

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        title = Paragraph("Audio Evidence Verification Report", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 12))

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

        audio_details = Paragraph("Audio Details", styles['Heading2'])
        story.append(audio_details)
        audio_info = [
            ['Device:', case['device']],
            ['Location:', case['location']],
        ]
        audio_table = Table(audio_info)
        audio_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        story.append(audio_table)
        story.append(Spacer(1, 12))

        analysis_header = Paragraph("Audio Analysis", styles['Heading2'])
        story.append(analysis_header)
        tamper_result = case['tamper_result']
        analysis_info = [
            ['Result:', tamper_result['result']],
            ['Confidence:', f"{tamper_result['confidence']:.2%}"],
            ['Estimated Tampered Region:',
             f"{tamper_result.get('tamper_percentage', 0):.2f}%"],
            ['Model Used:', 'Forensic Tamper Detection Model'],
        ]
        analysis_table = Table(analysis_info)
        analysis_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        story.append(analysis_table)
        story.append(Spacer(1, 12))

        # ### NEW: Add table of top tamper segments with types
        segments = tamper_result.get("tamper_segments", [])
        if segments:
            seg_header = Paragraph("Detected Tampered Segments", styles['Heading2'])
            story.append(seg_header)

            seg_rows = [["Time (s)", "Confidence", "Tamper Type"]]
            for seg in segments:
                seg_rows.append([
                    f"{seg['time']:.2f}",
                    f"{seg['confidence']:.3f}",
                    seg.get('tamper_type', 'Unknown')
                ])

            seg_table = Table(seg_rows)
            seg_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
            ]))
            story.append(seg_table)
            story.append(Spacer(1, 12))

        if case['speaker_result']:
            voice_header = Paragraph("Voice Verification", styles['Heading2'])
            story.append(voice_header)
            speaker_result = case['speaker_result']
            voice_info = [
                ['Cosine Similarity:',
                 f"{speaker_result['cosine_similarity']:.3f}"],
                ['Pitch Similarity:',
                 f"{speaker_result['pitch_similarity']:.3f}"],
                ['Formant Similarity:',
                 f"{speaker_result['formant_similarity']:.3f}"],
                ['Spectral Similarity:',
                 f"{speaker_result['spectral_similarity']:.3f}"],
                ['Overall Result:', speaker_result['result']],
                ['Confidence:',
                 f"{speaker_result['overall_confidence']:.2%}"],
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
            no_voice = Paragraph(
                "Voice Verification: N/A (No reference audio provided)",
                styles['Normal']
            )
            story.append(no_voice)
            story.append(Spacer(1, 12))

        summary_header = Paragraph("Result Summary", styles['Heading2'])
        story.append(summary_header)
        tamper_status = "authentic" if tamper_result['result'] == 'Authentic' else "potentially tampered"
        speaker_status = ""
        if case['speaker_result']:
            speaker_match = case['speaker_result']['result'].lower()
            speaker_status = f" Speaker verification indicates a {speaker_match} with the reference audio."
        summary_text = (
            f"Based on technical analysis, the submitted audio evidence appears to be {tamper_status} "
            f"with {tamper_result['confidence']:.1%} confidence.{speaker_status} "
            f"This analysis was conducted using a blockchain-verified audio evidence verification system "
            f"on {case['created_at'].strftime('%B %d, %Y at %H:%M UTC')}."
        )
        summary = Paragraph(summary_text, styles['Normal'])
        story.append(summary)
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


@app.route('/static/<path:filename>')
def serve_static(filename):
    static_dir = os.path.join(os.getcwd(), 'static')
    return send_from_directory(static_dir, filename)


@app.route('/uploads/<case_id>/<filename>')
def serve_uploaded_file(case_id, filename):
    """Serves uploaded visualizations or audio files safely."""
    uploads_dir = os.path.join(app.config['UPLOAD_FOLDER'], case_id)
    file_path = os.path.join(uploads_dir, filename)

    print(f"🧭 Looking for file at: {file_path}")  # debug line

    if os.path.exists(file_path):
        return send_from_directory(uploads_dir, filename, as_attachment=True)
    else:
        print("❌ File not found on server!")
        return jsonify({'success': False, 'message': 'File not found'}), 404


# Initialize application
if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    init_db()
    init_contract()
    app.run(debug=True, host='0.0.0.0', port=5000)

