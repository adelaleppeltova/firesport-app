import { Link } from "react-router-dom";

export default function MyData() {
  return (
    <Link to="/data" className="my-data">
      <span className="my-data__icon">📄</span>
      <span>Moje data</span>
      <span className="my-data__arrow">›</span>
    </Link>
  );
}