# Real-Time Dance Guide System

An AI-powered web application that enables users to learn, practice, and evaluate dance movements using real-time feedback, motion analysis, and LLM-based interpretation.

---

## Introduction

The Real-Time Dance Guide System is designed to make dance learning accessible, structured, and interactive. Traditional dance training often requires physical instructors and is not accessible to everyone. Existing online resources provide video content but lack personalized feedback and structured guidance.

This system addresses that gap by combining computer vision, deep learning, and Large Language Models (LLMs) to deliver real-time guidance and intelligent performance evaluation.

---

## What the System Does

The application allows users to:

- Learn dance steps through guided tutorials  
- Practice movements with real-time feedback  
- Compare performance with reference choreography  
- Receive AI-generated evaluation and improvement suggestions  

---

## Core Features

### Practice Mode
- Step-by-step guided learning  
- Side-by-side reference comparison  
- Slow-motion playback  
- Real-time pose tracking using webcam  

### Test Mode
- Upload or record full dance performance  
- Automated scoring system  
- Motion accuracy analysis  
- Detailed feedback report  

### AI Capabilities
- Real-time pose estimation  
- Motion alignment and comparison  
- Deep motion analysis using ST-GCN  
- LLM-based feedback generation  

---

## How It Works

1. User provides input via webcam or uploaded video  
2. Video frames are extracted and processed  
3. Pose keypoints are detected using MediaPipe  
4. Keypoints are normalized for consistency  
5. Motion comparison is performed using:
   - Dynamic Time Warping (DTW) for temporal alignment  
   - ST-GCN for spatio-temporal motion analysis  
6. Quantitative metrics are generated  
7. LLM interprets these metrics into human-readable feedback  
8. Results are displayed with overlays and structured reports  

---

## LLM Integration

The system integrates a Large Language Model to convert raw motion evaluation metrics into meaningful, user-friendly feedback.

### Role of LLM
- Translates numerical scores into natural language explanations  
- Identifies incorrect body movements (arms, legs, posture, timing)  
- Provides actionable improvement suggestions  
- Generates overall performance verdict  

### Implementation
- Input: Metrics from DTW and ST-GCN  
- Processing: Prompt-based interpretation  
- Output: Structured feedback and evaluation summary  

---

## Tech Stack

### Frontend
- React.js  
- HTML, CSS, JavaScript  

### Backend
- Django  
- Django REST Framework  

### Machine Learning
- MediaPipe (Pose Estimation)  
- ST-GCN (Spatio-Temporal Graph Convolutional Network)  
- Dynamic Time Warping (DTW)  
- Cosine Similarity  
- Euclidean Distance  

### LLM Integration
- Gemma 3:1B (via Ollama)  
- Used for feedback interpretation  

### Tools and Services
- OpenCV  
- Firebase  
- Python  

---

## Machine Learning Overview

The system uses pose-based motion analysis trained on the AIST Dance Dataset (~5000 videos). Human movements are represented using COCO-17 keypoints.

A self-supervised ST-GCN autoencoder is trained using:

- Reconstruction loss  
- Velocity consistency loss  
- Acceleration loss  
- VICReg regularization  

### Performance
- Validation Loss: 0.4319  
- Training Loss: 0.5358  
- Approx. 5% performance drop with increased camera distance  

---

## System Architecture

- Input: Video (live or uploaded)  
- Processing: Pose extraction and normalization  
- Analysis: DTW + ST-GCN  
- Interpretation: LLM-based feedback  
- Output: Score, explanation, and visual overlays  

---

## Setup Instructions

### Clone Repository
git clone https://github.com/your-username/dance-guide-system.git  
cd dance-guide-system  

### Backend Setup
cd backend  
python -m venv venv  
source venv/bin/activate   # Windows: venv\Scripts\activate  
pip install -r requirements.txt  
python manage.py migrate  
python manage.py runserver  

### Frontend Setup
cd frontend  
npm install  
npm start  

---

## Applications

- Dance learning platforms  
- Short-form content creators  
- Fitness and motion training  
- Educational tools  
- AI-based interactive learning systems  

---

## Future Improvements

- Multi-person dance evaluation  
- Mobile application support  
- Faster real-time processing  
- Transformer-based pose models  
- Enhanced LLM reasoning and personalization  

---

## Contributors

- Sambad Khatiwada  
- Lokendra Joshi  
- Raghabendra Chaudhary  
- Santu Jhankri Magar  

---

## Contact

For collaboration or inquiries, connect via GitHub or professional platforms.

---

## License

This project is developed for academic purposes and can be extended for production use.
