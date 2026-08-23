import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import PageShell from '../components/PageShell';
import AnimatedMentor from '../components/AnimatedMentor';
import Editor from '@monaco-editor/react';

import { evaluateCode } from '../api/codeEvaluation';
import { detectEmotionFrame } from '../api/emotion';

function getFastApiWsBaseUrl() {
  const configured = import.meta.env.VITE_FASTAPI_WS_BASE_URL || import.meta.env.VITE_FASTAPI_BASE_URL || 'http://localhost:8000';
  const withoutApi = configured.replace(/\/api$/, '');
  return withoutApi.replace(/^http/, 'ws').replace(/\/$/, '');
}

function buildTechnicalStarterCode(questionId, language = 'python') {
  if (language === 'javascript') {
    return `function longest_subarray_sum_k(arr, k) {
  // Write your solution here.
  return 0;
}

module.exports = { longest_subarray_sum_k };
`;
  }

  if (language === 'java') {
    return `class Solution {
  static int longest_subarray_sum_k(int[] arr, int k) {
    // Write your solution here.
    return 0;
  }
}
`;
  }

  if (questionId === 'tech_dsa_1') {
    return `def longest_subarray_sum_k(arr, k):
    """Return the maximum length of a contiguous subarray with sum equal to k."""
    # Write your solution here.
    pass
`;
  }

  return `def solve(*args):
    """Write your solution here."""
    pass
`;
}

