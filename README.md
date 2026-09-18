# Blockchain-Integrated Audio Forensics Framework

A secure and intelligent framework for detecting audio tampering, verifying speaker identity, and maintaining the integrity of digital audio evidence using deep learning, cryptography, and blockchain technology.

## Overview

Digital audio recordings are increasingly used as evidence in investigations, but they can be altered using audio editing tools and AI-generated voice technologies. Identifying such modifications and ensuring that evidence remains unchanged are important challenges in digital forensics.

This project presents a Blockchain-Integrated Audio Forensics Framework that combines machine learning-based audio analysis with cryptographic hashing and blockchain-based evidence management. The system analyzes uploaded audio recordings, extracts relevant forensic features, detects possible tampering, and supports speaker verification. It also generates a SHA-256 hash for the audio file and records evidence-related information on a blockchain to support integrity verification and traceability.

The framework includes a web-based interface that allows authorized users to manage audio evidence, view analysis results, and generate forensic reports.

## Objectives

* Detect possible tampering in digital audio recordings.
* Extract meaningful audio features for forensic analysis.
* Develop a deep learning model for audio tampering classification.
* Support speaker verification using reference audio recordings.
* Generate cryptographic hashes to identify changes in audio evidence.
* Maintain evidence-related records using blockchain technology.
* Protect sensitive information through encryption and access control.
* Provide an accessible dashboard for audio analysis and evidence management.

## Key Features

### Audio Preprocessing

The system prepares audio recordings for analysis through preprocessing operations such as silence trimming, amplitude normalization, and spectral-subtraction noise reduction. Audio is processed at a standardized sampling rate of 22,050 Hz.

### Forensic Feature Extraction

Relevant audio characteristics are extracted using Librosa and other numerical processing libraries. These features include MFCCs, spectral characteristics, temporal information, and other features used in the classification pipeline.

### Deep Learning-Based Tampering Detection

A four-layer dense neural network is developed to classify audio recordings using extracted forensic features. The model incorporates LeakyReLU activation, batch normalization, and dropout regularization to support model training and generalization.

### Speaker Verification

The framework includes a speaker verification component that compares a test recording with a reference speaker recording. This provides additional information for audio evidence analysis alongside the tampering detection result.

### Cryptographic Evidence Integrity

SHA-256 hashing is used to generate a digital fingerprint of each audio file. The generated hash can be compared with a previously recorded hash to identify changes in the file contents.

### Blockchain-Based Evidence Management

The system uses an Ethereum-compatible blockchain environment and smart contracts to maintain evidence-related records. Ganache is used for local blockchain development and testing, while Web3.py provides the connection between the backend and blockchain.

### Secure Evidence Storage

MongoDB is used to manage evidence metadata and application records. AES and RSA cryptographic mechanisms are incorporated to support the protection of sensitive information.

### Role-Based Access and Reporting

The application provides role-based authentication and a dashboard for authorized users to upload audio, view analysis results, manage evidence information, and generate forensic reports.

## System Architecture

```text
User Authentication
        |
        v
Audio Evidence Upload
        |
        v
Audio Preprocessing
        |
        v
Feature Extraction
        |
        +----------------------+
        |                      |
        v                      v
Tampering Detection     Speaker Verification
        |                      |
        +----------+-----------+
                   |
                   v
           SHA-256 Hashing
                   |
                   v
        Evidence Metadata Storage
                   |
             +-----+-----+
             |           |
             v           v
          MongoDB    Blockchain
             |       Smart Contract
             |           |
             +-----+-----+
                   |
                   v
           Forensic Dashboard
                   |
                   v
            Report Generation
```

## Technologies Used

| Category             | Technologies                         |
| -------------------- | ------------------------------------ |
| Programming Language | Python                               |
| Backend              | Flask                                |
| Frontend             | React, TypeScript                    |
| Machine Learning     | TensorFlow, Scikit-learn             |
| Audio Processing     | Librosa, NumPy                       |
| Database             | MongoDB                              |
| Blockchain           | Ethereum, Ganache, Solidity, Web3.py |
| Cryptography         | SHA-256, AES, RSA                    |
| Model Management     | Joblib                               |
| Development Tools    | Anaconda, Visual Studio Code, Git    |

## Project Structure

```text
audio_evidence_system/
│
├── backend/
│   ├── app.py
│   ├── routes/
│   ├── models/
│   ├── services/
│   └── utils/
│
├── frontend/
│   ├── src/
│   ├── components/
│   └── pages/
│
├── models/
│   └── dt_flight_phase.joblib
│
├── blockchain/
│   ├── contracts/
│   └── deployment/
│
├── audio/
│   ├── uploads/
│   └── processed/
│
├── reports/
│
├── requirements.txt
└── README.md
```

