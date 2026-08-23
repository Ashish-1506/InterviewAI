export default function AnimatedMentor({ compact = false, speaking = false }) {
  return (
    <div
      className={`mentor-scene ${compact ? 'mentor-scene--compact' : ''} ${speaking ? 'mentor-scene--speaking' : ''}`}
      aria-label="Animated InterviewAI practice guide"
      role="img"
    >
      <span className="mentor-orbit mentor-orbit--one" />
      <span className="mentor-orbit mentor-orbit--two" />
      <span className="mentor-spark mentor-spark--one" />
      <span className="mentor-spark mentor-spark--two" />
      <div className="mentor-bubble">
        <span className="mentor-bubble-dot" />
        <span>{speaking ? 'I’m listening' : 'Let’s prepare'}</span>
      </div>
      <div className="mentor-character" aria-hidden="true">
        <div className="mentor-head">
          <span className="mentor-ear mentor-ear--left" />
          <span className="mentor-ear mentor-ear--right" />
          <span className="mentor-antenna" />
          <div className="mentor-face">
            <span className="mentor-eye" />
            <span className="mentor-eye" />
            <span className="mentor-smile" />
          </div>
        </div>
        <div className="mentor-body"><span>IA</span></div>
      </div>
    </div>
  );
}
