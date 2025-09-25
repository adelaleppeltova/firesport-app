import React, { useEffect, useState } from "react";
import { fetchAthletes } from "../api/athletes";

function AthletesPage() {
  const [athletes, setAthletes] = useState([]);

  useEffect(() => {
    fetchAthletes().then((res) => setAthletes(res.data));
  }, []);

  return (
    <div>
      <h2>Athletes</h2>
      {athletes.map((a) => (
        <AthleteCard key={a._id} athlete={a} />
      ))}
    </div>
  );
}

export default AthletesPage;
