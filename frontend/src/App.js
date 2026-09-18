

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

const API_BASE = 'http://localhost:5000/api';
axios.defaults.baseURL = API_BASE;
axios.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ---------------- LOGIN ----------------
function Login({ onLogin }) {
  const [credentials, setCredentials] = useState({ username: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await axios.post('/auth/login', credentials);
      if (response.data.success) {
        localStorage.setItem('token', response.data.token);
        onLogin(response.data.user);
      }
    } catch (error) {
      setError(error.response?.data?.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-form">
        <h2>Audio Evidence System</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Username:</label>
            <input
              type="text"
              value={credentials.username}
              onChange={(e) => setCredentials({ ...credentials, username: e.target.value })}
              required
            />
          </div>
          <div className="form-group">
            <label>Password:</label>
            <input
              type="password"
              value={credentials.password}
              onChange={(e) => setCredentials({ ...credentials, password: e.target.value })}
              required
            />
          </div>
          {error && <div className="message error"><div className="message-header">❌ Error</div>{error}</div>}
          <button type="submit" disabled={loading}>
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>
      </div>
    </div>
  );
}

// ---------------- ADMIN DASHBOARD ----------------
function AdminDashboard({ user }) {
  const [cases, setCases] = useState([]);
  const [newUser, setNewUser] = useState({
    username: '', password: '', full_name: '', badge_number: '', department: ''
  });
  const [activeTab, setActiveTab] = useState('dashboard');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => { loadCases(); }, []);

  const loadCases = async () => {
    try {
      const response = await axios.get('/cases');
      setCases(response.data.cases || []);
    } catch (error) {
      console.error('Failed to load cases:', error);
    }
  };

  const createUser = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');
    try {
      const response = await axios.post('/auth/create-user', newUser);
      if (response.data.success) {
        setMessage('✅ User created successfully');
        setNewUser({ username: '', password: '', full_name: '', badge_number: '', department: '' });
      }
    } catch (error) {
      setMessage(error.response?.data?.message || 'Failed to create user');
    } finally { setLoading(false); }
  };

  const downloadReport = async (caseId, caseNumber, fileNumber) => {
    try {
      const response = await axios.get(`/generate-report/${caseId}`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Audio_Evidence_Report_${caseNumber}_${fileNumber}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch {
      alert('Failed to generate report');
    }
  };

  return (
    <div className="dashboard">
      <div className="sidebar">
        <h3>Admin Panel</h3>
        <nav>
          <button
            className={activeTab === 'dashboard' ? 'active' : ''}
            onClick={() => setActiveTab('dashboard')}
          >
            Dashboard
          </button>
          <button
            className={activeTab === 'create-user' ? 'active' : ''}
            onClick={() => setActiveTab('create-user')}
          >
            Create User
          </button>
          <button
            className={activeTab === 'profile' ? 'active' : ''}
            onClick={() => setActiveTab('profile')}
          >
            Profile
          </button>
        </nav>
      </div>

      <div className="main-content">
        {activeTab === 'dashboard' && (
          <div>
            <h2>All Cases</h2>
            <div className="cases-table">
              <table>
                <thead>
                  <tr>
                    <th>Case No.</th>
                    <th>File No.</th>
                    <th>Officer</th>
                    <th>Status</th>
                    <th>Timestamp</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {cases.map((case_) => (
                    <tr key={case_._id}>
                      <td>{case_.case_number}</td>
                      <td>{case_.file_number}</td>
                      <td>{case_.officer_name}</td>
                      <td>
                        <span className={`status ${case_.tamper_result?.result?.toLowerCase()}`}>
                          {case_.tamper_result?.result || 'Processing'}
                        </span>
                      </td>
                      <td>{new Date(case_.created_at).toLocaleString()}</td>
                      <td>
                        <button
                          onClick={() =>
                            downloadReport(case_._id, case_.case_number, case_.file_number)
                          }
                          className="download-btn"
                        >
                          Download Report
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === 'create-user' && (
          <div>
            <h2>Create New Officer Account</h2>
            <form onSubmit={createUser} className="user-form">
              <div className="form-row">
                <div className="form-group">
                  <label>Username:</label>
                  <input
                    type="text"
                    value={newUser.username}
                    onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Password:</label>
                  <input
                    type="password"
                    value={newUser.password}
                    onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                    required
                  />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Full Name:</label>
                  <input
                    type="text"
                    value={newUser.full_name}
                    onChange={(e) => setNewUser({ ...newUser, full_name: e.target.value })}
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Badge Number:</label>
                  <input
                    type="text"
                    value={newUser.badge_number}
                    onChange={(e) => setNewUser({ ...newUser, badge_number: e.target.value })}
                  />
                </div>
              </div>
              <div className="form-group">
                <label>Department:</label>
                <input
                  type="text"
                  value={newUser.department}
                  onChange={(e) => setNewUser({ ...newUser, department: e.target.value })}
                />
              </div>
              {message && (
                <div className="message success">
                  <div className="message-header">🟢 Status</div>
                  {message}
                </div>
              )}
              <button type="submit" disabled={loading}>
                {loading ? 'Creating...' : 'Create User'}
              </button>
            </form>
          </div>
        )}

        {activeTab === 'profile' && (
          <div>
            <h2>Profile</h2>
            <div className="profile-info">
              <p><strong>Username:</strong> {user.username}</p>
              <p><strong>Role:</strong> {user.role}</p>
              <p><strong>Full Name:</strong> {user.full_name}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------- USER DASHBOARD ----------------
function UserDashboard({ user }) {
  const [cases, setCases] = useState([]);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [uploadForm, setUploadForm] = useState({
    case_number: '',
    device: '',
    location: '',
  });
  const [files, setFiles] = useState({ audio_file: null, reference_file: null });
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('info');
  const [visualURL, setVisualURL] = useState(null);

  const [tamperSummary, setTamperSummary] = useState(null);
  const [tamperSegments, setTamperSegments] = useState([]);
  const [tamperStatus, setTamperStatus] = useState(null);

  useEffect(() => {
    loadCases();
  }, []);

  const loadCases = async () => {
    try {
      const response = await axios.get('/cases');
      setCases(response.data.cases || []);
    } catch (error) {
      console.error('Failed to load cases:', error);
    }
  };

  const handleFileChange = (e) => {
    const { name, files: fileList } = e.target;
    setFiles({ ...files, [name]: fileList[0] });
  };

  
  const handleUpload = async (e) => {
    e.preventDefault();
    if (!files.audio_file) {
      setMessage('Please select an audio file');
      setMessageType('error');
      return;
    }

    setUploading(true);
    setMessageType('info');
    setMessage('Processing audio through complete workflow...');

    setVisualURL(null);
    setTamperSummary(null);
    setTamperSegments([]);
    setTamperStatus(null);

    const formData = new FormData();
    formData.append('audio_file', files.audio_file);
    if (files.reference_file) {
      console.log('📁 Reference file attached:', files.reference_file.name);
      formData.append('reference_file', files.reference_file);
    } else {
      console.log('ℹ️ No reference file provided');
    }
    formData.append('case_number', uploadForm.case_number);
    formData.append('device', uploadForm.device);
    formData.append('location', uploadForm.location);

    try {
      const { data } = await axios.post('/upload-audio', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      console.log('📥 Response received:', data);

      // DUPLICATE HANDLING
      if (data.duplicate) {
        setMessageType('duplicate');
        setMessage(
          `⚠️ Duplicate File Detected
- Case Number: ${data.case_number || 'N/A'}
- File Number: ${data.file_number || 'N/A'}
- Previously Analyzed By: ${data.previous_user || 'Unknown'}
- First Recorded At: ${data.previous_time || 'N/A'}
- Previous Decision: ${data.tamper_result?.result || 'N/A'} (${((data.tamper_result?.confidence || 0) * 100).toFixed(1)}% confidence)`
        );
        if (data.tamper_result?.visual_url) {
          setVisualURL(data.tamper_result.visual_url);
        }
        return;
      }

      if (data.success) {
        setUploadForm({ case_number: '', device: '', location: '' });
        setFiles({ audio_file: null, reference_file: null });
        await loadCases();

        // Determine message color by tamper result
        const status = data.tamper_result?.result || 'Unknown';
        if (status === 'Tampered') {
          setMessageType('tampered');
        } else {
          setMessageType('success'); // Authentic / other
        }

        // Build speaker verification message
        let speakerMessage = '';
        if (data.speaker_result) {
          console.log('✅ Speaker result found:', data.speaker_result);

          // Check if there was an error
          if (data.speaker_result.result === 'Error') {
            speakerMessage = `- Speaker Verification: Error (${data.speaker_result.error || 'Unknown error'})`;
          } else {
            speakerMessage = `- Speaker Verification: ${data.speaker_result.result} (${(data.speaker_result.overall_confidence * 100).toFixed(1)}% confidence, Score: ${data.speaker_result.similarity_score.toFixed(3)})`;
          }
        } else {
          console.log('ℹ️ No speaker result in response');
          speakerMessage = '- Speaker Verification: N/A (No reference audio provided)';
        }

        // Build message text
        setMessage(
          `✅ Processing Complete
- File Number: ${data.file_number}
- Comparison Status: ${data.comparison_status || 'N/A'}
- Verified By: ${data.verified_by || 'You'}
- Verified At: ${data.verified_at || new Date().toLocaleString()}
- Tamper Detection: ${data.tamper_result.result} (${(data.tamper_result.confidence * 100).toFixed(1)}% confidence)
${speakerMessage}`
        );

        if (data.tamper_result.visual_url) {
          setVisualURL(data.tamper_result.visual_url);
        }

        // Summary + segments
        if (data.tamper_result) {
          setTamperStatus(status);
          setTamperSummary({
            result: status,
            confidence: data.tamper_result.confidence,
            percentage: data.tamper_result.tamper_percentage,
            duration: data.tamper_result.duration,
          });

          if (status === 'Authentic') {
            setTamperSegments([]);
          } else {
            setTamperSegments(data.tamper_result.tamper_segments || []);
          }
        } else {
          setTamperStatus(null);
          setTamperSummary(null);
          setTamperSegments([]);
        }
      }
    } catch (error) {
      console.error('❌ Upload error:', error);
      setMessageType('error');
      setMessage(error.response?.data?.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const downloadReport = async (caseId, caseNumber, fileNumber) => {
    try {
      const res = await axios.get(`/generate-report/${caseId}`, {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute(
        'download',
        `Audio_Evidence_Report_${caseNumber}_${fileNumber}.pdf`,
      );
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch {
      alert('Failed to generate report');
    }
  };

  const renderMessageHeader = () => {
    if (messageType === 'tampered') return '🔴 Tampered Audio Detected';
    if (messageType === 'success') return '🟢 Audio Verified as Authentic';
    if (messageType === 'duplicate') return '⚠️ Duplicate Evidence Detected';
    if (messageType === 'error') return '❌ Error';
    return 'ℹ️ Status';
  };

  return (
    <div className="dashboard">
      <div className="sidebar">
        <h3>Officer Panel</h3>
        <nav>
          <button
            className={activeTab === 'dashboard' ? 'active' : ''}
            onClick={() => setActiveTab('dashboard')}
          >
            My Cases
          </button>
          <button
            className={activeTab === 'upload' ? 'active' : ''}
            onClick={() => setActiveTab('upload')}
          >
            Upload Audio
          </button>
          <button
            className={activeTab === 'profile' ? 'active' : ''}
            onClick={() => setActiveTab('profile')}
          >
            Profile
          </button>
        </nav>
      </div>

      <div className="main-content">
        {/* MY CASES TAB */}
        {activeTab === 'dashboard' && (
          <div>
            <h2>My Cases</h2>
            <div className="cases-table">
              <table>
                <thead>
                  <tr>
                    <th>Case No.</th>
                    <th>File No.</th>
                    <th>Status</th>
                    <th>Timestamp</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {cases.map((case_) => (
                    <tr key={case_._id}>
                      <td>{case_.case_number}</td>
                      <td>{case_.file_number}</td>
                      <td>
                        <span
                          className={`status ${case_.tamper_result?.result?.toLowerCase()}`}
                        >
                          {case_.tamper_result?.result || 'Processing'}
                        </span>
                      </td>
                      <td>{new Date(case_.created_at).toLocaleString()}</td>
                      <td>
                        <button
                          onClick={() =>
                            downloadReport(
                              case_._id,
                              case_.case_number,
                              case_.file_number,
                            )
                          }
                          className="download-btn"
                        >
                          Generate Report
                        </button>

                        {case_.tamper_result?.visual_url && (
                          <div className="case-visual-preview">
                            <img
                              src={`http://localhost:5000${case_.tamper_result.visual_url}`}
                              alt="Tamper visualization"
                              className="case-visual-thumb"
                            />
                            <a
                              href={`http://localhost:5000${case_.tamper_result.visual_url}`}
                              download
                              className="download-visual-btn"
                            >
                              ⬇️ Download Visualization
                            </a>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>

              </table>
            </div>
          </div>
        )}

        {/* UPLOAD TAB */}
        {activeTab === 'upload' && (
          <div>
            <h2>Upload Audio Evidence</h2>
            <form onSubmit={handleUpload} className="upload-form">
              <div className="form-group">
                <label>Case Number:</label>
                <input
                  type="text"
                  value={uploadForm.case_number}
                  onChange={(e) => {
                    const value = e.target.value;
                    if (/^\d*$/.test(value)) {
                      setUploadForm({ ...uploadForm, case_number: value });
                    }
                  }}
                  placeholder="Enter numeric case number"
                  required
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Recording Device:</label>
                  <input
                    type="text"
                    value={uploadForm.device}
                    onChange={(e) =>
                      setUploadForm({ ...uploadForm, device: e.target.value })
                    }
                    placeholder="e.g., iPhone 12, Sony IC Recorder"
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Location:</label>
                  <input
                    type="text"
                    value={uploadForm.location}
                    onChange={(e) =>
                      setUploadForm({
                        ...uploadForm,
                        location: e.target.value,
                      })
                    }
                    placeholder="e.g., 123 Main St, Interview Room A"
                    required
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Primary Audio File:</label>
                <input
                  type="file"
                  name="audio_file"
                  accept=".wav,.mp3,.m4a,.flac"
                  onChange={handleFileChange}
                  required
                />
                <small>Supported formats: WAV, MP3, M4A, FLAC</small>
              </div>

              <div className="form-group">
                <label>Reference Audio (Optional - for speaker verification):</label>
                <input
                  type="file"
                  name="reference_file"
                  accept=".wav,.mp3,.m4a,.flac"
                  onChange={handleFileChange}
                />
                <small>Upload a known voice sample for speaker verification</small>
              </div>

              {/* MAIN STATUS CARD */}
              {message && (
                <div className={`message ${messageType}`}>
                  <div className="message-header">
                    {renderMessageHeader()}
                  </div>
                  <pre>{message}</pre>
                </div>
              )}

              {/* Tamper analysis summary (separate from status card) */}
              {tamperSummary && (
                <div
                  className={`tamper-summary ${tamperStatus === 'Authentic' ? 'authentic' : 'tampered'
                    }`}
                >
                  <h4>
                    {tamperStatus === 'Authentic'
                      ? '🟢 Audio Verified as Authentic'
                      : '🔴 Potential Tampering Detected'}
                  </h4>
                  <p>
                    <strong>Model Decision:</strong> {tamperSummary.result}{' '}
                    ({(tamperSummary.confidence * 100).toFixed(1)}% confidence
                    {tamperStatus === 'Authentic'
                      ? ' — No editing signatures detected.'
                      : ''}
                    )
                  </p>

                  {tamperStatus !== 'Authentic' && (
                    <p>
                      <strong>Estimated Tampered Region:</strong>{' '}
                      {tamperSummary.percentage?.toFixed(2)}% of total audio
                    </p>
                  )}

                  <p>
                    <strong>Audio Duration Analyzed:</strong>{' '}
                    {tamperSummary.duration?.toFixed(2)} seconds
                  </p>

                  {tamperStatus === 'Authentic' && (
                    <p className="tamper-note">
                      No strong evidence of editing was detected. This result
                      should still be interpreted together with other case
                      evidence.
                    </p>
                  )}
                </div>
              )}

              {/* Waveform visualization */}
              {visualURL && (
                <div className="tamper-visualization">
                  <h4>🔍 Waveform Visualization</h4>
                  <img
                    src={`http://localhost:5000${visualURL}`}
                    alt="Tampering / waveform visualization"
                    className="visual-image"
                  />
                  <a
                    href={`http://localhost:5000${visualURL}`}
                    download
                    className="download-visual-btn"
                  >
                    ⬇️ Download Visualization
                  </a>
                </div>
              )}

              {/* Tampered segments only if Tampered */}
              {tamperStatus === 'Tampered' &&
                tamperSegments &&
                tamperSegments.length > 0 && (
                  <div className="tamper-details">
                    <h4>🔎 Detected Tampered Segments</h4>
                    <p className="tamper-note">
                      Showing up to the top 5 most suspicious regions
                      automatically highlighted by the forensic model.
                    </p>
                    <div className="tamper-card-grid">
                      {tamperSegments.map((seg, index) => (
                        <div key={index} className="tamper-card">
                          <div className="tamper-card-header">
                            <span className="tamper-tag">
                              {seg.tamper_type || 'Suspicious Region'}
                            </span>
                            <span className="tamper-time">
                              ⏱ {Number(seg.time).toFixed(2)} s
                            </span>
                          </div>
                          <p className="tamper-confidence">
                            Confidence:&nbsp;
                            <strong>
                              {(seg.confidence * 100).toFixed(1)}%
                            </strong>
                          </p>
                          <p className="tamper-explanation">
                            {seg.explanation}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

              <button type="submit" disabled={uploading} className="upload-btn">
                {uploading ? 'Processing Workflow...' : 'Upload & Process Audio'}
              </button>
            </form>

            <div className="workflow-info">
              <h3>Workflow Process:</h3>
              <ol>
                <li>Audio preprocessing (normalization, noise reduction)</li>
                <li>SHA-256 hash computation</li>
                <li>Blockchain evidence storage</li>
                <li>Tamper detection analysis</li>
                <li>Speaker verification (if reference provided)</li>
                <li>Blockchain results storage</li>
                <li>Report generation ready</li>
              </ol>
            </div>
          </div>
        )}

        {/* PROFILE TAB */}
        {activeTab === 'profile' && (
          <div>
            <h2>Profile</h2>
            <div className="profile-info">
              <p><strong>Username:</strong> {user.username}</p>
              <p><strong>Full Name:</strong> {user.full_name}</p>
              <p><strong>Role:</strong> {user.role}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------- MAIN APP ----------------
function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    localStorage.removeItem('token');
    localStorage.removeItem('userData');
    setUser(null);
    setLoading(false);
  }, []);

  const handleLogin = (userData) => {
    setUser(userData);
    localStorage.setItem('userData', JSON.stringify(userData));
  };

  const handleLogout = () => {
    setUser(null);
    localStorage.removeItem('token');
    localStorage.removeItem('userData');
  };

  if (loading) return <div className="loading">Loading...</div>;
  if (!user) return <Login onLogin={handleLogin} />;

  return (
    <div className="app">
      <header className="app-header">
        <h1>Audio Evidence Verification System</h1>
        <div className="user-info">
          <span>Welcome, {user.full_name}</span>
          <button onClick={handleLogout} className="logout-btn">
            Logout
          </button>
        </div>
      </header>
      {user.role === 'admin' ? (
        <AdminDashboard user={user} />
      ) : (
        <UserDashboard user={user} />

      )}
    </div>
  );
}

export default App;
