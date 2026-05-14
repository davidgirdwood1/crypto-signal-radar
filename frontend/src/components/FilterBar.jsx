const classifications = [
  "Bullish Momentum",
  "Bearish Momentum",
  "Hype / Meme Pump",
  "Scam Risk",
  "Liquidity Risk",
  "Regulatory Risk",
  "Exchange / Listing Signal",
  "Social / Narrative Signal",
  "Noise / Ignore"
];

const sentiments = ["bullish", "bearish", "neutral", "risky", "unknown"];

export default function FilterBar({ filters, onChange }) {
  function setFilter(key, value) {
    onChange({ ...filters, [key]: value });
  }

  return (
    <section className="filter-bar" aria-label="Event filters">
      <select value={filters.source} onChange={(event) => setFilter("source", event.target.value)}>
        <option value="">All sources</option>
        <option value="dexscreener">DEX Screener</option>
        <option value="coingecko">CoinGecko</option>
      </select>
      <select value={filters.classification} onChange={(event) => setFilter("classification", event.target.value)}>
        <option value="">All classifications</option>
        {classifications.map((item) => <option key={item} value={item}>{item}</option>)}
      </select>
      <select value={filters.sentiment} onChange={(event) => setFilter("sentiment", event.target.value)}>
        <option value="">All sentiment</option>
        {sentiments.map((item) => <option key={item} value={item}>{item}</option>)}
      </select>
      <label className="risk-input">
        <span>Min risk</span>
        <input
          type="number"
          min="0"
          max="100"
          value={filters.min_risk_score}
          onChange={(event) => setFilter("min_risk_score", event.target.value)}
        />
      </label>
    </section>
  );
}
