import AnimatedMentor from './AnimatedMentor';

export default function PageShell({ eyebrow, title, description, children, variant = 'default' }) {
  if (variant === 'interview') {
    return <main className="interview-page-shell">{children}</main>;
  }

  return (
    <main className="page-shell">
      <section className="hero-card">
        <div className="hero-copy">
          <p className="eyebrow"><span className="eyebrow-dot" />{eyebrow}</p>
          <h1>{title}</h1>
          <p className="lead">{description}</p>
          <div className="hero-trust">
            <span>Practice privately</span>
            <span>Get specific feedback</span>
          </div>
        </div>
        <div className="hero-panel">
          <AnimatedMentor />
          <div className="hero-panel-copy">
            <span className="panel-label">Your practice guide</span>
            <strong>Sharper answers.<br />Stronger interviews.</strong>
            <p>Structured practice, voice feedback, and clear next steps.</p>
          </div>
        </div>
      </section>
      <section className="content-card">{children}</section>
    </main>
  );
}
