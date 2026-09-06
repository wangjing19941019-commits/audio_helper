export default function ReplyPanel({ reply, warning, audioUrl, needPlayButton, onManualPlay }) {
  if (!reply && !warning) {
    return null;
  }
  return (
    <section className="result-block">
      <h2>推荐语</h2>
      {reply ? <p className="reply-text">{reply}</p> : null}
      {warning ? <p className="status status-error">{warning}</p> : null}
      {audioUrl && needPlayButton ? (
        <button type="button" className="play-button" onClick={onManualPlay}>
          播放推荐语音
        </button>
      ) : null}
    </section>
  );
}
