import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import PageShell from '../components/PageShell';
import { login, persistAuthSession } from '../api/auth';

export default function LoginPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: '', password: '' });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [touched, setTouched] = useState({ email: false, password: false });

  function handleBlur(field) {
    setTouched({ ...touched, [field]: true });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setIsSubmitting(true);
    setError('');

    try {
      const response = await login(form);
      persistAuthSession(response);
      navigate('/dashboard');
    } catch (submissionError) {
      setError(submissionError.message || 'An error occurred. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  }

  const emailError = touched.email && !form.email ? 'Email is required' : '';
  const passwordError = touched.password && !form.password ? 'Password is required' : '';

  return (
    <PageShell
      eyebrow="Authentication"
      title="Log in to InterviewAI"
      description="Sign in with the email and password you used during signup."
    >
      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        <label htmlFor="email">
          Email
          <input
            id="email"
            type="email"
            value={form.email}
            onChange={(event) => setForm({ ...form, email: event.target.value })}
            onBlur={() => handleBlur('email')}
            autoComplete="email"
            aria-describedby={emailError ? 'email-error' : undefined}
            required
          />
          {emailError && <p id="email-error" className="form-error">{emailError}</p>}
        </label>
        <label htmlFor="password">
          Password
          <input
            id="password"
            type="password"
            value={form.password}
            onChange={(event) => setForm({ ...form, password: event.target.value })}
            onBlur={() => handleBlur('password')}
            autoComplete="current-password"
            aria-describedby={passwordError ? 'password-error' : undefined}
            required
          />
          {passwordError && <p id="password-error" className="form-error">{passwordError}</p>}
        </label>
        {error ? <p className="form-error" role="alert">{error}</p> : null}
        <button className="button-link" type="submit" disabled={isSubmitting} aria-busy={isSubmitting}>
          {isSubmitting ? 'Signing in...' : 'Sign in'}
        </button>
        <p className="form-footnote">
          New here? <Link to="/signup">Create an account</Link>
        </p>
      </form>
    </PageShell>
  );
}
