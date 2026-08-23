import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import PageShell from '../components/PageShell';
import { persistAuthSession, signup } from '../api/auth';

export default function SignupPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: '', email: '', password: '', resumeUrl: '' });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [touched, setTouched] = useState({ name: false, email: false, password: false });

  function handleBlur(field) {
    setTouched({ ...touched, [field]: true });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setIsSubmitting(true);
    setError('');

    // Validate form
    if (!form.name.trim()) {
      setError('Full name is required');
      setIsSubmitting(false);
      return;
    }
    if (!form.email.trim()) {
      setError('Email is required');
      setIsSubmitting(false);
      return;
    }
    if (form.password.length < 6) {
      setError('Password must be at least 6 characters');
      setIsSubmitting(false);
      return;
    }

    try {
      const response = await signup(form);
      persistAuthSession(response);
      navigate('/dashboard');
    } catch (submissionError) {
      setError(submissionError.message || 'An error occurred. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  }

  const nameError = touched.name && !form.name.trim() ? 'Full name is required' : '';
  const emailError = touched.email && !form.email.trim() ? 'Email is required' : '';
  const passwordError = touched.password && form.password.length < 6 ? 'Password must be at least 6 characters' : '';

  return (
    <PageShell
      eyebrow="Authentication"
      title="Create a candidate account"
      description="Create your profile first, then log in with the same email and password."
    >
      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        <label htmlFor="name">
          Full name
          <input
            id="name"
            type="text"
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
            onBlur={() => handleBlur('name')}
            autoComplete="name"
            aria-describedby={nameError ? 'name-error' : undefined}
            required
          />
          {nameError && <p id="name-error" className="form-error">{nameError}</p>}
        </label>
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
            autoComplete="new-password"
            aria-describedby={passwordError ? 'password-error' : undefined}
            required
          />
          {passwordError && <p id="password-error" className="form-error">{passwordError}</p>}
        </label>
        <label htmlFor="resumeUrl">
          Resume URL (optional)
          <input
            id="resumeUrl"
            type="url"
            value={form.resumeUrl}
            onChange={(event) => setForm({ ...form, resumeUrl: event.target.value })}
            placeholder="https://..."
          />
        </label>
        {error ? <p className="form-error" role="alert">{error}</p> : null}
        <button className="button-link" type="submit" disabled={isSubmitting} aria-busy={isSubmitting}>
          {isSubmitting ? 'Creating account...' : 'Create account'}
        </button>
        <p className="form-footnote">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </form>
    </PageShell>
  );
}
