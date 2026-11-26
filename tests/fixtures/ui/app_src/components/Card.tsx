export default function Card({ title }) {
  return (
    <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", boxShadow: "0 1px 2px rgba(0,0,0,.1)" }}>
      <h3 style={{ color: "#0f172a" }}>{title}</h3>
      <p style={{ color: "#64748b" }}>Card body</p>
      <a style={{ color: "#2563eb" }} href="#more">More</a>
    </div>
  );
}