export default function InterviewPage() {
  const { sessionId } = useParams();

  // Emotion analysis (privacy-first; optional, consent-gated)
  const [emotionFeatureEnabled, setEmotionFeatureEnabled] = useState(false); // UI toggle (disabled by default)
  const [emotionSamplingEnabled, setEmotionSamplingEnabled] = useState(false);

  const [emotionConsentOpen, setEmotionConsentOpen] = useState(false);
  const [emotionCamActive, setEmotionCamActive] = useState(false);


  const [emotionLastScore, setEmotionLastScore] = useState(null);
  const [emotionError, setEmotionError] = useState('');
  const [emotionLastSentAt, setEmotionLastSentAt] = useState(null);
  const [emotionHelpText, setEmotionHelpText] = useState('');

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const videoStreamRef = useRef(null);
  const emotionSamplerRef = useRef(null);



  const [wsState, setWsState] = useState({ status: 'connecting', error: '' });
  const [recState, setRecState] = useState({ recording: false, muted: false });
  const [micState, setMicState] = useState('not requested');
  const [recError, setRecError] = useState('');
  const [submittingRecording, setSubmittingRecording] = useState(false);
  const [interviewerQuestion, setInterviewerQuestion] = useState('');
  const [interviewerAudioUrl, setInterviewerAudioUrl] = useState(null);
  const [voiceTranscript, setVoiceTranscript] = useState('');
  const [voiceStats, setVoiceStats] = useState(null);
  const [responseScore, setResponseScore] = useState(null);

  const [sessionType, setSessionType] = useState('HR');
  const [activeQuestionId, setActiveQuestionId] = useState(null);
  const [activeTurnIndex, setActiveTurnIndex] = useState(null);

  const [codeLanguage, setCodeLanguage] = useState('python');
  const [code, setCode] = useState('');
  const [evalState, setEvalState] = useState({ running: false, result: null, error: '' });


  const wsRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const microphoneStreamRef = useRef(null);
  const chunksRef = useRef([]);
  const loadedTechnicalQuestionRef = useRef(null);
  const codeEditedRef = useRef(false);

  const isTechnicalRound = sessionType === 'Technical';

  useEffect(() => {
    if (!isTechnicalRound) {
      return;
    }

    const questionKey = activeQuestionId || 'generic-technical-question';
    if (loadedTechnicalQuestionRef.current === questionKey) {
      return;
    }

    loadedTechnicalQuestionRef.current = questionKey;
    codeEditedRef.current = false;
    setCode(buildTechnicalStarterCode(activeQuestionId, codeLanguage));
    setEvalState({ running: false, result: null, error: '' });
  }, [activeQuestionId, codeLanguage, isTechnicalRound]);

  useEffect(() => {
    if (isTechnicalRound && !code) {
      setCode(buildTechnicalStarterCode(activeQuestionId, codeLanguage));
    }
  }, [activeQuestionId, code, codeLanguage, isTechnicalRound]);

  useEffect(() => {
    // FastAPI WS is served on :8000 in docker-compose.
    const fastApiWsBase = getFastApiWsBaseUrl();
    const token = localStorage.getItem('interviewai_token');
    const authQuery = token ? `?token=${encodeURIComponent(token)}` : '';
    const url = `${fastApiWsBase}/ws/interview/${sessionId}${authQuery}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setWsState({ status: 'connected', error: '' });

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.mode) setSessionType(data.mode);
        if (typeof data.turnIndex === 'number') setActiveTurnIndex(data.turnIndex);
        if (data.questionId !== undefined) setActiveQuestionId(data.questionId || null);
        if (data.question) setInterviewerQuestion(data.question);
        if (data.transcript !== undefined) setVoiceTranscript(data.transcript || '');
        if (data.responseScore !== undefined) setResponseScore(data.responseScore || null);
        if (data.fillerWordCount !== undefined || data.wpm !== undefined || data.verbalConfidence !== undefined) {
          setVoiceStats({
            fillerWordCount: data.fillerWordCount ?? null,
            wpm: data.wpm ?? null,
            avgPauseLengthS: data.avgPauseLengthS ?? null,
            verbalConfidence: data.verbalConfidence ?? null,
            audioDurationMs: data.audioDurationMs ?? null,
          });
        }

        if (data.questionAudioB64) {
          const byteCharacters = atob(data.questionAudioB64);
          const byteNumbers = new Array(byteCharacters.length);
          for (let i = 0; i < byteCharacters.length; i++) byteNumbers[i] = byteCharacters.charCodeAt(i);
          const byteArray = new Uint8Array(byteNumbers);
          const blob = new Blob([byteArray], { type: data.questionAudioMimeType || 'audio/mpeg' });

          const objectUrl = URL.createObjectURL(blob);
          setInterviewerAudioUrl((currentUrl) => {
            if (currentUrl) URL.revokeObjectURL(currentUrl);
            return objectUrl;
          });

          const audio = new Audio(objectUrl);
          audio.onended = () => {
            URL.revokeObjectURL(objectUrl);
          };
          audio.play().catch(() => {});
        } else if (data.question && 'speechSynthesis' in window) {
          // Local development does not need a large server-side TTS model.
          // Use the browser voice when the API intentionally omits audio.
          window.speechSynthesis.cancel();
          window.speechSynthesis.speak(new SpeechSynthesisUtterance(data.question));
        }
      } catch (e) {}
    };

    ws.onerror = (err) => setWsState({ status: 'error', error: String(err?.message || err) });
    ws.onclose = (event) => {
      const reason = event?.reason ? ` (${event.reason})` : '';
      setWsState((s) => ({ ...s, status: 'closed', error: s.error || `Connection closed${reason}` }));
    };

    window.__interviewSocketDebug = { url, ws };

    return () => {
      ws.close();
      window.speechSynthesis?.cancel();
    };
  }, [sessionId]);

  useEffect(() => {
    return () => {
      if (interviewerAudioUrl) URL.revokeObjectURL(interviewerAudioUrl);
    };
  }, [interviewerAudioUrl]);

  const recordingStartTsRef = useRef(null);
  const isMutedRef = useRef(false);

  function audioBlobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(reader.error || new Error('Could not read the recording.'));
      reader.onloadend = () => {
        try {
          const bytes = new Uint8Array(reader.result);
          let binary = '';
          for (let i = 0; i < bytes.byteLength; i += 1) binary += String.fromCharCode(bytes[i]);
          resolve(btoa(binary));
        } catch (error) {
          reject(error);
        }
      };
      reader.readAsArrayBuffer(blob);
    });
  }

  function microphoneErrorMessage(error) {
    if (error?.name === 'NotAllowedError' || error?.name === 'SecurityError') {
      return 'Microphone access was blocked. Allow microphone access for localhost:5173, then try again.';
    }
    if (error?.name === 'NotFoundError') {
      return 'No microphone was found. Connect or select a microphone, then try again.';
    }
    if (error?.name === 'NotReadableError') {
      return 'Your microphone is in use by another app. Close that app and try again.';
    }
    return error?.message || 'Could not start microphone recording.';
  }

  async function startRecording() {
    if (recState.recording || submittingRecording) return;
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setRecError('The interview connection is not open. Refresh the page and try again.');
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setMicState('unavailable');
      setRecError('This browser does not support microphone recording. Use a current Chrome, Edge, or Firefox browser.');
      return;
    }

    setMicState('requesting permission');
    setRecError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        video: false,
      });
      const audioTrack = stream.getAudioTracks()[0];
      if (!audioTrack || !audioTrack.enabled) throw new Error('The browser did not provide an active microphone track.');

      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : undefined;
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      chunksRef.current = [];
      microphoneStreamRef.current = stream;
      recordingStartTsRef.current = Date.now();
      isMutedRef.current = false;

      recorder.ondataavailable = (event) => {
        if (event.data?.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onerror = (event) => {
        setRecError(event.error?.message || 'The microphone recorder encountered an error.');
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        microphoneStreamRef.current = null;
        mediaRecorderRef.current = null;
        setRecState({ recording: false, muted: false });

        try {
          if (chunksRef.current.length === 0) {
            throw new Error('No audio was captured. Check that your microphone is not muted and try again.');
          }
          if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            throw new Error('The interview connection closed before your answer could be sent.');
          }

          const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' });
          const audioB64 = await audioBlobToBase64(blob);
          const elapsedMs = recordingStartTsRef.current ? Date.now() - recordingStartTsRef.current : undefined;
          wsRef.current.send(JSON.stringify({ control: { action: 'start' } }));
          wsRef.current.send(JSON.stringify({ audio: { audio_b64: audioB64, chunk_start_ms: 0, chunk_end_ms: elapsedMs } }));
          wsRef.current.send(JSON.stringify({ control: { action: 'stop' } }));
          setMicState('granted');
        } catch (error) {
          setRecError(error?.message || 'Could not send the recording.');
        } finally {
          setSubmittingRecording(false);
        }
      };

      recorder.start();
      mediaRecorderRef.current = recorder;
      setMicState('granted');
      setRecState({ recording: true, muted: false });
    } catch (error) {
      setMicState('blocked or unavailable');
      setRecError(microphoneErrorMessage(error));
    }
  }

  function stopRecordingAndSend() {
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === 'inactive') return;
    setSubmittingRecording(true);
    recorder.stop();
  }

  async function toggleMute() {
    setRecState((s) => {
      const nextMuted = !s.muted;
      isMutedRef.current = nextMuted;
      microphoneStreamRef.current?.getAudioTracks().forEach((track) => {
        track.enabled = !nextMuted;
      });
      return { ...s, muted: nextMuted };
    });
  }

  const connectionStatus = wsState.status === 'connected' ? 'Live connection' : wsState.status;
  const questionNumber = typeof activeTurnIndex === 'number' ? activeTurnIndex + 1 : 1;


  return (
    <PageShell variant="interview">
      <div className="interview-workspace">
        <header className="interview-header">
          <div className="interview-brand">
            <span className="brand-mark">IA</span>
            <div>
              <span className="header-kicker">InterviewAI practice room</span>
              <h1>{sessionType} interview</h1>
            </div>
          </div>
          <div className="session-status-group">
            <span className={`status-pill status-${wsState.status}`}><i />{connectionStatus}</span>
            <span className="session-id">Session {sessionId.slice(-6)}</span>
          </div>
        </header>

        {wsState.error ? <div className="interview-alert">{wsState.error}</div> : null}

        <section className="interview-stage">
        <div className="prompt-card">
          <AnimatedMentor compact speaking={wsState.status === 'connected'} />
          <h2 style={{ marginTop: 0 }}>Interviewer · Question {questionNumber}</h2>
          <p>{interviewerQuestion || 'Waiting for the first question...'}</p>
          <div style={{ fontSize: 13, color: '#666' }}>
            Round: {sessionType} {activeQuestionId ? `· Question ${activeQuestionId}` : ''}
            {typeof activeTurnIndex === 'number' ? ` · Turn ${activeTurnIndex}` : ''}
          </div>
        </div>

        <div className={`answer-card ${recState.recording ? 'is-recording' : ''}`}>
          <h2 style={{ marginTop: 0 }}>You</h2>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {!recState.recording ? (
              <button onClick={startRecording} disabled={submittingRecording || wsState.status !== 'connected'}>
                {submittingRecording ? 'Sending answer...' : 'Start Recording'}
              </button>
            ) : (
              <>
                <button onClick={stopRecordingAndSend}>Stop & submit</button>
                <button onClick={toggleMute} style={{ opacity: recState.muted ? 1 : 0.85 }}>
                  {recState.muted ? 'Unmute' : 'Mute'}
                </button>
              </>
            )}
            <span>
              {submittingRecording
                ? 'Sending your answer...'
                : recState.recording
                ? recState.muted
                  ? 'Muted'
                  : 'Recording...'
                : 'Not recording'}
            </span>

          </div>
          <div style={{ marginTop: 8, fontSize: 13, color: micState === 'granted' ? '#286b2d' : '#666' }}>
            Microphone permission: {micState}
          </div>
          {recError ? <p style={{ color: 'red', marginBottom: 0 }}>{recError}</p> : null}
          <div style={{ marginTop: 10, fontSize: 13, color: '#444' }}>
            <div><b>Last transcript:</b> {voiceTranscript || 'Waiting for your spoken answer...'}</div>
            {voiceStats ? (
              <div style={{ marginTop: 6 }}>
                <b>Speech stats:</b>{' '}
                filler words {voiceStats.fillerWordCount ?? '—'},
                {' '}WPM {voiceStats.wpm ? voiceStats.wpm.toFixed(1) : '—'},
                {' '}confidence {voiceStats.verbalConfidence ?? '—'}
              </div>
            ) : null}
            {responseScore ? (
              <div style={{ marginTop: 8, padding: 8, borderRadius: 6, background: '#f4f8ff' }}>
                <b>Response score: {responseScore.overall}/100</b>
                {' '}· Relevance {responseScore.relevance}/100
                {' '}· Depth {responseScore.depth}/100
                {' '}· Structure {responseScore.structure}/100
                {responseScore.feedback ? <div style={{ marginTop: 4 }}>{responseScore.feedback}</div> : null}
              </div>
            ) : null}
          </div>
        </div>

        </section>

        {/* Technical live coding (shown only during Technical rounds) */}
        {isTechnicalRound ? (
          <div className="technical-panel" style={{ border: '1px solid #ddd', padding: 12, borderRadius: 8 }}>
            <h2 style={{ marginTop: 0 }}>Technical Coding</h2>

            <div style={{ marginBottom: 12, padding: 12, borderRadius: 8, background: '#fafafa', border: '1px solid #eee' }}>
              <div style={{ fontWeight: 700 }}>Problem statement</div>
              <div style={{ marginTop: 6, whiteSpace: 'pre-wrap', color: '#333' }}>
                {interviewerQuestion || 'Waiting for the coding prompt...'}
              </div>
              <div style={{ marginTop: 6, fontSize: 12, color: '#666' }}>
                Use the function stub below, run against hidden tests, and iterate before submitting.
              </div>
            </div>

            <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 10, flexWrap: 'wrap' }}>
              <label>
                <span style={{ display: 'block', fontSize: 12, color: '#666' }}>Language</span>
                <select value={codeLanguage} onChange={(event) => setCodeLanguage(event.target.value)}>
                  <option value="python">Python</option>
                  <option value="javascript">JavaScript</option>
                  <option value="java">Java</option>
                </select>
              </label>

              <button
                type="button"
                onClick={() => {
                  setCode(buildTechnicalStarterCode(activeQuestionId, codeLanguage));
                  setEvalState({ running: false, result: null, error: '' });
                  codeEditedRef.current = false;
                }}
              >
                Reset starter
              </button>

              <button
                disabled={evalState.running || !isTechnicalRound || !activeQuestionId}
                onClick={async () => {
                  if (!activeQuestionId) return;
                  const payload = {
                    session_id: sessionId,
                    question_id: activeQuestionId || 'unknown',
                    language: codeLanguage,
                    code,
                    turnIndex: activeTurnIndex,
                  };

                  setEvalState({ running: true, result: null, error: '' });
                  try {
                    const res = await evaluateCode(payload);
                    setEvalState({ running: false, result: res, error: '' });
                  } catch (e) {
                    setEvalState({ running: false, result: null, error: String(e?.message || e) });
                  }
                }}
              >
                {evalState.running ? 'Running...' : 'Run'}
              </button>

              <span style={{ color: evalState.error ? 'red' : undefined }}>{evalState.error}</span>
            </div>

            <div style={{ height: 320, border: '1px solid #eee', borderRadius: 6, overflow: 'hidden' }}>
              <Editor
                height="320px"
                defaultLanguage={codeLanguage}
                language={codeLanguage}
                value={code}
                onChange={(v) => {
                  codeEditedRef.current = true;
                  setCode(v ?? '');
                }}
                theme="vs-light"
                options={{ minimap: { enabled: false }, fontSize: 13, wordWrap: 'on' }}
              />
            </div>

            <div style={{ marginTop: 12 }}>
              <h3 style={{ marginTop: 0 }}>Output</h3>
              {evalState.result ? (
                <div style={{ border: '1px solid #eee', padding: 10, borderRadius: 6 }}>
                  <div>
                    Verdict:{' '}
                    <b style={{ color: evalState.result.passed ? 'green' : 'red' }}>
                      {evalState.result.passed ? 'PASS' : 'FAIL'}
                    </b>
                  </div>
                  <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', marginTop: 8 }}>
                    {`stdout:\n${evalState.result.stdout || ''}\n\nstderr:\n${evalState.result.stderr || ''}`}
                  </pre>
                  {evalState.result.aiReview ? (
                    <div style={{ marginTop: 10 }}>
                      <b>AI Review</b>
                      <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{evalState.result.aiReview}</pre>
                    </div>
                  ) : null}
                </div>
              ) : (
                <div style={{ color: '#666' }}>
                  Run the code to see stdout/stderr and AI review.
                </div>
              )}
            </div>
          </div>
        ) : null}

        {/* Optional live emotion analysis indicator */}
        <div style={{ display: emotionFeatureEnabled ? 'block' : 'none', border: '1px dashed #bbb', padding: 10, borderRadius: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
            <div>
              <b>Emotion analysis:</b> {emotionCamActive ? 'Active' : 'Idle'}
              {emotionLastSentAt ? (
                <span style={{ marginLeft: 8, color: '#666' }}>
                  last update: {new Date(emotionLastSentAt).toLocaleTimeString()}
                </span>
              ) : null}
            </div>
            {emotionLastScore ? (
              <span style={{ fontSize: 12, color: '#666' }}>
                engaged {emotionLastScore.engaged?.toFixed?.(2) ?? ''}
              </span>
            ) : null}
          </div>
          {emotionError ? <p style={{ color: 'red', margin: '6px 0 0' }}>{emotionError}</p> : null}
        </div>

        {interviewerAudioUrl ? (
          <div>
            <p>Playing audio...</p>
          </div>
        ) : null}
      </div>

      {/* Consent modal + camera control */}
      {emotionConsentOpen ? (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 999 }}>
          <div style={{ width: 520, background: '#fff', borderRadius: 12, padding: 16, boxShadow: '0 8px 30px rgba(0,0,0,0.25)' }}>
            <h3 style={{ marginTop: 0 }}>Camera consent</h3>
            <p>
              This interview uses your camera to analyze expressions for feedback purposes. Video is not stored, only periodic frame analysis.
            </p>
            <div style={{ fontSize: 12, color: '#666' }}>
              Emotion analysis is optional and can be disabled at any time.
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 14 }}>
              <button
                onClick={() => {
                  setEmotionConsentOpen(false);
                  setEmotionFeatureEnabled(false);
                }}
              >
                Not now
              </button>
              <button
                onClick={async () => {
                  setEmotionConsentOpen(false);
                  try {
                    setEmotionFeatureEnabled(true);
                    setEmotionError('');
                    setEmotionHelpText('');
                    // activate camera after consent
                    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
                    videoStreamRef.current = stream;
                    setEmotionCamActive(true);
                    if (videoRef.current) {
                      videoRef.current.srcObject = stream;
                      await videoRef.current.play();
                    }

                    // Start sampler: 1 frame every 3-5 seconds. (use 4000ms)
                    if (emotionSamplerRef.current) clearInterval(emotionSamplerRef.current);
                    emotionSamplerRef.current = setInterval(async () => {
                      try {
                        if (!videoRef.current) return;
                        const video = videoRef.current;
                        if (video.readyState < 2) return;

                        const canvas = canvasRef.current;
                        if (!canvas) return;
                        canvas.width = video.videoWidth || 640;
                        canvas.height = video.videoHeight || 480;

                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

                        const dataUrl = canvas.toDataURL('image/jpeg', 0.7);
                        const base64 = dataUrl.split(',')[1];

                        // Associate with latest turn index (best effort)
                        const turnIndex = activeTurnIndex;

                        const res = await detectEmotionFrame({
                          session_id: sessionId,
                          frame_jpeg_b64: base64,
                          turn_index: turnIndex,
                          timestamp_ms: Date.now(),
                        });

                        // store lightweight display
                        setEmotionLastScore(res?.scores || null);
                        setEmotionLastSentAt(Date.now());
                        setEmotionError('');
                      } catch (e) {
                        setEmotionError(String(e?.message || e));
                      }
                    }, 4000);
                  } catch (e) {
                    const message = String(e?.message || e || 'Unknown camera error');
                    const normalized = message.toLowerCase();
                    let help = 'Enable camera access in your browser and make sure a webcam is connected.';
                    if (normalized.includes('not found') || normalized.includes('device')) {
                      help = 'No camera was detected. Plug in a webcam or allow camera access in your browser settings.';
                    } else if (normalized.includes('permission') || normalized.includes('denied')) {
                      help = 'Camera access was blocked. Please allow camera permissions for this site and try again.';
                    } else if (normalized.includes('insecure context')) {
                      help = 'Camera access requires a secure connection. Use HTTPS or localhost.';
                    }
                    setEmotionError(message);
                    setEmotionHelpText(help);
                    setEmotionFeatureEnabled(false);
                    setEmotionCamActive(false);
                  }
                }}
              >
                I agree
              </button>
            </div>

            {/* Hidden video/canvas for frame capture */}
            <video ref={videoRef} style={{ display: 'none' }} playsInline muted />
            <canvas ref={canvasRef} style={{ display: 'none' }} />
          </div>
        </div>
      ) : null}

      {/* Feature toggle (disabled by default; no camera unless consent is accepted) */}
      <div style={{ marginTop: 12, border: '1px solid #ddd', padding: 12, borderRadius: 8 }}>
        <h3 style={{ marginTop: 0 }}>Facial emotion feedback (optional)</h3>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <label style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <input
              type="checkbox"
              checked={emotionFeatureEnabled}
              onChange={(e) => {
                const next = e.target.checked;
                if (!next) {
                  setEmotionFeatureEnabled(false);
                  setEmotionCamActive(false);
                  if (emotionSamplerRef.current) {
                    clearInterval(emotionSamplerRef.current);
                    emotionSamplerRef.current = null;
                  }
                  if (videoStreamRef.current) {
                    videoStreamRef.current.getTracks().forEach((t) => t.stop());
                    videoStreamRef.current = null;
                  }
                } else {
                  // Show explicit consent screen before activating camera.
                  setEmotionConsentOpen(true);
                }
              }}
            />
            Enable camera-based expression analysis
          </label>

          {emotionCamActive ? (
            <button
              onClick={() => {
                setEmotionFeatureEnabled(false);
                setEmotionCamActive(false);
                if (emotionSamplerRef.current) {
                  clearInterval(emotionSamplerRef.current);
                  emotionSamplerRef.current = null;
                }
                if (videoStreamRef.current) {
                  videoStreamRef.current.getTracks().forEach((t) => t.stop());
                  videoStreamRef.current = null;
                }
              }}
            >
              Disable
            </button>
          ) : null}
        </div>
        {emotionError ? <p style={{ color: 'red', marginBottom: 0 }}>{emotionError}</p> : null}
        {emotionHelpText ? <p style={{ color: '#666', margin: '4px 0 0' }}>{emotionHelpText}</p> : null}
      </div>

      {/* Hidden video/canvas for capture (only becomes active after consent) */}
      <video ref={videoRef} style={{ display: 'none' }} playsInline muted />
      <canvas ref={canvasRef} style={{ display: 'none' }} />

    </PageShell>
  );
}


