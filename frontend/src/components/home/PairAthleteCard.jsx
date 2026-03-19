import { useState } from "react";
import Card from "../Card";
import PairAthleteDialog from "./PairAthleteDialog";
import PrimaryButton from "../PrimaryButton";

export default function PairAthleteCard() {
  const [showPairDialog, setShowPairDialog] = useState(false);

  return (
    <>
      <Card title="Propoj účet se závodníkem" className="card--home-account">
        <div className="pair-athlete">
          <p className="pair-athlete__text">
            Propojení účtu zpřístupní personalizovaný přehled výsledků,
            statistik a vývoje výkonu.
          </p>
          <div className="button-center">
            <PrimaryButton onClick={() => setShowPairDialog(true)}>
              Vybrat závodníka
            </PrimaryButton>
          </div>
        </div>
      </Card>
      {showPairDialog && (
        <PairAthleteDialog onClose={() => setShowPairDialog(false)} />
      )}
    </>
  );
}
