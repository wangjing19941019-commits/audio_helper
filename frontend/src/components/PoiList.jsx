function formatDistance(meters) {
  if (typeof meters !== "number" || Number.isNaN(meters)) {
    return "";
  }
  const rounded = Number.isInteger(meters) ? String(meters) : String(Math.round(meters * 10) / 10);
  return `距离中点 ${rounded} 米`;
}

export default function PoiList({ pois }) {
  if (!Array.isArray(pois) || pois.length === 0) {
    return null;
  }
  return (
    <section className="result-block">
      <h2>候选店铺</h2>
      <ol className="poi-list">
        {pois.slice(0, 3).map((poi, index) => (
          <li key={`${poi.name}-${poi.address}-${index}`}>
            <strong>{poi.name}</strong>
            <p>{poi.address}</p>
            <p className="hint">{formatDistance(poi.distance_to_midpoint_m)}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
