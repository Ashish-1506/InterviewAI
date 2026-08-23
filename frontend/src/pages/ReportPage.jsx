import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import PageShell from '../components/PageShell';
import { getFinalScoringReport } from '../api/scoring';
import { getEmotionReport } from '../api/emotion';


function EmotionChart({ series, categories }) {
  // Minimal SVG chart: multiple lines, no external deps.
  const seriesValues = Object.values(series || {});
  const maxLen = seriesValues.length ? Math.max(...seriesValues.map((v) => v.length), 1) : 1;
  const w = 720;
  const h = 260;
  const pad = 28;

  const xs = Array.from({ length: maxLen }, (_, i) => i);

  const yFor = (val) => {
    const clamped = Math.max(0, Math.min(1, val));
    return pad + (1 - clamped) * (h - pad * 2);
  };

  const xFor = (i) => {
    if (maxLen <= 1) return pad;
    return pad + (i / (maxLen - 1)) * (w - pad * 2);
  };

  const gridLines = [0, 0.25, 0.5, 0.75, 1];

  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 260 }}>
      {!seriesValues.length ? (
        <text x={w / 2} y={h / 2} fontSize={14} fill="#888" textAnchor="middle">
          No emotion samples yet
        </text>
      ) : null}

      {/* grid */}
      {gridLines.map((g) => {
        const y = yFor(g);
        return (
          <g key={g}>
            <line x1={pad} x2={w - pad} y1={y} y2={y} stroke="#eee" />
            <text x={pad - 8} y={y + 4} fontSize={10} fill="#888" textAnchor="end">
              {g.toFixed(2)}
            </text>
          </g>
        );
      })}

      {/* lines */}
      {categories.map((cat) => {
        const colorMap = {
          confident: '#2d8cff',
          engaged: '#19c37d',
          neutral: '#9aa3ad',
          nervous: '#ff7a59',
          confused: '#8e5bff',
        };
        const values = series?.[cat] || [];
        const pts = xs
          .map((i) => {
            const v = values[i] ?? null;
            if (v === null) return null;
            return `${xFor(i)},${yFor(v)}`;
          })
          .filter(Boolean);

        if (!pts.length) return null;

        return (
          <polyline
            key={cat}
            points={pts.join(' ')}
            fill="none"
            stroke={colorMap[cat] || '#333'}
            strokeWidth={2}
          />
        );
      })}

      {/* legend */}
      {categories.map((cat, idx) => {
        const colorMap = {
          confident: '#2d8cff',
          engaged: '#19c37d',
          neutral: '#9aa3ad',
          nervous: '#ff7a59',
          confused: '#8e5bff',
        };
        const x = pad + idx * 150;
        return (
          <g key={cat} transform={`translate(${x},${h - 14})`}>
            <circle cx={0} cy={0} r={4} fill={colorMap[cat] || '#333'} />
            <text x={8} y={4} fontSize={11} fill="#333">
              {cat}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export default function ReportPage() {
  const { sessionId } = useParams();

  const [report, setReport] = useState(null);
  const [emotionReport, setEmotionReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [emotionLoading, setEmotionLoading] = useState(true);
  const [error, setError] = useState('');
  const [emotionError, setEmotionError] = useState('');

  useEffect(() => {
    let cancelled = false;
    async function run() {
      setLoading(true);
      setError('');
      try {
        const res = await getFinalScoringReport(sessionId);

        if (!cancelled) setReport(res);
      } catch (e) {
        if (!cancelled) setError(String(e?.message || e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    run();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  useEffect(() => {
    let cancelled = false;

    async function runEmotion() {
      setEmotionLoading(true);
      setEmotionError('');

      try {
        const res = await getEmotionReport(sessionId);
        if (!cancelled) setEmotionReport(res);
      } catch (e) {
        if (!cancelled) {
          setEmotionReport(null);
          setEmotionError(String(e?.message || e));
        }
      } finally {
        if (!cancelled) setEmotionLoading(false);
      }
    }

    runEmotion();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const categories = useMemo(
    () => ['communication', 'technical_depth', 'confidence', 'problem_solving'],
    []
  );

  const categoryScores = report?.category_scores || null;
  const questionBreakdown = report?.question_breakdown || [];
  const strengths = report?.strengths || [];
  const weaknesses = report?.weaknesses || [];
  const emotionChartSeries = emotionReport?.chart_series || null;
  const emotionSummary = emotionReport?.session_summary || null;
  const emotionTurns = emotionReport?.aggregated_by_turn || [];

  const overallScore = report?.overall_score_0_to_100 ?? 0;
  const emotionCategories = useMemo(
    () => ['confident', 'engaged', 'neutral', 'nervous', 'confused'],
    []
  );

  function renderEmotionTrendLabel(turn) {
    const parts = [];
    const avg = turn?.averages || {};
    const trend = turn?.trend || {};

    if (typeof avg.confident === 'number') parts.push(`confidence ${(avg.confident * 100).toFixed(0)}%`);
    if (typeof avg.engaged === 'number') parts.push(`engagement ${(avg.engaged * 100).toFixed(0)}%`);
    if (typeof avg.nervous === 'number') parts.push(`nervousness ${(avg.nervous * 100).toFixed(0)}%`);

    const delta = trend.confidentDelta ?? trend.engagedDelta ?? trend.nervousDelta;
    if (typeof delta === 'number') {
      const sign = delta >= 0 ? '+' : '';
      parts.push(`trend ${sign}${(delta * 100).toFixed(0)} pts`);
    }

    return parts.join(' · ');
  }

  return (
    <PageShell
      eyebrow="Report"
      title={`Report for ${sessionId}`}
      description="Post-interview scoring report: overall + category subscores + evidence-backed strengths/weaknesses."
    >

      {loading ? <p>Loading report...</p> : null}
      {error ? <p style={{ color: 'red' }}>{error}</p> : null}

      {!loading && !error ? (
        <div style={{ display: 'grid', gap: 14 }}>
          <div style={{ border: '1px solid #eee', padding: 14, borderRadius: 8 }}>
            <h3 style={{ marginTop: 0 }}>Overall score</h3>
            <div style={{ display: 'flex', gap: 12, alignItems: 'baseline', flexWrap: 'wrap' }}>
              <div style={{ fontSize: 40, fontWeight: 800 }}>{overallScore.toFixed(1)}</div>
              <div style={{ color: '#666' }}>
                / 100
                <div style={{ marginTop: 6, fontSize: 13 }}>
                  Weights used: {report?.weights_used ? JSON.stringify(report.weights_used) : '—'}
                </div>
              </div>
            </div>
          </div>

          <div style={{ border: '1px solid #eee', padding: 14, borderRadius: 8 }}>
            <h3 style={{ marginTop: 0 }}>Category subscores (0-10)</h3>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              {categories.map((c) => (
                <div key={c} style={{ minWidth: 180, border: '1px solid #f0f0f0', padding: 10, borderRadius: 8 }}>
                  <div style={{ fontSize: 12, color: '#777' }}>{c}</div>
                  <div style={{ fontWeight: 800, fontSize: 22 }}>{(categoryScores?.[c] ?? 0).toFixed(1)}</div>
                </div>
              ))}
            </div>
          </div>

          <div style={{ border: '1px solid #eee', padding: 14, borderRadius: 8 }}>
            <h3 style={{ marginTop: 0 }}>Emotion trends</h3>
            {emotionLoading ? <p>Loading emotion analysis...</p> : null}
            {!emotionLoading && emotionError ? <p style={{ color: '#666' }}>{emotionError}</p> : null}
            {!emotionLoading && !emotionError && emotionReport ? (
              <>
                <EmotionChart series={emotionChartSeries || {}} categories={emotionCategories} />
                <div style={{ marginTop: 10, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  <div style={{ minWidth: 180, border: '1px solid #f5f5f5', padding: 10, borderRadius: 8 }}>
                    <div style={{ fontSize: 12, color: '#777' }}>Dominant signals</div>
                    <div style={{ fontWeight: 700 }}>
                      {(emotionSummary?.dominant || []).join(', ') || 'No clear dominant signal'}
                    </div>
                  </div>
                  <div style={{ minWidth: 220, border: '1px solid #f5f5f5', padding: 10, borderRadius: 8 }}>
                    <div style={{ fontSize: 12, color: '#777' }}>Overall observation</div>
                    <div style={{ fontWeight: 700 }}>
                      Trends only, not a diagnosis. Raw frames were discarded after analysis.
                    </div>
                  </div>
                </div>

                {emotionSummary?.notable_shifts?.length ? (
                  <div style={{ marginTop: 12 }}>
                    <div style={{ fontWeight: 800, marginBottom: 8 }}>Notable shifts</div>
                    <ul style={{ marginTop: 0, paddingLeft: 18 }}>
                      {emotionSummary.notable_shifts.map((shift, index) => (
                        <li key={index} style={{ marginBottom: 6 }}>
                          {shift}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {emotionTurns.length ? (
                  <div style={{ marginTop: 12 }}>
                    <div style={{ fontWeight: 800, marginBottom: 8 }}>Per-question emotion trend</div>
                    <div style={{ display: 'grid', gap: 10 }}>
                      {emotionTurns.map((turn) => (
                        <div key={turn.turn_index} style={{ border: '1px solid #f3f3f3', padding: 10, borderRadius: 8 }}>
                          <div style={{ fontSize: 13, color: '#666' }}>Turn {turn.turn_index}</div>
                          <div style={{ fontWeight: 700 }}>{renderEmotionTrendLabel(turn)}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </>
            ) : null}
          </div>

          <div style={{ border: '1px solid #eee', padding: 14, borderRadius: 8 }}>
            <h3 style={{ marginTop: 0 }}>Strengths & weaknesses</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
              <div>
                <b>Strengths</b>
                {strengths.length ? (
                  <ul style={{ marginTop: 8, paddingLeft: 18 }}>
                    {strengths.map((s, i) => (
                      <li key={i} style={{ marginBottom: 8 }}>
                        <div style={{ fontSize: 13, color: '#666' }}>
                          {s.mode} · Turn {s.turn_index ?? '—'}
                        </div>
                        <div style={{ fontWeight: 700 }}>{s.moment ?? 'Moment identified'}</div>
                        <div style={{ fontSize: 13, color: '#333' }}>{s.evidence}</div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p style={{ color: '#666' }}>No strengths found.</p>
                )}
              </div>

              <div>
                <b>Weaknesses</b>
                {weaknesses.length ? (
                  <ul style={{ marginTop: 8, paddingLeft: 18 }}>
                    {weaknesses.map((w, i) => (
                      <li key={i} style={{ marginBottom: 8 }}>
                        <div style={{ fontSize: 13, color: '#666' }}>
                          {w.mode} · Turn {w.turn_index ?? '—'}
                        </div>
                        <div style={{ fontWeight: 700 }}>{w.moment ?? 'Moment identified'}</div>
                        <div style={{ fontSize: 13, color: '#333' }}>{w.evidence}</div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p style={{ color: '#666' }}>No weaknesses found.</p>
                )}
              </div>
            </div>
          </div>

          <div style={{ border: '1px solid #eee', padding: 14, borderRadius: 8 }}>
            <h3 style={{ marginTop: 0 }}>Question-by-question breakdown</h3>
            {questionBreakdown.length ? (
              <div style={{ display: 'grid', gap: 12 }}>
                {questionBreakdown.map((item, i) => (
                  <details key={i} style={{ border: '1px solid #f6f6f6', padding: 12, borderRadius: 8 }}>
                    <summary style={{ cursor: 'pointer', fontWeight: 800 }}>
                      {item.mode} · Turn {item.turn_index}
                    </summary>

                    <div style={{ marginTop: 10, color: '#333' }}>
                      <div style={{ fontWeight: 800 }}>Question</div>
                      <div style={{ whiteSpace: 'pre-wrap' }}>{item.question}</div>

                      {item.answer_or_code ? (
                        <div style={{ marginTop: 10 }}>
                          <div style={{ fontWeight: 800 }}>Your answer/code</div>
                          <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', background: '#fafafa', padding: 10, borderRadius: 6 }}>
                            {item.answer_or_code}
                          </pre>
                        </div>
                      ) : null}

                      {item.speech_metrics ? (
                        <div style={{ marginTop: 10, fontSize: 13, color: '#666' }}>
                          <b>Speech metrics</b>: {JSON.stringify(item.speech_metrics)}
                        </div>
                      ) : null}

                      {item.emotion_snapshot ? (
                        <div style={{ marginTop: 10, fontSize: 13, color: '#666' }}>
                          <b>Emotion snapshot</b>: {JSON.stringify(item.emotion_snapshot)}</div>
                      ) : null}

                      <div style={{ marginTop: 10 }}>
                        <div style={{ fontWeight: 800 }}>AI feedback (0-10)</div>
                        <div style={{ fontSize: 13, color: '#666' }}>
                          relevance: {item.ai_feedback?.relevance?.toFixed?.(1) ?? item.ai_feedback?.relevance}
                          {' · '}depth: {item.ai_feedback?.depth?.toFixed?.(1) ?? item.ai_feedback?.depth}
                          {' · '}structure: {item.ai_feedback?.structure?.toFixed?.(1) ?? item.ai_feedback?.structure}
                          {' · '}overall: {item.ai_feedback?.overall?.toFixed?.(1) ?? item.ai_feedback?.overall}
                        </div>
                        {item.ai_feedback?.justification ? (
                          <div style={{ marginTop: 6, whiteSpace: 'pre-wrap' }}>{item.ai_feedback.justification}</div>
                        ) : null}
                      </div>
                    </div>
                  </details>
                ))}
              </div>
            ) : (
              <p style={{ color: '#666' }}>No question breakdown available.</p>
            )}
          </div>
        </div>
      ) : null}

    </PageShell>
  );
}

