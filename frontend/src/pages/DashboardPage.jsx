import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { apiRequest } from '../api/client';
import { clearAuthSession } from '../api/auth';
import { startInterviewSession } from '../api/interviews';
import { uploadResume } from '../api/resume';
import PageShell from '../components/PageShell';

export default function DashboardPage() {
  const navigate = useNavigate();
  const [authState, setAuthState] = useState({ token: null, user: null });
  const [resumeFile, setResumeFile] = useState(null);
  const [resumeUploadState, setResumeUploadState] = useState({ loading: false, error: '', success: '' });
  const [sessionState, setSessionState] = useState({ loading: false, error: '' });
  const [interviewType, setInterviewType] = useState('HR');
  const [targetRole, setTargetRole] = useState('SDE');

  const roleOptions = useMemo(() => ['SDE', 'Data Analyst', 'Product Manager', 'QA Engineer'], []);

  useEffect(() => {
    let isMounted = true;

    async function loadCurrentUser() {
      const token = localStorage.getItem('interviewai_token');
      const userJson = localStorage.getItem('interviewai_user');
      let cachedUser = null;

      if (userJson) {
        try {
          cachedUser = JSON.parse(userJson);
        } catch (parseError) {
          cachedUser = null;
        }
      }

      if (!token) {
        if (isMounted) {
          setAuthState({ token: null, user: null });
        }
        return;
      }

      try {
        const response = await apiRequest('/users/me');
        if (isMounted) {
          setAuthState({ token, user: response.user });
          localStorage.setItem('interviewai_user', JSON.stringify(response.user));
        }
      } catch (error) {
        if (isMounted) {
          if (error.status === 401) {
            clearAuthSession();
            setAuthState({ token: null, user: null });
            return;
          }

          setAuthState({
            token,
            user: cachedUser,
          });
        }
      }
    }

    loadCurrentUser();

    return () => {
      isMounted = false;
    };
  }, []);

  function handleLogout() {
    clearAuthSession();
    setAuthState({ token: null, user: null });
    navigate('/login');
  }

  async function handleUploadResume(event) {
    event.preventDefault();
    setResumeUploadState({ loading: true, error: '', success: '' });

    if (!resumeFile) {
      setResumeUploadState({ loading: false, error: 'Choose a PDF or DOCX file first.', success: '' });
      return;
    }

    try {
      const response = await uploadResume(resumeFile);
      setAuthState((current) => ({
        ...current,
        user: response.user,
      }));
      localStorage.setItem('interviewai_user', JSON.stringify(response.user));
      setResumeUploadState({ loading: false, error: '', success: 'Resume uploaded successfully.' });
    } catch (error) {
      if (error.status === 401) {
        clearAuthSession();
        setAuthState({ token: null, user: null });
        setResumeUploadState({
          loading: false,
          error: 'Your session expired. Please log in again, then upload the resume.',
          success: '',
        });
        return;
      }

      setResumeUploadState({ loading: false, error: error.message, success: '' });
    }
  }

  async function handleStartInterview() {
    setSessionState({ loading: true, error: '' });

    try {
      const response = await startInterviewSession({
        type: interviewType,
        targetRole,
      });

      navigate(`/interview/${response.sessionId}`);
    } catch (error) {
      setSessionState({ loading: false, error: error.message });
      return;
    }

    setSessionState({ loading: false, error: '' });
  }

  const isAuthenticated = Boolean(authState.token && authState.user);

  return (
    <PageShell
      eyebrow="Workspace"
      title={isAuthenticated ? 'Candidate dashboard' : 'Welcome to InterviewAI'}
      description={
        isAuthenticated
          ? 'The central hub for interview sessions, reports, and profile data.'
          : 'Sign in or create an account to manage interview sessions and reports.'
      }
    >
      <section className="dashboard-profile">
        {isAuthenticated ? (
          <div>
            <p className="eyebrow">Signed in as</p>
            <h2>{authState.user.name}</h2>
            <p>{authState.user.email}</p>
          </div>
        ) : (
          <div>
            <p className="eyebrow">Guest view</p>
            <h2>You are not signed in</h2>
            <p>Log in to upload a resume and start an interview session.</p>
          </div>
        )}

        <div className="route-links">
          {isAuthenticated ? (
            <button 
              className="button-link" 
              type="button" 
              onClick={handleLogout}
              aria-label={`Log out from ${authState.user?.name}'s account`}
            >
              Log out
            </button>
          ) : (
            <>
              <Link className="button-link" to="/login">
                Log in
              </Link>
              <Link className="button-link" to="/signup">
                Sign up
              </Link>
            </>
          )}
        </div>
      </section>

      {!isAuthenticated ? (
        <p className="form-footnote">
          The cards below are visible for the full flow, but uploading and starting an interview require a signed-in account.
        </p>
      ) : null}

      <section className="dashboard-grid">
        <article className="dashboard-card">
          <h2>Resume upload</h2>
          <p>Upload a PDF or DOCX resume so the backend can store the file URL and parse it later.</p>
          <form className="dashboard-form" onSubmit={handleUploadResume}>
            <label htmlFor="resume-file">
              Choose file
              <input
                id="resume-file"
                type="file"
                accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={(event) => setResumeFile(event.target.files?.[0] || null)}
                disabled={!isAuthenticated}
                aria-describedby={resumeUploadState.error ? 'resume-error' : undefined}
              />
            </label>
            {!isAuthenticated ? (
              <p className="form-footnote">Log in to upload and store a resume on your profile.</p>
            ) : null}
            {resumeUploadState.error ? <p id="resume-error" className="form-error">{resumeUploadState.error}</p> : null}
            {resumeUploadState.success ? <p className="form-success">{resumeUploadState.success}</p> : null}
            <button 
              className="button-link" 
              type="submit" 
              disabled={resumeUploadState.loading || !isAuthenticated || !resumeFile}
              aria-busy={resumeUploadState.loading}
            >
              {resumeUploadState.loading ? 'Uploading...' : 'Upload resume'}
            </button>
          </form>
          {isAuthenticated && authState.user?.resumeUrl ? (
            <p className="form-footnote">
              ✓ Current resume: <a href={authState.user.resumeUrl} target="_blank" rel="noreferrer">View document</a>
            </p>
          ) : (
            <p className="form-footnote">No resume uploaded yet.</p>
          )}
        </article>

        <article className="dashboard-card">
          <h2>Start interview</h2>
          <p>Choose the interview type and target role, then start a new session.</p>
          <div className="dashboard-form">
            <label htmlFor="interview-type">
              Interview type
              <select 
                id="interview-type"
                value={interviewType} 
                onChange={(event) => setInterviewType(event.target.value)} 
                disabled={!isAuthenticated}
              >
                <option value="HR">HR Interview</option>
                <option value="Technical">Technical Interview</option>
              </select>
            </label>
            <label htmlFor="target-role">
              Target role
              <select 
                id="target-role"
                value={targetRole} 
                onChange={(event) => setTargetRole(event.target.value)} 
                disabled={!isAuthenticated}
              >
                {roleOptions.map((role) => (
                  <option key={role} value={role}>
                    {role}
                  </option>
                ))}
              </select>
            </label>
            {!isAuthenticated ? (
              <p className="form-footnote">Log in to start an interview session.</p>
            ) : null}
            {sessionState.error ? <p className="form-error" role="alert">{sessionState.error}</p> : null}
            <button 
              className="button-link" 
              type="button" 
              onClick={handleStartInterview} 
              disabled={sessionState.loading || !isAuthenticated}
              aria-busy={sessionState.loading}
            >
              {sessionState.loading ? 'Starting session...' : 'Start Interview'}
            </button>
          </div>
        </article>
      </section>

      <div className="placeholder-grid two-column">
        <article>
          <h2>Active sessions</h2>
          <p>Show current and historical interview sessions here.</p>
        </article>
        <article>
          <h2>Recent reports</h2>
          <p>Summaries and weakness analysis will surface from MongoDB reports.</p>
        </article>
      </div>
    </PageShell>
  );
}
