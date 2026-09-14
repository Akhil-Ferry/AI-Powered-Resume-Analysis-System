export default function BadgeList({ items = [], tone = "default", emptyLabel = "None" }) {
  if (!items || items.length === 0) {
    return <span className="muted">{emptyLabel}</span>;
  }
  return (
    <div className="badge-list">
      {items.map((item, i) => (
        <span key={`${item}-${i}`} className={`badge badge-${tone}`}>
          {item}
        </span>
      ))}
    </div>
  );
}