> The directory structure above is an overview. Update it to match the actual files and folders in the repository.

## Installation and Setup

### Prerequisites

Before running the project, install the following:

* Python 3.10
* Anaconda
* MongoDB
* Node.js and npm
* Ganache
* Git

### 1. Clone the Repository

```bash
git clone <YOUR_PRIVATE_REPOSITORY_URL>
cd audio_evidence_system
```

### 2. Create the Python Environment

```bash
conda create -n audio-forensics python=3.10
conda activate audio-forensics
```

### 3. Install Backend Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file and add the required database, blockchain, and application configuration.

```env
MONGO_URI=your_mongodb_connection_string
SECRET_KEY=your_secret_key
BLOCKCHAIN_RPC_URL=http://127.0.0.1:7545
CONTRACT_ADDRESS=your_contract_address
```

Keep credentials and private keys outside the repository.

### 5. Configure the Blockchain

Start Ganache and deploy the project's smart contract using the configured deployment workflow. Update the contract address and blockchain connection settings in the application.

### 6. Run the Application

Start the Flask backend:

```bash
python app.py
```

Start the React frontend from its directory:

```bash
cd frontend
npm install
npm run dev
```

Use the local URL displayed by the development server to access the application.

## Application Workflow

1. The authorized user logs in and uploads an audio recording.
2. The system preprocesses the recording and extracts forensic features.
3. The machine learning model analyzes the audio for possible tampering.
4. The speaker verification component compares the recording with a reference speaker.
5. A SHA-256 hash is generated for the evidence file.
6. Evidence metadata and the cryptographic hash are stored in the database and blockchain, according to the implemented workflow.
7. The user can view the analysis results, verify evidence integrity, and generate a forensic report.

## Evidence Integrity Verification

The system uses SHA-256 to compare the current audio file with its previously recorded hash.

```text
Original Audio File
        |
        v
Stored SHA-256 Hash
        |
        |
Current Audio File
        |
        v
New SHA-256 Hash
        |
        v
Compare Both Hashes
        |
        +------------------+
        |                  |
        v                  v
Hash Match          Hash Mismatch
        |                  |
        v                  v
Contents match     Contents differ
stored evidence    from stored file
```

A matching hash indicates that the compared file contents are consistent with the recorded hash. A mismatch indicates that the file contents have changed and require further examination.

## Machine Learning Model

The project uses a deep learning-based classification pipeline to analyze audio forensic features. The neural network architecture incorporates:

* Dense layers
* LeakyReLU activation
* Batch normalization
* Dropout
* A classification output layer

The model is intended to assist in identifying potential audio manipulation. Its performance depends on the training dataset, audio quality, and the types of manipulation represented during training.

## Blockchain and Security

The blockchain component provides an additional record of evidence-related information, while cryptographic mechanisms support data protection and integrity verification.

| Component         | Purpose                                       |
| ----------------- | --------------------------------------------- |
| SHA-256           | Generate an audio file fingerprint            |
| AES               | Symmetric encryption                          |
| RSA               | Asymmetric cryptographic operations           |
| MongoDB           | Store application and evidence metadata       |
| Blockchain        | Maintain evidence-related transaction records |
| Smart Contract    | Manage blockchain evidence operations         |
| Role-Based Access | Restrict access to authorized users           |

## Limitations

This project is an academic research prototype. Machine learning results should be interpreted as supporting evidence rather than conclusive proof of audio authenticity or tampering.

The framework does not replace a complete professional forensic investigation. Results may vary depending on recording conditions, audio quality, training data, and manipulation techniques.

## Future Enhancements

* Improve detection of AI-generated and cloned voices.
* Integrate advanced speaker verification models such as ECAPA-TDNN.
* Expand the training dataset with diverse audio manipulation techniques.
* Introduce decentralized storage for larger evidence files.
* Improve forensic report generation and evidence tracking.
* Deploy the system in a secure cloud environment.
* Add additional blockchain nodes and production-grade smart contract workflows.

## Academic Project

This project was developed as a major project in the field of Computer Science and Engineering, exploring the integration of artificial intelligence, digital audio forensics, cryptography, and blockchain technology.

## Copyright and License

**Copyright © 2026 Shashank B R. All Rights Reserved.**

This project, including its source code, architecture, documentation, trained models, and related materials, is the intellectual property of the author.

Unauthorized copying, reproduction, modification, distribution, or commercial use of this project or any substantial portion of its contents is prohibited without prior written permission from the copyright holder.

This repository is made available for academic reference and evaluation. No license is granted for reuse or redistribution unless explicitly authorized by the copyright holder.

For permission to use or reproduce any part of this project, contact the author through the repository's official contact details.
